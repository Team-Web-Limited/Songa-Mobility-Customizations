import frappe
from songa_mobility_customizations.services.notifications.branch_role import (
    notify_users_by_branch_and_role
)

def handle_transfer_request(doc):
    if doc.workflow_state != "Pending Approval":
        return

    from_warehouse = doc.items[0].from_warehouse if doc.items else None
    if not from_warehouse:
        return

    warehouse = frappe.get_doc("Warehouse", from_warehouse)
    branch = warehouse.custom_branch

    notify_users_by_branch_and_role(
        branch=branch,
        role="Hub Manager",
        title="Material Transfer Request Pending Approval",
        message=(
            f"Material Transfer Request {doc.name} "
            "has been submitted for your approval."
        ),
        reference_doctype=doc.doctype,
        reference_name=doc.name
    )


    