"""HTTP-Endpoints für die Import-Dropzone- und Assistent-Pages.

Whitelisted Methoden:
    - analyze_file(file_url): Detect handler + DB-freie Vorschau
    - process_file(file_url, handler_key, config): Führt den Import aus
    - list_handlers(): Metadaten aller registrierten Handler (für manuelle Auswahl)
    - run_documents(run_name): erzeugte Zieldokumente eines Runs (gruppiert)
    - dashboard_stats(): Statistiken + letzte Runs für die Dropzone-Page
    - customer_context(customer_refs): pro-Kunde-Kontext (bekannt/neu, Coverage, letzter Run)
    - run_summary(run_name): aggregierte Top-Kunden-Summen eines Runs
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

	# ZIPs müssen komplett gelesen werden (Central Directory steht am Ende);
	# bei CSVs reichen 8 KiB für den Header.
	read_full = path.lower().endswith(".zip")
	with open(path, "rb") as f:
		sample = f.read() if read_full else f.read(8192)
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
		# Kein Fehler — sondern „Unmatched": Frontend soll eine manuelle
		# Handler-Zuordnung über das Dropdown anbieten. error bleibt null.
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
		SELECT l.customer, c.customer_name,
		       l.target_doc_type, l.target_doc_name,
		       COUNT(*) AS line_count, SUM(COALESCE(l.amount, 0)) AS total_amount
		FROM `tabSupplier Import Line` l
		LEFT JOIN `tabCustomer` c ON c.name = l.customer
		WHERE l.parent = %(run)s
		  AND l.line_status = 'Created'
		  AND l.target_doc_name IS NOT NULL
		  AND l.target_doc_name != ''
		GROUP BY l.customer, c.customer_name, l.target_doc_type, l.target_doc_name
		ORDER BY COALESCE(c.customer_name, l.customer)
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


@frappe.whitelist()
def dashboard_stats(months: int = 1, recent_count: int = 6) -> dict:
	"""Kennzahlen für die Dropzone-Startseite.

	Liefert eine Aktivitäts-Zusammenfassung der letzten ``months`` Monate plus
	die letzten ``recent_count`` Import-Runs inklusive Kurzstatistik.
	"""
	from_date = frappe.utils.add_months(frappe.utils.nowdate(), -int(months))

	totals_row = frappe.db.sql(
		"""
		SELECT
			COUNT(*) AS total_runs,
			SUM(CASE WHEN status = 'Succeeded' THEN 1 ELSE 0 END) AS succeeded,
			SUM(CASE WHEN status = 'Partial' THEN 1 ELSE 0 END) AS partial,
			SUM(CASE WHEN status = 'Failed' THEN 1 ELSE 0 END) AS failed,
			COALESCE(SUM(document_count), 0) AS total_documents,
			COALESCE(SUM(line_count), 0) AS total_lines,
			COALESCE(SUM(error_count), 0) AS total_errors
		FROM `tabSupplier Import Run`
		WHERE creation >= %(from_date)s
		""",
		{"from_date": from_date},
		as_dict=True,
	)
	totals = totals_row[0] if totals_row else {}

	subs_row = frappe.db.sql(
		"""SELECT COUNT(*) AS active, COALESCE(SUM(qty_current), 0) AS total_qty
		   FROM `tabSupply Subscription` WHERE status = 'Active'""",
		as_dict=True,
	)
	subs = subs_row[0] if subs_row else {}

	recent = frappe.db.sql(
		"""
		SELECT name, profile, status, creation, finished_at,
		       line_count, document_count, error_count
		FROM `tabSupplier Import Run`
		ORDER BY creation DESC
		LIMIT %(limit)s
		""",
		{"limit": int(recent_count)},
		as_dict=True,
	)

	return {
		"window": {"months": int(months), "from_date": str(from_date)},
		"totals": {
			"runs": int(totals.get("total_runs") or 0),
			"succeeded": int(totals.get("succeeded") or 0),
			"partial": int(totals.get("partial") or 0),
			"failed": int(totals.get("failed") or 0),
			"documents": int(totals.get("total_documents") or 0),
			"lines": int(totals.get("total_lines") or 0),
			"errors": int(totals.get("total_errors") or 0),
		},
		"subscriptions": {
			"active": int(subs.get("active") or 0),
			"total_qty": int(subs.get("total_qty") or 0),
		},
		"recent_runs": recent,
	}


@frappe.whitelist()
def customer_context(customer_refs: str | list) -> list[dict]:
	"""Kundenkontext für den Wizard Schritt 1.

	Für jeden Kunden-Ref: hat er Supply Subscriptions (bekannt?), hat er eine
	aktive License Coverage, wie viele Runs waren's bisher?
	"""
	if isinstance(customer_refs, str):
		customer_refs = json.loads(customer_refs or "[]")
	refs = [c for c in (customer_refs or []) if c]
	if not refs:
		return []

	subs = frappe.db.sql(
		"""
		SELECT customer, COUNT(*) AS n_subscriptions,
		       COALESCE(SUM(qty_current), 0) AS qty_total
		FROM `tabSupply Subscription`
		WHERE customer IN %(refs)s
		GROUP BY customer
		""",
		{"refs": tuple(refs)},
		as_dict=True,
	)
	subs_map = {r["customer"]: r for r in subs}

	coverage = frappe.db.sql(
		"""
		SELECT c.customer, COUNT(DISTINCT c.name) AS n_coverages,
		       COALESCE(SUM(ci.qty), 0) AS covered_qty
		FROM `tabLicense Coverage` c
		LEFT JOIN `tabLicense Coverage Item` ci ON ci.parent = c.name
		WHERE c.enabled = 1 AND c.customer IN %(refs)s
		GROUP BY c.customer
		""",
		{"refs": tuple(refs)},
		as_dict=True,
	)
	cov_map = {r["customer"]: r for r in coverage}

	customer_rows = frappe.db.sql(
		"SELECT name, customer_name FROM `tabCustomer` WHERE name IN %(refs)s",
		{"refs": tuple(refs)},
		as_dict=True,
	)
	customer_name_map = {r["name"]: r["customer_name"] for r in customer_rows}

	rows = []
	for ref in refs:
		s = subs_map.get(ref, {})
		c = cov_map.get(ref, {})
		rows.append({
			"customer": ref,
			"customer_name": customer_name_map.get(ref),
			"exists": ref in customer_name_map,
			"subscriptions": int(s.get("n_subscriptions") or 0),
			"subscription_qty": int(s.get("qty_total") or 0),
			"coverages": int(c.get("n_coverages") or 0),
			"covered_qty": int(c.get("covered_qty") or 0),
		})
	return rows


@frappe.whitelist()
def run_summary(run_name: str, top_n: int = 5) -> dict:
	"""Aggregierte Zusammenfassung eines Runs: Totals + Top-N-Kunden."""
	if not run_name:
		return {}
	totals = frappe.db.sql(
		"""
		SELECT COUNT(DISTINCT customer) AS customers,
		       COUNT(DISTINCT target_doc_name) AS documents,
		       COALESCE(SUM(CASE WHEN line_status = 'Created' THEN amount END), 0) AS total_created,
		       SUM(CASE WHEN line_status = 'Created' THEN 1 ELSE 0 END) AS lines_created,
		       SUM(CASE WHEN line_status = 'Skipped' THEN 1 ELSE 0 END) AS lines_skipped,
		       SUM(CASE WHEN line_status = 'Error' THEN 1 ELSE 0 END) AS lines_error
		FROM `tabSupplier Import Line`
		WHERE parent = %(run)s
		""",
		{"run": run_name},
		as_dict=True,
	)
	top = frappe.db.sql(
		"""
		SELECT l.customer, c.customer_name,
		       COUNT(DISTINCT l.target_doc_name) AS documents,
		       COUNT(*) AS line_count,
		       COALESCE(SUM(l.amount), 0) AS total_amount
		FROM `tabSupplier Import Line` l
		LEFT JOIN `tabCustomer` c ON c.name = l.customer
		WHERE l.parent = %(run)s AND l.line_status = 'Created'
		GROUP BY l.customer, c.customer_name
		ORDER BY total_amount DESC
		LIMIT %(limit)s
		""",
		{"run": run_name, "limit": int(top_n)},
		as_dict=True,
	)
	return {
		"totals": totals[0] if totals else {},
		"top_customers": top,
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
