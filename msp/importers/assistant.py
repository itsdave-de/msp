"""HTTP-Endpoints für die Import-Dropzone-Page.

Drei whitelisted Methoden:
    - analyze_file(file_url): Detect handler + DB-freie Vorschau
    - process_file(file_url, handler_key, config): Führt den Import aus
    - list_handlers(): Metadaten aller registrierten Handler (für manuelle Auswahl)
"""

from __future__ import annotations

import json
import os
import traceback

import frappe

from msp.importers.handlers.registry import all_handlers, detect_best_handler, get as get_handler


@frappe.whitelist()
def list_handlers() -> list[dict]:
	"""Metadaten aller registrierten Handler — für manuelle Format-Zuordnung in der UI."""
	out = []
	for cls in all_handlers():
		out.append({
			"handler_key": cls.handler_key,
			"display_name": cls.display_name,
			"accepted_extensions": cls.accepted_extensions,
			"wizard_route": cls.wizard_route,
		})
	return out


@frappe.whitelist()
def analyze_file(file_url: str) -> dict:
	"""Erkennt das Format einer hochgeladenen Datei und liefert eine DB-freie Vorschau.

	``file_url`` ist die `/private/files/…`- oder `/files/…`-URL des File-Doctypes.
	"""
	path = _resolve_file_url(file_url)
	if not os.path.exists(path):
		frappe.throw(f"Datei nicht gefunden: {file_url}")

	with open(path, "rb") as f:
		sample = f.read(8192)
	filename = os.path.basename(path)

	best_cls, confidence, scores = detect_best_handler(sample, filename)
	result = {
		"file_url": file_url,
		"filename": filename,
		"size": os.path.getsize(path),
		"confidence": confidence,
		"scores": scores,
		"handler_key": None,
		"display_name": None,
		"wizard_route": None,
		"preview": None,
		"error": None,
	}
	if best_cls is None:
		result["error"] = "Kein passender Handler — Format nicht erkannt."
		return result

	result["handler_key"] = best_cls.handler_key
	result["display_name"] = best_cls.display_name
	result["wizard_route"] = best_cls.wizard_route

	try:
		preview = best_cls.preview(path)
	except Exception as e:
		result["error"] = f"Vorschau fehlgeschlagen: {e}"
		result["preview_traceback"] = traceback.format_exc(limit=5)
		return result

	result["preview"] = {
		"line_count": preview.line_count,
		"customer_count": preview.customer_count,
		"product_count": preview.product_count,
		"period_label": preview.period_label,
		"format_drift": preview.format_drift,
		"credit_note_lines": preview.credit_note_lines,
		"warnings": preview.warnings,
		"suggested_profile": preview.supplier_profile_suggested,
		"extra": preview.extra,
	}
	return result


@frappe.whitelist()
def run_documents(run_name: str) -> list[dict]:
	"""Gibt die pro Supplier Import Run erzeugten Zieldokumente zurück —
	gruppiert pro (target_doc_type, target_doc_name), mit Zeilen-Anzahl und
	Summe. Wird vom Import-Assistent-Wizard benötigt, weil
	``frappe.client.get_list`` auf Child-Doctypes die `fields` ignoriert."""
	if not run_name:
		return []
	rows = frappe.db.sql(
		"""
		SELECT customer, target_doc_type, target_doc_name,
		       COUNT(*) AS line_count, SUM(COALESCE(amount, 0)) AS total_amount
		FROM `tabSupplier Import Line`
		WHERE parent = %(run)s
		  AND line_status = 'Created'
		  AND target_doc_name IS NOT NULL
		  AND target_doc_name != ''
		GROUP BY customer, target_doc_type, target_doc_name
		ORDER BY customer
		""",
		{"run": run_name},
		as_dict=True,
	)
	return rows


@frappe.whitelist()
def process_file(file_url: str, handler_key: str,
                 config: str | dict | None = None) -> dict:
	"""Führt den Import mit dem gewählten Handler durch.

	``config`` kann als JSON-String (vom Browser) oder als dict übergeben werden.
	Typische Felder: profile, output_mode, acknowledge_format_drift.
	"""
	if isinstance(config, str):
		try:
			config = json.loads(config or "{}")
		except Exception:
			frappe.throw("Ungültige config — muss valides JSON sein.")
	config = config or {}

	handler_cls = get_handler(handler_key)
	path = _resolve_file_url(file_url)
	if not os.path.exists(path):
		frappe.throw(f"Datei nicht gefunden: {file_url}")

	result = handler_cls.execute(path, config=config)
	return {
		"status": result.status,
		"run_name": result.run_name,
		"document_count": result.document_count,
		"line_count": result.line_count,
		"error_count": result.error_count,
		"skipped_count": result.skipped_count,
		"message": result.message,
	}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_file_url(file_url: str) -> str:
	"""Wandelt `/private/files/...` oder `/files/...` in einen absoluten Dateipfad."""
	if not file_url:
		frappe.throw("Keine Datei-URL übergeben.")
	if os.path.isabs(file_url) and os.path.exists(file_url):
		return file_url
	site_path = os.path.abspath(frappe.get_site_path())
	if file_url.startswith("/private/files/"):
		return os.path.join(site_path, "private", "files", file_url.split("/private/files/", 1)[1])
	if file_url.startswith("/files/"):
		return os.path.join(site_path, "public", "files", file_url.split("/files/", 1)[1])
	frappe.throw(f"Unbekanntes Dateipfad-Format: {file_url}")
