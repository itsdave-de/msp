"""Cleanup-Helper: löscht alles, was der neue Importer erzeugt hat (nur Test!)."""

from __future__ import annotations

import frappe


def cleanup_all():
	"""Entfernt sämtliche vom neuen Importer angelegten Daten (Test-System only!)."""
	if "test" not in frappe.local.conf.get("db_name", "") and not frappe.local.conf.get("developer_mode"):
		raise Exception("Cleanup nur in Entwicklungs-/Test-Umgebungen erlaubt.")

	# 1. Supply Subscription Events → 2. Supply Subscriptions
	frappe.db.sql("DELETE FROM `tabSupply Subscription Event`")
	frappe.db.sql("DELETE FROM `tabSupply Subscription`")

	# 3. Supplier Import Lines (child) → 4. Runs
	frappe.db.sql("DELETE FROM `tabSupplier Import Line`")
	frappe.db.sql("DELETE FROM `tabSupplier Import Run`")

	# 5. Draft Sales Invoices, die über den neuen Importer erzeugt wurden
	#    (Heuristik: aus Supplier Import Line.target_doc_name wären sie referenziert
	#     gewesen — da wir die Lines gerade gelöscht haben, nehmen wir stattdessen
	#     alle Draft-SIs mit unserem supply_subscription-Link als Anzeichen.)
	draft_sis = frappe.db.sql_list("""
		SELECT DISTINCT parent FROM `tabSales Invoice Item`
		WHERE supply_subscription IS NOT NULL AND supply_subscription != ''
	""")
	for name in draft_sis:
		doc = frappe.get_doc("Sales Invoice", name)
		if doc.docstatus == 0:
			doc.delete()

	# 6. Draft Delivery Notes entsprechend
	draft_dns = frappe.db.sql_list("""
		SELECT DISTINCT parent FROM `tabDelivery Note Item`
		WHERE supply_subscription IS NOT NULL AND supply_subscription != ''
	""")
	for name in draft_dns:
		doc = frappe.get_doc("Delivery Note", name)
		if doc.docstatus == 0:
			doc.delete()

	frappe.db.commit()
	return {
		"supply_subscriptions_deleted": True,
		"import_runs_deleted": True,
		"sales_invoices_cleaned": len(draft_sis),
		"delivery_notes_cleaned": len(draft_dns),
	}
