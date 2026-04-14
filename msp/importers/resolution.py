"""ERP-Lookups: Customer + Item aus kanonischen Feldern auflösen."""

from __future__ import annotations

import frappe


def resolve_customer(external_ref: str | None, fallback: str | None = None) -> tuple[str | None, bool]:
	"""Gibt (customer_name, is_fallback) zurück. None wenn weder Match noch Fallback greift."""
	if external_ref:
		exists = frappe.db.exists("Customer", external_ref)
		if exists:
			return external_ref, False
		# Fallback-Match auf customer_name, falls ID nicht existiert
		match = frappe.db.get_value("Customer", {"customer_name": external_ref}, "name")
		if match:
			return match, False
	if fallback and frappe.db.exists("Customer", fallback):
		return fallback, True
	return None, False


def resolve_item(vendor_product_id: str | None) -> tuple[str | None, str]:
	"""Gibt (item_code, reason) zurück. Reason bei Nichtauflösbarkeit: 'no-match' oder 'ambiguous'."""
	if not vendor_product_id:
		return None, "no-vendor-product-id"
	matches = frappe.db.get_all(
		"Item",
		filters={"hersteller_artikel_nummer": vendor_product_id},
		fields=["name"],
		limit=2,
	)
	if not matches:
		return None, "no-match"
	if len(matches) > 1:
		return None, "ambiguous"
	return matches[0]["name"], "ok"


def determine_effective_output_mode(run_mode: str | None, profile_default: str,
                                    customer_billing_mode: str | None) -> str:
	"""Reihenfolge: expliziter Run-Override → Customer.billing_mode → Profil-Default.

	Customer.billing_mode-Werte (aus MSP-Custom-Field):
	    ASAP, Collective Bill, per Item Group, per Sales Order, remaining per Item Group
	Alles außer "ASAP" ⇒ Delivery Note (wird später gesammelt verrechnet).
	"""
	if run_mode:
		return run_mode
	if customer_billing_mode and customer_billing_mode != "ASAP":
		return "Delivery Note"
	return profile_default or "Sales Invoice"
