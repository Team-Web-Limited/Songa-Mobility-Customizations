import frappe
from frappe import _
from frappe.utils import flt, getdate
from frappe.model.mapper import get_mapped_doc
from frappe.model.document import Document
import json



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
  
    if doc.docstatus != 1:
        return
    
    if not doc.payment_schedule:
        frappe.msgprint("No payment terms found. No invoices created.")
        return
    
    for payment_term in doc.payment_schedule:
        create_sales_invoice_for_term(doc, payment_term)

def create_sales_invoice_for_term(sales_order, payment_term):
   
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



# Landed Cost Voucher Fecth Items Scripts
@frappe.whitelist()
def fetch_linked_charges(purchase_receipts):
   
    try:
        frappe.logger().debug(f"fetch_linked_charges called with: {purchase_receipts}")
        
        if isinstance(purchase_receipts, str):
            purchase_receipts = frappe.parse_json(purchase_receipts)
        
        frappe.logger().debug(f"Parsed purchase_receipts: {purchase_receipts}")
        
        if not purchase_receipts:
            frappe.throw(_("No purchase receipts provided"))
        
        # Filter out any None or empty values
        purchase_receipts = [pr for pr in purchase_receipts if pr]
        
        if not purchase_receipts:
            frappe.throw(_("No valid purchase receipts provided"))
            
        frappe.logger().debug(f"Filtered purchase_receipts: {purchase_receipts}")
        
        additional_charges = []
        
        for pr_name in purchase_receipts:
            frappe.logger().debug(f"Processing purchase receipt: {pr_name}")
            
            if not pr_name:
                continue
                
            if not frappe.db.exists('Purchase Receipt', pr_name):
                frappe.logger().debug(f"Purchase Receipt {pr_name} does not exist")
                continue
                
            # Get main purchase receipt
            main_pr = frappe.get_doc('Purchase Receipt', pr_name)
            frappe.logger().debug(f"Found main PR: {main_pr.name}")
            
            # Find all linked purchase receipts (additional charges) using your custom field
            linked_receipts = frappe.get_all('Purchase Receipt',
                filters={
                    'custom_reference_purchase_receipt': main_pr.name,
                    'docstatus': 1  
                },
                fields=['name']
            )
            
            frappe.logger().debug(f"Found {len(linked_receipts)} linked receipts for {main_pr.name}")
            
            # Add items from linked receipts (additional charges) ONLY
            for linked_pr in linked_receipts:
                linked_doc = frappe.get_doc('Purchase Receipt', linked_pr.name)
                frappe.logger().debug(f"Processing linked PR: {linked_doc.name} with {len(linked_doc.items)} items")
                
                for item in linked_doc.items:
                    additional_charges.append({
                        'item_code': item.item_code,
                        'item_name': item.item_name,
                        'description': item.description or item.item_name or item.item_code,
                        'qty': item.qty,
                        'rate': item.rate,
                        'amount': item.amount,
                        'receipt_document_type': 'Purchase Receipt',
                        'receipt_document': linked_doc.name,
                        'purchase_receipt_item': item.name,
                        'expense_account': item.expense_account,
                        'is_additional_charge': 1,
                        'source_receipt': linked_doc.name
                    })
        
        frappe.logger().debug(f"Total additional charges found: {len(additional_charges)}")
        return additional_charges
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), _('Error fetching linked charges'))
        frappe.throw(_('Failed to fetch linked charges: {0}').format(str(e)))