import frappe
from frappe import _

def validate_purchase_order(doc, method):
    items_requiring_attachments = []
    
    for item in doc.items:
        if frappe.db.get_value("Item", item.item_code, "custom_has_attachments"):
            items_requiring_attachments.append(item.item_code)
    
    if items_requiring_attachments:
        attachments = frappe.get_all("File", {
            "attached_to_name": doc.name,
            "attached_to_doctype": "Purchase Order"
        })
        
        if not attachments:
            frappe.throw(_(
                "The following items require attachments: {0}. "
                "Please attach required documents before saving."
            ).format(", ".join(items_requiring_attachments)))

