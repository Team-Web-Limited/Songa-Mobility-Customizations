import frappe
from frappe.utils import flt, getdate
from frappe.model.mapper import get_mapped_doc


@frappe.whitelist(allow_guest=True)
def generate_scheduled_invoices():
    """Run daily. Generate invoices for Sales Orders whose payment_schedule due dates == today."""
    today = frappe.utils.today()

    sales_orders = frappe.get_all(
        "Sales Order",
        filters={"docstatus": 1}, 
        fields=["name"]
    )

    for so in sales_orders:
        sales_order = frappe.get_doc("Sales Order", so.name)

        if not sales_order.payment_schedule:
            continue

        for term in sales_order.payment_schedule:
            if frappe.utils.formatdate(term.due_date, "yyyy-mm-dd") != today:
                continue
            # Check for duplicates
            existing = frappe.get_all(
                "Sales Invoice",
                filters={
                    "sales_order": sales_order.name,
                    "payment_terms_template": sales_order.payment_terms_template,
                    "due_date": term.due_date
                }
            )
            
            if existing:
                continue
            try:
                invoice_name = create_sales_invoice_for_term(sales_order, term)
            except Exception as e:
                frappe.log_error(f"Failed to create invoice for SO {sales_order.name}, term {term.payment_term}: {str(e)}")


def create_sales_invoice_for_term(sales_order, payment_term):
    portion = flt(payment_term.invoice_portion) / 100

    def postprocess(source, target):
        target.due_date = payment_term.due_date
        target.payment_terms_template = source.payment_terms_template

        # Adjust quantities
        for item in target.items:
            item.qty = flt(item.qty) * portion

        target.run_method("set_missing_values")
        target.run_method("calculate_taxes_and_totals")

        # Override payment schedule
        target.payment_schedule = []
        target.append("payment_schedule", {
            "payment_term": payment_term.payment_term,
            "due_date": payment_term.due_date,
            "invoice_portion": 100.0,
            "payment_amount": target.grand_total,
            "base_payment_amount": target.base_grand_total,
            "outstanding": target.grand_total,
            "base_outstanding": target.base_grand_total
        })
    try:
        si = get_mapped_doc(
            "Sales Order",
            sales_order.name,
            {
                "Sales Order": {
                    "doctype": "Sales Invoice",
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
            postprocess=postprocess
        )

        si.insert()
        si.submit()
        frappe.db.commit()
        # return si.name

    except Exception as e:
        frappe.log_error(f"Invoice creation error: {str(e)}")
        raise