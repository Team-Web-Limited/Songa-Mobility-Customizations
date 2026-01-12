import frappe
from frappe.utils import get_url
from songa_mobility_customizations.services.notifications.branch_role import get_users_by_branch_and_role

def handle_stock_entry_workflow(doc, method):
    """
    Handle notifications for Stock Entry workflow
    Triggered on_update of Stock Entry documents
    """
    if doc.purpose != "Material Transfer":
        print(f"Skipping Stock Entry Notification: Purpose is {doc.purpose}")
        return

    # Check if workflow state changed to "In Transit"
    if doc.has_value_changed("workflow_state") and doc.workflow_state == "In Transit":
        # Get Material Request from the items (assuming created from MR)
        material_request_name = None
        for item in doc.items:
            if item.material_request:
                material_request_name = item.material_request
                break
        
        real_target_warehouse = None
        
        if material_request_name:
            # Fetch the Material Request document to get the actual target warehouse
            mr_doc = frappe.get_doc("Material Request", material_request_name)
            # In Material Request, the target warehouse is usually 'set_warehouse' (for Transfer)
            # or 'to_warehouse' in items. Based on previous context, 'set_warehouse' is used.
            real_target_warehouse = mr_doc.set_warehouse or (mr_doc.items[0].warehouse if mr_doc.items else None)
            
            print(f"\n\n\n\n\n Linked Material Request: {material_request_name} | Real Target Warehouse: {real_target_warehouse} \n\n\n\n\n")
        else:
            # Fallback if no MR linked (though workflow implies it)
             print(f"\n\n\n\n\n No linked Material Request found in items for {doc.name} \n\n\n\n\n")
             return

        if not real_target_warehouse:
            print(f"Skipping Stock Entry Notification: No target warehouse found via MR for {doc.name}")
            return

        notify_target_hub_manager(doc, real_target_warehouse)


def notify_target_hub_manager(doc, to_warehouse):
    print(f"\n\n\n\n\n notify_target_hub_manager : {to_warehouse} \n\n\n\n\n")
    try:
        warehouse = frappe.get_doc("Warehouse", to_warehouse)
        branch = warehouse.custom_branch
        print(f"\n\n\n\n\n branch : {branch}\n\n\n\n\n")

        # Get all users with role 'Hub Manager' for this branch
        hub_managers = get_users_by_branch_and_role(branch, "Hub Manager")
        print(f"\n\n\n\n\n hub_managers : {hub_managers}\n\n\n\n\n")
        
        if not hub_managers:
            frappe.log_error(f"No Hub Manager found for branch {branch}", "Workflow Notification")
            print(f"\n\n\n\n\n No Hub Manager found for branch {branch} \n\n\n\n\n")
            return

        # Document URL
        doc_url = get_url(doc.get_url())

        subject = "Material Transfer In Transit – Approval Required"
        message = f"""
        <p>A Material Transfer is now marked In Transit and requires your review.</p>
        <ul>
            <li><strong>Stock Entry:</strong> {doc.name}</li>
            <li><strong>From Warehouse:</strong> {doc.from_warehouse}</li>
            <li><strong>To Warehouse:</strong> {doc.to_warehouse or to_warehouse}</li>
        </ul>
        <p>Please review quantities, valuation, then approve or reject once the goods arrive.</p>
        <p>If approved please create and submit the Stock Entry (Material Receipt).</p>
        <p>Access the document here: <a href="{doc_url}">{doc.name}</a></p>
        """

        for manager in hub_managers:
            print(f"\n\n\n\n\n manager : {manager}\n\n\n\n\n")
            frappe.sendmail(
                recipients=[manager],
                subject=subject,
                message=message,
                now=True
            )

        frappe.msgprint(f"Hub Manager(s) for branch '{branch}' notified about {doc.name}")

    except Exception as e:
        frappe.log_error(f"Error notifying Target Hub Manager: {str(e)}", "Workflow Notification") 