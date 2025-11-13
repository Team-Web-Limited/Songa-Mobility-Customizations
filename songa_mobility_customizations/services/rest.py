import frappe
from frappe import _
from frappe.utils import flt, getdate
from frappe.model.mapper import get_mapped_doc


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



def create_sales_invoices_from_payment_terms(doc, method):
    """
    Create Sales Invoices based on Payment Terms when Sales Order is submitted
    """
    if doc.docstatus != 1:
        return
    
    if not doc.payment_schedule:
        frappe.msgprint("No payment terms found. No invoices created.")
        return
    
    for payment_term in doc.payment_schedule:
        create_sales_invoice_for_term(doc, payment_term)

def create_sales_invoice_for_term(sales_order, payment_term):
    """
    Create Sales Invoice using Frappe's mapper for proper amount handling
    """
    try:
        portion = flt(payment_term.invoice_portion) / 100
        
        def postprocess(source, target):
            target.due_date = payment_term.due_date
            target.payment_terms_template = source.payment_terms_template
            
            # Adjust item quantities proportionally
            for item in target.items:
                item.qty = flt(item.qty) * portion
            
            # Let Frappe calculate the amounts automatically
            target.run_method("set_missing_values")
            target.run_method("calculate_taxes_and_totals")
            
            # Clear existing payment schedule and add only this term
            target.payment_schedule = []
            target.append("payment_schedule", {
                "payment_term": payment_term.payment_term,
                "due_date": payment_term.due_date,
                "invoice_portion": 100.0,  # This invoice represents 100% of its portion
                "payment_amount": target.grand_total,
                "base_payment_amount": target.base_grand_total,
                "outstanding": target.grand_total,
                "base_outstanding": target.base_grand_total
            })
        
        sales_invoice = get_mapped_doc(
            "Sales Order",
            sales_order.name,
            {
                "Sales Order": {
                    "doctype": "Sales Invoice",
                    "field_map": {
                        "order_type": "order_type",
                        "customer": "customer",
                        "company": "company",
                        "currency": "currency"
                    }
                },
                "Sales Order Item": {
                    "doctype": "Sales Invoice Item",
                    "field_map": {
                        "name": "sales_order_item",
                        "parent": "sales_order",
                    },
                    "condition": lambda doc: doc.qty > 0
                }
            },
            target_doc=None,
            postprocess=postprocess
        )
        
        sales_invoice.insert()
        frappe.msgprint(f"Created Sales Invoice: {sales_invoice.name} for {payment_term.payment_term}")
        
    except Exception as e:
        frappe.log_error(f"Error creating Sales Invoice: {str(e)}")
        frappe.throw(f"Failed to create Sales Invoice: {str(e)}")