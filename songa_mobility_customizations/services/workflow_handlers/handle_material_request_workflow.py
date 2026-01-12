import frappe
from frappe.utils import get_url
from songa_mobility_customizations.services.notifications.branch_role import get_users_by_branch_and_role


def handle_material_request_workflow(doc, method):
    print("\n\n\n\n\n handle_material_request_workflow \n\n\n\n\n")
    """
    Handle workflow state changes for Material Request
    Triggered on_update of Material Request documents
    """
    # Only proceed for Material Transfer type
    if doc.material_request_type != "Material Transfer":
        print(f"Skipping workflow handler: Type is {doc.material_request_type}")
        return
    
    print("\n\n\n\n Material Request Workflow \n\n\n\n")
    
    # Check if workflow state changed to "Pending Approval"
    if doc.has_value_changed("workflow_state") and doc.workflow_state == "Pending Approval":
        print("\n\n\n\n workflow state value changed Pending Approval \n\n\n\n")
        notify_hub_manager(doc)

    # Check if workflow state changed to "Approved"
    if doc.has_value_changed("workflow_state") and doc.workflow_state == "Approved":
        print("\n\n\n\n Approved \n\n\n\n")
        notify_operations_manager(doc)


def notify_hub_manager(doc):
    print("\n\n\n\n notify_hub_manager \n\n\n\n")
    """
    Notify the Hub Manager(s) responsible for the branch of the source warehouse
    """
    try:
        from_warehouse = doc.set_from_warehouse
        if not from_warehouse:
            frappe.log_error(f"No source warehouse found for {doc.name}", "Workflow Notification")
            return

        warehouse = frappe.get_doc("Warehouse", from_warehouse)
        branch = warehouse.custom_branch

        # Get all users with role 'Hub Manager' for this branch
        hub_managers = get_users_by_branch_and_role(branch, "Hub Manager")
        print("\n\n\n\n hub_managers \n\n", hub_managers)
        
        if not hub_managers:
            frappe.log_error(f"No Hub Manager found for branch {branch}", "Workflow Notification")
            print("\n\n\n\n No Hub Manager found for branch {branch} \n\n")
            return

        # Document URL
        doc_url = get_url(doc.get_url())

        subject = "Material Transfer Request Pending Approval"
        message = f"""
        <p>A Material Transfer Request has been submitted for your approval.</p>
        <ul>
            <li><strong>Request ID:</strong> {doc.name}</li>
            <li><strong>Requested By:</strong> {doc.owner}</li>
            <li><strong>From Warehouse:</strong> {doc.set_from_warehouse}</li>
            <li><strong>To Warehouse:</strong> {doc.get('set_warehouse', 'Not specified')}</li>
            <li><strong>Items:</strong> {len(doc.items)} item(s)</li>
        </ul>
        <p>Please review quantities, valuation, and availability, then approve or reject.</p>
        <p>Access the request here: <a href="{doc_url}">{doc.name}</a></p>
        """

        for manager in hub_managers:
            frappe.sendmail(
                recipients=[manager],
                subject=subject,
                message=message,
                now=True
            )

        frappe.msgprint(f"Hub Manager(s) for branch '{branch}' notified about {doc.name}")

    except Exception as e:
        frappe.log_error(f"Error notifying Hub Manager: {str(e)}", "Workflow Notification")


def notify_operations_manager(doc):
    print("\n\n\n\n\n notify_operations_manager \n\n\n\n\n")
    """
    Notify the Operations Manager(s) responsible for the branch of the source warehouse
    """
    try:
        from_warehouse = doc.set_from_warehouse
        if not from_warehouse:
            frappe.log_error(f"No source warehouse found for {doc.name}", "Workflow Notification")
            return

        warehouse = frappe.get_doc("Warehouse", from_warehouse)
        print("\n\n\n\n\n warehouse \n\n\n\n\n", warehouse)
        branch = warehouse.custom_branch
        print("\n\n\n\n\n branch \n\n\n\n\n", branch)

        # Get all users with role 'Operations Manager' for this branch
        ops_managers = get_users_by_branch_and_role(branch, "Operations Manager")
        print("\n\n\n\n\n ops_managers \n\n\n\n\n", ops_managers)
        
        if not ops_managers:
            frappe.log_error(f"No Operations Manager found for branch {branch}", "Workflow Notification")
            print("\n\n\n\n\n No Operations Manager found for branch {branch} \n\n\n\n\n")
            return

        # Document URL
        doc_url = get_url(doc.get_url())
        print("\\n\\n\\n\\n\\n doc_url \\n\\n\\n\\n\\n", doc_url)

        subject = "Material Transfer Request Pending Approval"
        
        # Helper to get full name
        hub_manager_name = frappe.db.get_value("User", doc.modified_by, "full_name") or doc.modified_by
        
        message = f"""
        <p>A Material Transfer Request has been approved by {hub_manager_name}.</p>
        <p>Next step: create the Material Transfer and mark it as In Transit.</p>
        <p>Access the request here: <a href="{doc_url}">{doc.name}</a></p>
        """

        for manager in ops_managers:
            print("\\n\\n\\n\\n\\n manager \\n\\n\\n\\n\\n", manager)
            print("\\n\\n\\n\\n\\n subject \\n\\n\\n\\n\\n", subject)
            print("\\n\\n\\n\\n\\n message \\n\\n\\n\\n\\n", message)
            frappe.sendmail(
                recipients=[manager],
                subject=subject,
                message=message,
                now=True
            )

        frappe.msgprint(f"Operations Manager(s) for branch '{branch}' notified about {doc.name}")

    except Exception as e:
        frappe.log_error(f"Error notifying Operations Manager: {str(e)}", "Workflow Notification") 
