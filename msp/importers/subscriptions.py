"""Upsert-Logik für Supply Subscription + Supply Subscription Event."""

from __future__ import annotations

import frappe

from msp.importers.base import CanonicalRow


def upsert_supply_subscription(row: CanonicalRow, *, customer: str,
                               supplier: str | None, vendor: str | None,
                               item: str | None) -> str | None:
	"""Legt bei Bedarf eine Supply Subscription an oder aktualisiert das Golden Record.

	Rückgabe: der Name der Supply Subscription (z. B. ``SUB-<external_id>``) oder
	None, wenn kein ``subscription_external_id`` in der Zeile steht (dann wird
	keine Subscription geführt).
	"""
	external_id = (row.subscription_external_id or "").strip()
	if not external_id:
		return None

	existing = frappe.db.get_value("Supply Subscription", {"external_id": external_id}, "name")

	payload = {
		"doctype": "Supply Subscription",
		"external_id": external_id,
		"customer": customer,
		"supplier": supplier,
		"vendor": vendor,
		"item": item,
		"vendor_product_id": row.vendor_product_id,
		"billing_plan": row.billing_plan,
		"term_duration": row.term_duration,
		"start_date": row.subscription_start,
		"status": "Active",
	}

	if existing:
		doc = frappe.get_doc("Supply Subscription", existing)
		# Nur leere/stale Felder auffüllen, keine Werte überschreiben, die vom
		# User manuell gesetzt wurden (Ausnahme: Stammdaten wie Produkt/Item).
		doc.customer = customer or doc.customer
		doc.supplier = supplier or doc.supplier
		doc.vendor = vendor or doc.vendor
		if item and not doc.item:
			doc.item = item
		doc.vendor_product_id = row.vendor_product_id or doc.vendor_product_id
		doc.billing_plan = row.billing_plan or doc.billing_plan
		doc.term_duration = row.term_duration or doc.term_duration
		if row.subscription_start and not doc.start_date:
			doc.start_date = row.subscription_start
		doc.save(ignore_permissions=True)
		return doc.name

	new = frappe.get_doc(payload)
	new.insert(ignore_permissions=True)
	return new.name


def create_event(row: CanonicalRow, *, supply_subscription: str,
                 target_doctype: str, target_name: str, target_row: str | None = None,
                 supplier_import_line_row: str | None = None) -> str:
	"""Erzeugt ein Supply Subscription Event für eine abgerechnete Periode."""
	event = frappe.get_doc({
		"doctype": "Supply Subscription Event",
		"supply_subscription": supply_subscription,
		"period_start": row.period_start,
		"period_end": row.period_end,
		"qty": int(row.qty) if row.qty else 0,
		"rate": row.unit_price or row.list_price or 0,
		"amount": row.amount or 0,
		"booking_type": row.booking_type or "Billing",
		"sales_invoice": target_name if target_doctype == "Sales Invoice" else None,
		"sales_invoice_item_row": target_row if target_doctype == "Sales Invoice" else None,
		"delivery_note": target_name if target_doctype == "Delivery Note" else None,
		"delivery_note_item_row": target_row if target_doctype == "Delivery Note" else None,
		"supplier_import_line": supplier_import_line_row,
	})
	event.insert(ignore_permissions=True)
	return event.name


def event_exists_for_period(subscription_external_id: str, period_start,
                            period_end) -> bool:
	"""Deduplizierungs-Check: Wurde diese Subscription+Period bereits importiert?"""
	if not (subscription_external_id and period_start and period_end):
		return False
	subscription_name = frappe.db.get_value(
		"Supply Subscription",
		{"external_id": subscription_external_id}, "name",
	)
	if not subscription_name:
		return False
	return bool(frappe.db.exists(
		"Supply Subscription Event",
		{
			"supply_subscription": subscription_name,
			"period_start": period_start,
			"period_end": period_end,
		},
	))
