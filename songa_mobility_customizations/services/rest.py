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



@frappe.whitelist()
def bulk_delete_purchase_invoices(names):
    if isinstance(names, str):
        names = json.loads(names)
    
    deleted = []
    skipped = []
    
    for name in names:
        docstatus = frappe.db.get_value("Purchase Invoice", name, "docstatus")
        if docstatus == 0:
            try:
                frappe.delete_doc("Purchase Invoice", name)
                deleted.append(name)
            except Exception as e:
                frappe.log_error(f"Error deleting Purchase Invoice {name}: {str(e)}")
                skipped.append(name)
        else:
            skipped.append(name)
            
    return {
        "deleted": deleted,
        "skipped": skipped
    }


@frappe.whitelist()
def bulk_pay_purchase_invoices(names, payment_details):
    """Create Payment Entries for eligible Purchase Invoices.

    By default, invoices are grouped by supplier and compatible accounting
    dimensions. Set ``group_by_supplier`` to false to create one entry per
    invoice. Each group is processed independently with a savepoint.
    """
    if isinstance(names, str):
        names = frappe.parse_json(names)
    if isinstance(payment_details, str):
        payment_details = frappe.parse_json(payment_details)

    if not names:
        frappe.throw(_("Please select at least one Purchase Invoice."))
    if not isinstance(payment_details, dict):
        frappe.throw(_("Payment details are required."))

    posting_date = payment_details.get("posting_date") or frappe.utils.nowdate()
    paid_from = payment_details.get("paid_from")
    mode_of_payment = payment_details.get("mode_of_payment")
    reference_no = payment_details.get("reference_no")
    reference_date = payment_details.get("reference_date")
    submit_entries = frappe.utils.cint(payment_details.get("submit_entries"))
    group_by_supplier = frappe.utils.cint(payment_details.get("group_by_supplier", 1))

    if not paid_from:
        frappe.throw(_("Please select a Bank/Cash Account."))
    if not mode_of_payment:
        frappe.throw(_("Please select a Mode of Payment."))
    account_type = frappe.db.get_value(
        "Account", {"name": paid_from, "is_group": 0}, "account_type"
    )
    if account_type not in ("Bank", "Cash"):
        frappe.throw(_("The selected Bank/Cash Account is invalid."))

    created = []
    skipped = []
    failed = []
    groups = {}

    for name in dict.fromkeys(names):
        try:
            invoice = frappe.get_doc("Purchase Invoice", name)
            invoice.check_permission("read")

            if invoice.docstatus != 1:
                skipped.append({"invoice": name, "reason": _("Invoice is not submitted.")})
                continue

            if invoice.invoice_is_blocked():
                skipped.append({"invoice": name, "reason": _("Invoice is on hold.")})
                continue

            outstanding = frappe.utils.flt(invoice.outstanding_amount)
            if outstanding <= 0:
                skipped.append({"invoice": name, "reason": _("Invoice has no outstanding amount.")})
                continue

            existing = frappe.db.sql(
                """
                select per.parent
                from `tabPayment Entry Reference` per
                inner join `tabPayment Entry` pe on pe.name = per.parent
                where per.reference_doctype = 'Purchase Invoice'
                    and per.reference_name = %s
                    and per.allocated_amount > 0
                    and pe.docstatus < 2
                limit 1
                """,
                name,
            )
            if existing:
                skipped.append({
                    "invoice": name,
                    "reason": _("Invoice already has an active Payment Entry ({0}).").format(existing[0][0]),
                })
                continue

            pe = frappe.call(
                "erpnext.accounts.doctype.payment_entry.payment_entry.get_payment_entry",
                dt="Purchase Invoice",
                dn=name,
                party_amount=outstanding,
                bank_account=paid_from,
                reference_date=reference_date,
            )
            pe.posting_date = posting_date
            pe.reference_date = reference_date or posting_date
            pe.reference_no = reference_no
            pe.mode_of_payment = mode_of_payment

            # These fields are custom in this installation and are used by
            # the Payment Entry form to retain supplier accounting dimensions.
            if invoice.meta.has_field("branch") and pe.meta.has_field("branch"):
                pe.branch = invoice.get("branch")
            if invoice.meta.has_field("cost_center") and pe.meta.has_field("cost_center"):
                pe.cost_center = invoice.get("cost_center") or pe.cost_center

            branch = invoice.get("branch") or None
            cost_center = invoice.get("cost_center") or pe.cost_center or None

            # Payment-specific deductions/taxes (for example early-payment
            # discounts or withholding) must remain tied to their source
            # invoice, so do not combine those entries.
            can_group = group_by_supplier and not pe.deductions and not pe.taxes
            if can_group:
                group_key = (
                    invoice.supplier,
                    invoice.company,
                    invoice.currency,
                    invoice.credit_to,
                    pe.paid_from_account_currency,
                    branch,
                    cost_center,
                )
            else:
                group_key = (name,)

            group = groups.setdefault(group_key, {"template": pe, "invoices": []})
            group["invoices"].append({"invoice": invoice, "payment_entry": pe})
        except Exception as exc:
            failed.append({"invoice": name, "reason": frappe.safe_decode(str(exc))})

    for group in groups.values():
        savepoint = "bulk_payment_" + frappe.generate_hash(length=8)
        frappe.db.savepoint(savepoint)
        try:
            template = group["template"]
            entries = group["invoices"]
            references = []
            paid_amount = 0
            received_amount = 0

            for entry in entries:
                source_pe = entry["payment_entry"]
                paid_amount += frappe.utils.flt(source_pe.paid_amount)
                received_amount += frappe.utils.flt(source_pe.received_amount)
                references.extend(source_pe.references)

            template.set("references", [])
            for reference in references:
                template.append(
                    "references",
                    {
                        "reference_doctype": reference.reference_doctype,
                        "reference_name": reference.reference_name,
                        "due_date": reference.due_date,
                        "bill_no": reference.bill_no,
                        "total_amount": reference.total_amount,
                        "outstanding_amount": reference.outstanding_amount,
                        "allocated_amount": reference.allocated_amount,
                        "payment_term": reference.payment_term,
                    },
                )

            template.paid_amount = paid_amount
            template.received_amount = received_amount
            template.set_amounts()
            template.insert()
            if submit_entries:
                template.submit()

            for entry in entries:
                created.append({
                    "invoice": entry["invoice"].name,
                    "payment_entry": template.name,
                    "status": "Submitted" if submit_entries else "Draft",
                })
        except Exception as exc:
            frappe.db.rollback(save_point=savepoint)
            for entry in group["invoices"]:
                failed.append({
                    "invoice": entry["invoice"].name,
                    "reason": frappe.safe_decode(str(exc)),
                })

    return {"created": created, "skipped": skipped, "failed": failed}
