import frappe
from frappe.utils import get_url

def handle_material_request_workflow(doc, method):
    """
    Handle workflow state changes for Material Request
    Triggered on_update of Material Request documents
    """
    # Only proceed for Material Transfer type
    if doc.material_request_type != "Material Transfer":
        return
    
    # Check if workflow state changed to "Approved"
    if doc.has_value_changed("workflow_state") and doc.workflow_state == "Approved":
        notify_operations_manager(doc)

def notify_operations_manager(doc):
    """
    Notify Operations Manager about approved Material Transfer
    """
    try:
        # Find all users with Operations Manager role
        ops_managers = frappe.get_all(
            "Has Role",
            filters={"role": "Operations Manager", "parenttype": "User"},
            fields=["parent"]
        )
        
        if not ops_managers:
            frappe.log_error("No Operations Manager found for notification", "Workflow Notification")
            return
        
        # Get the document URL
        doc_url = get_url(doc.get_url())
        
        # Prepare email content
        subject = f"Material Transfer Request Approved - {doc.name}"
        message = f"""
        <p>Hello Operations Manager,</p>
        
        <p>The Material Transfer Request <strong>{doc.name}</strong> has been approved by the Hub Manager and is ready for you to process.</p>
        
        <p><strong>Request Details:</strong></p>
        <ul>
            <li><strong>Requested By:</strong> {doc.owner}</li>
            <li><strong>From Warehouse:</strong> {doc.set_warehouse}</li>
            <li><strong>To Warehouse:</strong> {doc.get('to_warehouse', 'Not specified')}</li>
            <li><strong>Items:</strong> {len(doc.items)} item(s)</li>
        </ul>
        
        <p>Please create a Stock Entry (Material Transfer) to move the items to the target warehouse.</p>
        
        <p>You can access the request here: <a href="{doc_url}">{doc.name}</a></p>
        
        <p>Thank you.</p>
        """
        
        # Send email to all Operations Managers
        for manager in ops_managers:
            frappe.sendmail(
                recipients=[manager.parent],
                subject=subject,
                message=message,
                now=True
            )
            
        # Also create a system notification (Toast)
        frappe.msgprint(f"Operations Manager has been notified about approved transfer {doc.name}")
        
    except Exception as e:
        frappe.log_error(f"Error notifying Operations Manager: {str(e)}", "Workflow Notification")


