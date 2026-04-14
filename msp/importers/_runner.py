"""Convenience-Helper für Bench-Tests."""

from __future__ import annotations

import frappe

from msp.importers.run_orchestrator import execute_run


def run(name: str) -> dict:
	"""Startet einen bestehenden Supplier Import Run anhand seines Namens."""
	doc = frappe.get_doc("Supplier Import Run", name)
	return execute_run(doc)
