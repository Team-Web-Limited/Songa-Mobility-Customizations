import csv

import frappe
from frappe.utils import cint, flt, get_last_day

from erpnext.assets.doctype.asset_depreciation_schedule.asset_depreciation_schedule import (
    convert_draft_asset_depr_schedules_into_active,
    make_draft_asset_depr_schedules_if_not_present,
)


def _read_asset_names(csv_path):
    with open(csv_path, newline="", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile)
        return [row["ID"].strip() for row in reader if row.get("ID") and row["ID"].strip()]


def _set_finance_book_start_dates(asset):
    for row in asset.get("finance_books"):
        row.depreciation_start_date = get_last_day(asset.available_for_use_date)


def _has_depreciation_schedule(asset_name):
    return frappe.db.exists(
        "Asset Depreciation Schedule",
        {
            "asset": asset_name,
            "docstatus": ["<", 2],
        },
    )


def _delete_draft_schedule(asset_name):
    schedules = frappe.get_all(
        "Asset Depreciation Schedule",
        filters={
            "asset": asset_name,
            "docstatus": 0,
            "status": "Draft",
        },
        pluck="name",
    )
    for schedule in schedules:
        frappe.delete_doc("Asset Depreciation Schedule", schedule, ignore_permissions=True)


@frappe.whitelist()
def repair_from_csv(csv_path, dry_run=1, limit=0):
    """Enable depreciation and create active schedules for submitted Assets in a CSV.

    Expected CSV column: ID
    """
    dry_run = cint(dry_run)
    limit = cint(limit)
    asset_names = _read_asset_names(csv_path)
    if limit:
        asset_names = asset_names[:limit]

    summary = {
        "dry_run": dry_run,
        "csv_rows": len(asset_names),
        "would_repair": 0,
        "repaired": 0,
        "skipped": [],
        "errors": [],
    }

    for asset_name in asset_names:
        try:
            if not frappe.db.exists("Asset", asset_name):
                summary["skipped"].append({"asset": asset_name, "reason": "Asset not found"})
                continue

            asset = frappe.get_doc("Asset", asset_name)
            if asset.docstatus != 1:
                summary["skipped"].append({"asset": asset_name, "reason": "Asset is not submitted"})
                continue

            if asset.calculate_depreciation or asset.get("finance_books") or _has_depreciation_schedule(asset.name):
                summary["skipped"].append(
                    {"asset": asset_name, "reason": "Depreciation already enabled or schedule exists"}
                )
                continue

            if not asset.available_for_use_date:
                summary["skipped"].append({"asset": asset_name, "reason": "Missing available-for-use date"})
                continue

            if not flt(asset.gross_purchase_amount):
                summary["skipped"].append({"asset": asset_name, "reason": "Missing gross purchase amount"})
                continue

            asset.calculate_depreciation = 1
            asset.set_missing_values()
            _set_finance_book_start_dates(asset)
            asset.validate()

            if dry_run:
                summary["would_repair"] += 1
                frappe.db.rollback()
                continue

            asset.flags.ignore_validate_update_after_submit = True
            asset.save(ignore_permissions=True)

            make_draft_asset_depr_schedules_if_not_present(asset)
            convert_draft_asset_depr_schedules_into_active(asset)

            summary["repaired"] += 1
            frappe.db.commit()

        except Exception:
            frappe.db.rollback()
            summary["errors"].append({"asset": asset_name, "traceback": frappe.get_traceback()})

    return summary


@frappe.whitelist()
def cleanup_dry_run_side_effects(csv_path):
    """Remove draft-only side effects produced by an earlier dry run of this utility."""
    asset_names = _read_asset_names(csv_path)
    summary = {
        "csv_rows": len(asset_names),
        "cleaned": 0,
        "skipped": [],
        "errors": [],
    }

    for asset_name in asset_names:
        try:
            asset = frappe.get_doc("Asset", asset_name)
            if asset.calculate_depreciation:
                summary["skipped"].append({"asset": asset_name, "reason": "Depreciation is enabled"})
                continue

            _delete_draft_schedule(asset_name)
            frappe.db.delete(
                "Asset Finance Book",
                {
                    "parent": asset_name,
                    "parenttype": "Asset",
                    "parentfield": "finance_books",
                },
            )
            summary["cleaned"] += 1
            frappe.db.commit()

        except Exception:
            frappe.db.rollback()
            summary["errors"].append({"asset": asset_name, "traceback": frappe.get_traceback()})

    return summary
