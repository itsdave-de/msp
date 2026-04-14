"""Orchestriert einen Supplier Import Run.

Ablauf:
    1. Parser per ``profile.parser_key`` auflösen
    2. Datei lesen und via Parser in CanonicalRow-Objekte zerlegen
    3. Zeilen nach Kunde gruppieren
    4. Output-Modus je Gruppe bestimmen (Run-Override → Customer.billing_mode → Profil)
    5. DocumentBuilder aufrufen (Sales Invoice / Delivery Note)
    6. Supplier Import Line Records schreiben + Statistiken/Log füllen
"""

from __future__ import annotations

import json
import os
import traceback
from collections import defaultdict
from typing import Iterable

import frappe
from frappe.utils import now_datetime

from msp.importers.base import CanonicalRow, ParseResult
from msp.importers.builder import BuildResult, DocumentBuilder
from msp.importers.registry import resolve
from msp.importers.resolution import determine_effective_output_mode


def execute_run(run) -> dict:
	"""Einstiegspunkt. `run` ist ein :class:`Supplier Import Run`-Dokument."""
	log_buffer: list[str] = []

	def log(msg: str) -> None:
		log_buffer.append(msg)

	_set_status(run, status="Running", started_at=now_datetime())
	try:
		profile = frappe.get_doc("Supplier Import Profile", run.profile)
		if not profile.enabled:
			raise Exception(f"Profile '{profile.profile_name}' ist deaktiviert.")

		parser = resolve(profile.parser_key)
		file_path = _resolve_file_path(run.file)
		log(f"Parser: {profile.parser_key} · Datei: {file_path}")
		parse_result: ParseResult = parser.parse(file_path)
		log(f"Parsed: {len(parse_result.rows)} Zeilen "
		    f"(format_drift={parse_result.format_drift})")

		if parse_result.format_drift and not run.acknowledge_format_drift:
			raise Exception(
				"Format der Quelldatei weicht vom erwarteten Layout ab. "
				"Mit 'Abweichendes Format akzeptieren' übersteuern."
			)

		grouped = _group_rows(parse_result.rows)
		log(f"Gruppen (Kunden): {len(grouped)}")

		document_count = 0
		line_outcomes: list[dict] = []
		errors: list[str] = []

		builder = DocumentBuilder(profile)
		for customer_ref, group_rows in grouped.items():
			customer_billing_mode = _customer_billing_mode(customer_ref, profile.fallback_customer)
			effective_mode = determine_effective_output_mode(
				run.output_mode, profile.default_output_mode, customer_billing_mode,
			)
			log(f"  {customer_ref}: {len(group_rows)} Zeilen → {effective_mode}")
			try:
				group_result: BuildResult = builder.build(group_rows, output_mode=effective_mode)
				document_count += len(group_result.created_documents)
				errors.extend(group_result.errors)
				line_outcomes.extend(group_result.line_outcomes)
				for dt, name in group_result.created_documents:
					log(f"    created {dt} {name}")
			except Exception as e:
				tb = traceback.format_exc(limit=3)
				errors.append(f"Gruppe {customer_ref}: {e}")
				log(f"    ERROR: {e}\n{tb}")

		# Zeilenresultate in Supplier Import Line child table schreiben
		_persist_lines(run, line_outcomes)
		error_count = sum(1 for o in line_outcomes if o.get("status") == "Error")
		skipped_count = sum(1 for o in line_outcomes if o.get("status") == "Skipped")

		if errors or error_count:
			status = "Partial" if document_count else "Failed"
		else:
			# "Succeeded" gilt auch, wenn alle Zeilen rechtmäßig übersprungen wurden
			# (Idempotenz bei erneutem Import derselben Datei)
			status = "Succeeded"

		log(f"Ergebnis: documents={document_count} lines={len(line_outcomes)} "
		    f"errors={error_count} skipped={skipped_count} → status={status}")

		# Persistenter Statusschreib: direkt per DB (umgeht Hook-/Timestamp-Kollisionen
		# nach dem set-lines-Save, der direkt davor passiert ist).
		frappe.db.set_value("Supplier Import Run", run.name, {
			"status": status,
			"line_count": len(line_outcomes),
			"document_count": document_count,
			"error_count": error_count,
			"finished_at": now_datetime(),
			"log": "\n".join(log_buffer),
		}, update_modified=False)
		frappe.db.commit()

		return {
			"status": status,
			"document_count": document_count,
			"line_count": len(line_outcomes),
			"error_count": error_count,
			"skipped_count": skipped_count,
		}

	except Exception as e:
		log(f"FATAL: {e}\n{traceback.format_exc(limit=5)}")
		run.reload()
		run.status = "Failed"
		run.finished_at = now_datetime()
		run.log = "\n".join(log_buffer)
		run.save(ignore_permissions=True)
		frappe.db.commit()
		raise


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _set_status(run, *, status: str, started_at=None) -> None:
	run.reload()
	run.status = status
	if started_at is not None:
		run.started_at = started_at
	run.save(ignore_permissions=True)
	frappe.db.commit()


def _resolve_file_path(attached_file: str) -> str:
	"""Konvertiert den /private/files/... bzw. /files/... Pfad in den absoluten Dateisystempfad."""
	if not attached_file:
		raise Exception("Keine Datei angehängt.")
	# Absoluter Pfad, der bereits existiert → direkt nutzen
	if os.path.isabs(attached_file) and os.path.exists(attached_file):
		return attached_file
	site_path = os.path.abspath(frappe.get_site_path())
	if attached_file.startswith("/private/files/"):
		return os.path.join(site_path, "private", "files", attached_file.split("/private/files/", 1)[1])
	if attached_file.startswith("/files/"):
		return os.path.join(site_path, "public", "files", attached_file.split("/files/", 1)[1])
	raise Exception(f"Unbekannter Dateipfad: {attached_file}")


def _group_rows(rows: list[CanonicalRow]) -> dict[str, list[CanonicalRow]]:
	grouped: dict[str, list[CanonicalRow]] = defaultdict(list)
	for r in rows:
		key = r.customer_external_ref or "__NO_CUSTOMER__"
		grouped[key].append(r)
	return dict(grouped)


def _customer_billing_mode(customer_ref: str, fallback: str | None) -> str | None:
	if not customer_ref or customer_ref == "__NO_CUSTOMER__":
		customer_ref = fallback
	if not customer_ref:
		return None
	mode = frappe.db.get_value("Customer", customer_ref, "billing_mode")
	return mode


def _persist_lines(run, outcomes: Iterable[dict]) -> None:
	"""Schreibt die Import-Ergebnisse als Supplier Import Line-Zeilen in den Run."""
	run.reload()
	run.set("lines", [])
	for o in outcomes:
		row: CanonicalRow = o["row"]
		target_doctype = None
		target_name = None
		target_row = None
		if o.get("status") == "Created":
			# Aus Subscription-Event das Ziel rückgewinnen (best effort)
			event_name = o.get("event")
			if event_name:
				ev = frappe.db.get_value(
					"Supply Subscription Event", event_name,
					["sales_invoice", "sales_invoice_item_row",
					 "delivery_note", "delivery_note_item_row"],
					as_dict=True,
				)
				if ev:
					if ev.get("sales_invoice"):
						target_doctype = "Sales Invoice"
						target_name = ev["sales_invoice"]
						target_row = ev.get("sales_invoice_item_row")
					elif ev.get("delivery_note"):
						target_doctype = "Delivery Note"
						target_name = ev["delivery_note"]
						target_row = ev.get("delivery_note_item_row")

		run.append("lines", {
			"source_row": row.source_row,
			"customer": _customer_or_null(row.customer_external_ref),
			"customer_external_ref": row.customer_external_ref,
			"vendor_product_id": row.vendor_product_id,
			"qty": row.qty or 0,
			"rate": row.unit_price or row.list_price,
			"amount": row.amount,
			"period_start": row.period_start,
			"period_end": row.period_end,
			"subscription_external_id": row.subscription_external_id,
			"subscription_start": row.subscription_start,
			"billing_plan": row.billing_plan,
			"term_duration": row.term_duration,
			"booking_type": row.booking_type,
			"marketplace_ref": row.marketplace_ref,
			"order_ref": row.order_ref,
			"target_doc_type": target_doctype,
			"target_doc_name": target_name,
			"target_doc_row": target_row,
			"line_status": o.get("status") or "Pending",
			"error_message": o.get("error"),
			"raw_payload": json.dumps(row.raw, default=str, ensure_ascii=False) if row.raw else None,
		})
	run.save(ignore_permissions=True)


def _customer_or_null(ref: str | None) -> str | None:
	if not ref:
		return None
	if frappe.db.exists("Customer", ref):
		return ref
	return None
