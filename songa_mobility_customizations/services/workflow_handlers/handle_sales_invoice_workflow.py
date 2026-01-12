import frappe
from frappe.utils import get_url

def handle_sales_invoice_workflow(doc, method):
    """
    Handle notifications for Sales Invoice workflow
    Triggered on_update of Sales Invoice documents
    """
    
    # 4.A. Sales Invoice Return - Pending Approval
    # Trigger: When 'is_return' is 1 AND workflow_state becomes "Return Pending Approval"
    
    if doc.is_return and doc.has_value_changed("workflow_state") and doc.workflow_state == "Return Pending Approval":
        notify_accounts_manager_return(doc)


def notify_accounts_manager_return(doc):
    # To: Accounts Manager (AM)
    # Subject: Item Return Pending Approval
    # Body: An Item Return has been submitted. Your approval is required before processing.
    
    # Get users with role "Accounts Manager"
    # Note: Requirement says "Account Manager" in workflow but standard role is usually "Accounts Manager".
    # I will check for "Accounts Manager" (plural) as it is standard, but the user's workflow had "Account Manager".
    # I'll stick to standard "Accounts Manager" or "Accounts User" if custom role isn't there, 
    # but based on previous context, "Accounts Manager" seems likely.
    
    accounts_managers = frappe.get_all("Has Role", filters={"role": "Accounts Manager", "parenttype": "User"}, pluck="parent")

    if not accounts_managers:
        frappe.log_error("No Accounts Manager found for Return Notification", "Workflow Notification")
        # Try "Account Manager" just in case custom role exists as per workflow definition
        accounts_managers = frappe.get_all("Has Role", filters={"role": "Account Manager", "parenttype": "User"}, pluck="parent")
        if not accounts_managers:
             print("No Account(s) Manager found.")
             return

    doc_url = get_url(doc.get_url())
    subject = "Item Return Pending Approval"
    
    message = f"""
    <p>An Item Return has been submitted.</p>
    <ul>
        <li><strong>Invoice:</strong> {doc.name}</li>
        <li><strong>Customer:</strong> {doc.customer}</li>
        <li><strong>Grand Total:</strong> {doc.grand_total}</li>
    </ul>
    <p>Your approval is required before processing.</p>
    <p>Access the document here: <a href="{doc_url}">{doc.name}</a></p>
    """

    for manager in accounts_managers:
        frappe.sendmail(recipients=[manager], subject=subject, message=message, now=True)

    frappe.msgprint(f"Accounts Manager notified about Return {doc.name}")
