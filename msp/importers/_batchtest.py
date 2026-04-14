"""Batch-Test: mehrere ADN-CSVs chronologisch importieren."""

from __future__ import annotations

import json
import os
import frappe

from msp.importers._runner import run as run_one


CSV_SEQUENCE = [
	"/private/files/433148_Rechnungen_16_10_2025.csv",
	"/private/files/433148_Rechnungen_17_11_2025.csv",
	"/private/files/433148_Rechnungen_18_12_2025.csv",
	"/private/files/433148_Rechnungen_16_01_2026.csv",
	"/private/files/433148_Rechnungen_16_02_2026.csv",
	"/private/files/433148_Rechnungen_19_03_2026.csv",
]


def run(profile: str = "ADN Monthly CSV v1") -> str:
	results = []
	for path in CSV_SEQUENCE:
		abs_check = os.path.join(frappe.get_site_path(), "private", "files", os.path.basename(path))
		abs_check = os.path.abspath(abs_check)
		if not os.path.exists(abs_check):
			results.append({"file": path, "skipped": "file not found"})
			continue
		doc = frappe.get_doc({
			"doctype": "Supplier Import Run",
			"profile": profile,
			"file": path,
			"output_mode": "Sales Invoice",
		})
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
		summary = run_one(doc.name)
		results.append({"file": path, "run": doc.name, **summary})
	# Supply-Subscription-Bestand ermitteln
	subs_total = frappe.db.count("Supply Subscription")
	events_total = frappe.db.count("Supply Subscription Event")
	return json.dumps({
		"runs": results,
		"subscriptions_total": subs_total,
		"events_total": events_total,
	}, default=str, indent=2, ensure_ascii=False)
