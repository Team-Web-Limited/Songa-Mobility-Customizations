import frappe
from frappe.utils import get_url

def handle_purchase_order_workflow(doc, method):
    """
    Handle notifications for Purchase Order workflow
    Triggered on_update of Purchase Order documents
    """
    
    # 3.B. Purchase Order Exceeds Budget -> General Manager
    # Assumption: There is a workflow state expressly for this, or we check generic "Pending Approval" 
    # and some flag. For now, we will handle "Budget Approval" if that state exists, 
    # or just "Pending Approval" if we want to catch general approvals.
    # Requirement: "Purchase Order Requires Budget Approval"
    # If the state is specifically "Pending Budget Approval":
    if doc.has_value_changed("workflow_state") and doc.workflow_state == "Pending Budget Approval":
        notify_general_manager_budget(doc)
        
    # 3.C. Purchase Order Approved -> Finance Step (Accounts Manager)
    if doc.has_value_changed("workflow_state") and doc.workflow_state == "Approved":
        notify_accounts_manager(doc)


def notify_general_manager_budget(doc):
    # To: General Manager (GM)
    # Subject: Purchase Order Requires Budget Approval
    # Body: A Purchase Order exceeds the allocated cost center budget. Your approval is required before the purchase can proceed.
    
    # Get users with role "General Manager"
    general_managers = frappe.get_all("Has Role", filters={"role": "General Manager", "parenttype": "User"}, pluck="parent")

    if not general_managers:
        frappe.log_error("No General Manager found", "Workflow Notification")
        return

    doc_url = get_url(doc.get_url())
    subject = "Purchase Order Requires Budget Approval"
    
    message = f"""
    <p>A Purchase Order exceeds the allocated cost center budget.</p>
    <ul>
        <li><strong>PO Number:</strong> {doc.name}</li>
        <li><strong>Supplier:</strong> {doc.supplier}</li>
        <li><strong>Grand Total:</strong> {doc.grand_total}</li>
    </ul>
    <p>Your approval is required before the purchase can proceed.</p>
    <p>Access the document here: <a href="{doc_url}">{doc.name}</a></p>
    """

    for manager in general_managers:
        frappe.sendmail(recipients=[manager], subject=subject, message=message, now=True)

    frappe.msgprint(f"General Manager notified about {doc.name}")


def notify_accounts_manager(doc):
    # To: Accounts Manager (AM)
    # Subject: Purchase Order Approved – Finance Processing Required
    # Body: A Purchase Order has been approved. Please proceed with the Purchase Receipt, Purchase Invoice, and/or Payment processing.

    accounts_managers = frappe.get_all("Has Role", filters={"role": "Accounts Manager", "parenttype": "User"}, pluck="parent")

    if not accounts_managers:
        frappe.log_error("No Accounts Manager found", "Workflow Notification")
        return

    doc_url = get_url(doc.get_url())
    subject = "Purchase Order Approved – Finance Processing Required"
    
    message = f"""
    <p>A Purchase Order has been approved.</p>
    <ul>
        <li><strong>PO Number:</strong> {doc.name}</li>
        <li><strong>Supplier:</strong> {doc.supplier}</li>
        <li><strong>Grand Total:</strong> {doc.grand_total}</li>
    </ul>
    <p>Please proceed with the Purchase Receipt, Purchase Invoice, and/or Payment processing.</p>
    <p>Access the document here: <a href="{doc_url}">{doc.name}</a></p>
    """

    for manager in accounts_managers:
        frappe.sendmail(recipients=[manager], subject=subject, message=message, now=True)

    frappe.msgprint(f"Accounts Manager notified about {doc.name}")
