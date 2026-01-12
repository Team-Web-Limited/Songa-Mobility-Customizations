import frappe
from frappe.utils import get_url
from songa_mobility_customizations.services.notifications.branch_role import get_users_by_branch_and_role

def handle_purchase_invoice_workflow(doc, method):
    """
    Handle notifications for Purchase Invoice workflow
    Triggered on_update of Purchase Invoice documents
    """
    
    # 3.D. Purchase Invoice Approved -> Warehouse
    # Trigger: When PI is "Submitted" or "Approved" (assuming Submitted implies approval in standard flow, or specific workflow state)
    # Requirement: "The Purchase Invoice has been submitted."
    
    # Checking for "Submitted" state or simply docstatus=1 if not using workflow state field
    # If using workflow, we check workflow_state. 
    # Let's assume generic "Approved" or "Submitted" state name. 
    # Or strict check on submission if workflow engine sets state to "Submitted".
    
    # Case 1: Workflow State change
    if doc.has_value_changed("workflow_state") and doc.workflow_state in ["Submitted", "Approved"]:
        notify_target_warehouse_hm(doc)
    
    # Case 2: Standard Submission (if workflow state isn't the only trigger)
    # But usually we stick to one. If the requirement says "Approved -> Warehouse", we stick to workflow state.
    

def notify_target_warehouse_hm(doc):
    # To: Target Warehouse HM
    # Subject: Material Receipt Pending – Create Stock Entry
    # Body: The Purchase Invoice has been submitted. Please create and submit the Stock Entry (Material Receipt).
    
    # Note: Purchase Invoice implies we are paying. The goods might already be received (Purchase Receipt) 
    # or this PI is for a service/direct purchase.
    # Requirement implies "Create Stock Entry (Material Receipt)". This suggests the PI updates stock 
    # OR we are skipping Purchase Receipt and doing PI -> Stock Entry (?).
    # Standard ERPNext: Purchase Invoice *can* update stock ("Update Stock" checkbox).
    # If it logic implies a separate Stock Entry is needed, maybe it's for internal tracking?
    # We just need to find the "Target Warehouse".
    
    # Purchase Invoice Items have "warehouse" (Accepted Warehouse).
    # We'll pick the warehouse from the first item.
    
    target_warehouse = doc.items[0].warehouse if doc.items else None
    
    if not target_warehouse:
        # Some PIs might not update stock (Service).
        return

    try:
        warehouse_doc = frappe.get_doc("Warehouse", target_warehouse)
        branch = warehouse_doc.custom_branch
        
        if not branch:
             frappe.log_error(f"No branch found for warehouse {target_warehouse}", "Workflow Notification")
             return

        hub_managers = get_users_by_branch_and_role(branch, "Hub Manager")

        if not hub_managers:
            frappe.log_error(f"No Hub Manager found for branch {branch}", "Workflow Notification")
            return

        doc_url = get_url(doc.get_url())
        subject = "Material Receipt Pending – Create Stock Entry"
        
        message = f"""
        <p>The Purchase Invoice has been submitted.</p>
        <ul>
            <li><strong>Invoice:</strong> {doc.name}</li>
            <li><strong>Supplier:</strong> {doc.supplier}</li>
            <li><strong>Target Warehouse:</strong> {target_warehouse}</li>
        </ul>
        <p>Please create and submit the Stock Entry (Material Receipt).</p>
        <p>Access the document here: <a href="{doc_url}">{doc.name}</a></p>
        """

        for manager in hub_managers:
            frappe.sendmail(recipients=[manager], subject=subject, message=message, now=True)

        frappe.msgprint(f"Hub Manager(s) for branch '{branch}' notified about {doc.name}")
        
    except Exception as e:
         frappe.log_error(f"Error notifying PI Target Warehouse HM: {str(e)}", "Workflow Notification")
