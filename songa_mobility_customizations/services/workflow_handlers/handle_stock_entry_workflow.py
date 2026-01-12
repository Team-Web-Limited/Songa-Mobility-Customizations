import frappe
from frappe.utils import get_url
from songa_mobility_customizations.services.notifications.branch_role import get_users_by_branch_and_role

def handle_stock_entry_workflow(doc, method):
    """
    Handle notifications for Stock Entry submission
    Triggered on_submit of Stock Entry documents
    """
    if doc.purpose != "Material Transfer":
        print(f"Skipping Stock Entry Notification: Purpose is {doc.purpose}")
        return

    # Check if items are being added to transit (implies movement to transit warehouse)
    # or validation logic specific to "In Transit" step if workflow field exists.
    # Standard Stock Entry for Material Transfer moves from Source to Target.
    # If the user requirement is "Material Transfer In Transit", it usually means 
    # the goods are leaving the source and going to a transit warehouse (or target).
    
    # Assuming 'add_to_transit' check or simply on submission of a Material Transfer
    # where the target warehouse implies transit/destination.
    # The requirement says: "marked In Transit".
    
    # We will check if there is a target warehouse and notify its Hub Manager
    
    # Get Target Warehouse from the first item (assuming all go to same place for this context)
    to_warehouse = doc.items[0].t_warehouse if doc.items else None
    
    if not to_warehouse:
        print(f"Skipping Stock Entry Notification: No target warehouse found for {doc.name}")
        return

    notify_target_hub_manager(doc, to_warehouse)


def notify_target_hub_manager(doc, to_warehouse):
    print("\n\n\n\n\n notify_target_hub_manager \n\n\n\n")
    try:
        warehouse = frappe.get_doc("Warehouse", to_warehouse)
        branch = warehouse.custom_branch
        print("\n\n\n\n\n branch \n\n\n\n\n", branch)

        # Get all users with role 'Hub Manager' for this branch
        hub_managers = get_users_by_branch_and_role(branch, "Hub Manager")
        print("\n\n\n\n\n hub_managers \n\n\n\n\n", hub_managers)
        
        if not hub_managers:
            frappe.log_error(f"No Hub Manager found for branch {branch}", "Workflow Notification")
            print("\n\n\n\n\n No Hub Manager found for branch {branch} \n\n\n\n\n")
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
            print("\n\n\n\n\n manager \n\n\n\n\n", manager)
            frappe.sendmail(
                recipients=[manager],
                subject=subject,
                message=message,
                now=True
            )

        frappe.msgprint(f"Hub Manager(s) for branch '{branch}' notified about {doc.name}")

    except Exception as e:
        frappe.log_error(f"Error notifying Target Hub Manager: {str(e)}", "Workflow Notification") 