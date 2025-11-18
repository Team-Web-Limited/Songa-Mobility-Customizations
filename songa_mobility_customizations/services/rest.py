import frappe
from frappe import _

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




@frappe.whitelist()
def get_stock_info(item_code, warehouse):
    # Ensure valid args
    if not item_code or not warehouse:
        return {"error": "Item code and warehouse are required"}

    # 1️⃣ Get stock info for selected warehouse
    bin_data = frappe.db.get_value(
        "Bin",
        {"item_code": item_code, "warehouse": warehouse},
        ["actual_qty", "valuation_rate"],
        as_dict=True
    )

    # Handle case when NO Bin record exists for that warehouse
    if not bin_data:
        bin_data = {"actual_qty": 0, "valuation_rate": 0}

    available_qty = bin_data.get("actual_qty", 0) or 0
    valuation_rate = bin_data.get("valuation_rate", 0) or 0

    # 2️⃣ Find other warehouses with stock (excluding the selected one)
    other_wh = []
    if available_qty <= 0:
        other_wh = frappe.db.get_list(
            "Bin",
            fields=["warehouse", "actual_qty"],
            filters={
                "item_code": item_code,
                "actual_qty": [">", 0],
                "warehouse": ["!=", warehouse]
            },
            order_by="actual_qty desc"
        )

    return {
        "available_qty": available_qty,
        "valuation_rate": valuation_rate,
        "total_value": available_qty * valuation_rate,
        "other_warehouses": other_wh
    }

