import frappe
from frappe.utils import get_url
from songa_mobility_customizations.services.notifications.branch_role import get_users_by_branch_and_role


def handle_material_request_workflow(doc, method):
    print("\n\n\n\n\n handle_material_request_workflow \n\n\n\n\n")
    
    # Check if workflow state changed to "Pending Approval"
    if doc.has_value_changed("workflow_state") and doc.workflow_state == "Pending Approval":
        print("\n\n\n\n\n workflow state value changed Pending Approval \n\n\n\n")
        
        if doc.material_request_type == "Material Transfer":
            notify_transfer_pending_approval(doc)
            
        elif doc.material_request_type == "Material Issue":
             notify_issue_pending_approval(doc)
             
        elif doc.material_request_type == "Purchase":
             notify_purchase_pending_approval(doc)

    # Check if workflow state changed to "Approved"
    if doc.has_value_changed("workflow_state") and doc.workflow_state == "Approved":
        print("\n\n\n\n\n Approved \n\n\n\n")
        
        if doc.material_request_type == "Material Transfer":
            notify_transfer_approved(doc)


# --- Notification Functions ---

def notify_transfer_pending_approval(doc):
    print("\n\n\n\n\n notify_transfer_pending_approval \n\n\n\n")
    # For Transfer, source is set_from_warehouse
    warehouse_name = doc.set_from_warehouse
    
    # To: Hub Manager (HM Source Warehouse)
    notify_hub_manager(doc, subject_prefix="Material Transfer Request", 
                       body_intro="A Material Transfer Request has been submitted for your approval.",
                       body_instruction="Please review quantities, valuation, and availability, then approve or reject.",
                       warehouse_name=warehouse_name)


def notify_issue_pending_approval(doc):
    print("\n\n\n\n\n notify_issue_pending_approval \n\n\n\n")
    # For Issue, source is in items.warehouse
    warehouse_name = doc.items[0].warehouse if doc.items else None
    
    # To: Hub Manager (HM Source Warehouse)
    notify_hub_manager(doc, subject_prefix="Material Issue Request", 
                       body_intro="A Material Issue Request has been submitted for your approval.",
                       body_instruction="Review item quantity, valuation, and purpose, then approve or reject.",
                       warehouse_name=warehouse_name)


def notify_purchase_pending_approval(doc):
    print("\n\n\n\n\n notify_purchase_pending_approval \n\n\n\n")
    # To: Operations Manager (OM)
    
    ops_managers = frappe.get_all("Has Role", filters={"role": "Operations Manager", "parenttype": "User"}, pluck="parent")
    
    print("\n\n\n\n\n ops_managers \n\n\n\n\n", ops_managers)
    
    if not ops_managers:
        frappe.log_error("No Operations Manager found", "Workflow Notification")
        print("\n\n\n\n\n No Operations Manager found \n\n\n\n\n")
        return

    doc_url = get_url(doc.get_url())
    subject = "Purchase Material Request Pending Approval"
    
    message = f"""
    <p>A Purchase Material Request has been submitted.</p>
    <ul>
        <li><strong>Request ID:</strong> {doc.name}</li>
        <li><strong>Requested By:</strong> {doc.owner}</li>
        <li><strong>Items:</strong> {len(doc.items)} item(s)</li>
    </ul>
    <p>Please approve the request and create the corresponding Purchase Order.</p>
    <p>Access the request here: <a href="{doc_url}">{doc.name}</a></p>
    """

    for manager in ops_managers:
        frappe.sendmail(recipients=[manager], subject=subject, message=message, now=True)

    frappe.msgprint(f"Operations Manager notified about {doc.name}")


def notify_transfer_approved(doc):
    print("\n\n\n\n\n notify_transfer_approved \n\n\n\n\n")
    # To: Operations Manager (OM)
    # Subject: Material Transfer Request Pending Approval
    # Body: A Material Transfer Request has been approved by (Hub Manager name). Next step: create the Material Transfer and mark it as In Transit.
    
    ops_managers = frappe.get_all("Has Role", filters={"role": "Operations Manager", "parenttype": "User"}, pluck="parent")
    
    print("\n\n\n\n\n ops_managers \n\n\n\n\n", ops_managers)
    
    if not ops_managers:
        frappe.log_error("No Operations Manager found", "Workflow Notification")
        return

    doc_url = get_url(doc.get_url())
    subject = "Material Transfer Request Pending Approval"
    
    hub_manager_name = frappe.db.get_value("User", doc.modified_by, "full_name") or doc.modified_by
    
    message = f"""
    <p>A Material Transfer Request has been approved by {hub_manager_name}.</p>
    <p>Next step: create the Material Transfer and mark it as In Transit.</p>
    <p>Access the request here: <a href="{doc_url}">{doc.name}</a></p>
    """

    for manager in ops_managers:
        frappe.sendmail(recipients=[manager], subject=subject, message=message, now=True)

    frappe.msgprint(f"Operations Manager notified about {doc.name}")


# --- Helper ---

def notify_hub_manager(doc, subject_prefix, body_intro, body_instruction, warehouse_name=None):
    print(f"\n\n\n\n\n notify_hub_manager {subject_prefix} \n\n\n\n\n")
    try:
        # Use provided warehouse name, or fallback to set_from_warehouse (legacy/safe default)
        target_warehouse = warehouse_name or doc.get("set_from_warehouse")
        
        if not target_warehouse:
            frappe.log_error(f"No source warehouse found for {doc.name}", "Workflow Notification")
            print(f"No warehouse found for {doc.name}")
            return

        warehouse = frappe.get_doc("Warehouse", target_warehouse)
        print(f"\n\n\n\n\n warehouse {warehouse} \n\n\n\n\n")
        branch = warehouse.custom_branch
        print(f"\n\n\n\n\n branch {branch} \n\n\n\n\n")

        hub_managers = get_users_by_branch_and_role(branch, "Hub Manager")
        print(f"\n\n\n\n\n hub_managers {hub_managers} \n\n\n\n\n")
        
        if not hub_managers:
            frappe.log_error(f"No Hub Manager found for branch {branch}", "Workflow Notification")
            print(f"\n\n\n\n\n No Hub Manager found for branch {branch} \n\n\n\n\n")
            return

        doc_url = get_url(doc.get_url())
        subject = f"{subject_prefix} Pending Approval"
        
        message = f"""
        <p>{body_intro}</p>
        <ul>
            <li><strong>Request ID:</strong> {doc.name}</li>
            <li><strong>Requested By:</strong> {doc.owner}</li>
            <li><strong>Warehouse:</strong> {target_warehouse}</li>
            <li><strong>Items:</strong> {len(doc.items)} item(s)</li>
        </ul>
        <p>{body_instruction}</p>
        <p>Access the request here: <a href="{doc_url}">{doc.name}</a></p>
        """

        for manager in hub_managers:
            frappe.sendmail(recipients=[manager], subject=subject, message=message, now=True)

        frappe.msgprint(f"Hub Manager(s) for branch '{branch}' notified about {doc.name}")

    except Exception as e:
        frappe.log_error(f"Error notifying Hub Manager: {str(e)}", "Workflow Notification")
