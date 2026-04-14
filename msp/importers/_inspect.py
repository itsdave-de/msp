"""Inspect-Helpers für die Entwicklung."""

from __future__ import annotations

import json
import frappe


def inspect_run(name: str, show_lines: int = 5) -> str:
	run = frappe.get_doc("Supplier Import Run", name)
	lines = run.lines[:show_lines]
	return json.dumps({
		"status": run.status,
		"file": run.file,
		"line_count": run.line_count,
		"document_count": run.document_count,
		"error_count": run.error_count,
		"log_tail": (run.log or "")[-2000:],
		"first_lines": [
			{
				"customer_external_ref": l.customer_external_ref,
				"customer": l.customer,
				"vendor_product_id": l.vendor_product_id,
				"qty": l.qty,
				"amount": l.amount,
				"line_status": l.line_status,
				"error_message": l.error_message,
				"target": f"{l.target_doc_type or ''} {l.target_doc_name or ''}",
			}
			for l in lines
		],
	}, default=str, ensure_ascii=False, indent=2)
