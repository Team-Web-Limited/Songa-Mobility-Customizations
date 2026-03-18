import frappe
from frappe import _
from erpnext.accounts.doctype.budget.budget import Budget, DuplicateBudgetError

class CustomBudget(Budget):

    def validate(self):
        # Override the standard validate to handle custom fields correctly
        budget_against_field = frappe.scrub(self.budget_against)
        if self.budget_against == "Department":
            budget_against_field = "department"
        elif self.budget_against == "Branch":
            budget_against_field = "branch"
            
        if not self.get(budget_against_field):
            frappe.throw(_("{0} is mandatory").format(self.budget_against))
            
        self.custom_validate_duplicate()
        self.validate_accounts()
        self.set_null_value()
        self.validate_applicable_for()

    def custom_validate_duplicate(self):
        budget_against_field = frappe.scrub(self.budget_against)
        if self.budget_against == "Department":
            budget_against_field = "department"
        elif self.budget_against == "Branch":
            budget_against_field = "branch"
            
        budget_against = self.get(budget_against_field)
        
        accounts = [d.account for d in self.accounts] or []
        if not accounts:
            return
            
        existing_budget = frappe.db.sql(
            """
            select
                b.name, ba.account from `tabBudget` b, `tabBudget Account` ba
            where
                ba.parent = b.name and b.docstatus < 2 and b.company = {} and b.{}={} and
                b.fiscal_year={} and b.name != {} and ba.account in ({}) """.format(
                "%s", budget_against_field, "%s", "%s", "%s", ",".join(["%s"] * len(accounts))
            ),
            (self.company, budget_against, self.fiscal_year, self.name or "", *tuple(accounts)),
            as_dict=1,
        )

        for d in existing_budget:
            frappe.throw(
                _(
                    "Another Budget record '{0}' already exists against {1} '{2}' and account '{3}' for fiscal year {4}"
                ).format(d.name, self.budget_against, budget_against, d.account, self.fiscal_year),
                DuplicateBudgetError,
            )

    def set_null_value(self):
        if self.budget_against == "Cost Center":
            self.project = None
            self.department = None
            self.branch = None
        elif self.budget_against == "Project":
            self.cost_center = None
            self.department = None
            self.branch = None
        elif self.budget_against == "Department":
            self.cost_center = None
            self.project = None
            self.branch = None
        elif self.budget_against == "Branch":
            self.cost_center = None
            self.project = None
            self.department = None