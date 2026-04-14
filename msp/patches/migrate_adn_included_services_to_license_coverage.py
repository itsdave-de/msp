"""Migriert bestehende `ADN Included Services` + Items in den lieferantenneutralen
`License Coverage` / `License Coverage Item`.

Idempotent — bereits migrierte Records werden übersprungen (Markierung per Notes-Feld).
"""

from __future__ import annotations

import frappe

MIGRATION_MARKER = "[migrated from ADN Included Services]"


def execute():
	if not frappe.db.exists("DocType", "ADN Included Services"):
		# adnconnect nicht installiert — nichts zu tun
		return

	sources = frappe.get_all(
		"ADN Included Services",
		fields=["name", "customer", "inc_serv"],
	)
	migrated = 0
	for src in sources:
		existing = frappe.db.get_all(
			"License Coverage",
			filters={"customer": src["customer"]},
			fields=["name", "notes"],
		)
		if any(MIGRATION_MARKER in (e.get("notes") or "") for e in existing):
			continue

		items = frappe.get_all(
			"ADN Included Services Item",
			filters={"parent": src["name"]},
			fields=["item_code", "qty", "description"],
			order_by="idx",
		)
		if not items:
			continue

		cov = frappe.new_doc("License Coverage")
		cov.customer = src["customer"]
		cov.enabled = 1
		cov.notes = _compose_notes(src.get("inc_serv"))
		for it in items:
			cov.append("coverage_items", {
				"item": it["item_code"],
				"qty": int(it["qty"] or 0),
				"note": (it.get("description") or "").strip() or None,
			})
		cov.insert(ignore_permissions=True)
		migrated += 1

	if migrated:
		frappe.db.commit()
		print(f"License Coverage: {migrated} Records aus ADN Included Services übernommen.")


def _compose_notes(source_inc_serv: str | None) -> str:
	lines = [f"<p><em>{MIGRATION_MARKER}</em></p>"]
	if source_inc_serv:
		lines.append(source_inc_serv.strip())
	return "\n".join(lines)
