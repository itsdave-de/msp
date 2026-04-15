"""Handler für ADNs monatliche Rechnungs-CSV (und die ZIP-verpackte Variante).

Wrap-Schicht über dem bestehenden Parser :class:`msp.importers.adn_monthly_csv.ADNMonthlyCSVParser`
und dem Orchestrator. Neue Funktionalität: ZIP-Entpacken, Sniff-basierte Auto-Erkennung,
DB-freie Vorschau.
"""

from __future__ import annotations

import os
import shutil
from typing import Iterable

import frappe

from msp.importers.adn_monthly_csv import EXPECTED_HEADER, ADNMonthlyCSVParser
from msp.importers.base import CanonicalRow
from msp.importers.handlers.base import (
	BaseFileHandler,
	ExecuteResult,
	PreviewResult,
	ProgressCallback,
)
from msp.importers.handlers.registry import register
from msp.importers.zip_unpack import is_zip_path, unpack_single_csv


@register
class ADNMonthlyCSVHandler(BaseFileHandler):
	handler_key = "adn_monthly_csv_v1"
	display_name = "ADN Monthly CSV (Microsoft-Rechnungen)"
	accepted_extensions = [".csv", ".zip"]

	# ------------------------------------------------------------------
	# Sniff
	# ------------------------------------------------------------------

	_SIGNATURE_COLUMNS = {
		"RECHNUNG", "DATUM", "ENDKUNDE", "HERSTELLERNUMMER", "POSITIONSPREIS",
		"ENDKUNDE_REFERENCE", "SUBSCRIPTION_ID_EXTERNAL",
	}
	# Spalten, die ausschließlich im Microsoft-Format vorkommen — sie heben
	# uns von Hornet-CSVs ab, die dieselbe Header-Familie nutzen.
	_DISCRIMINATOR_COLUMNS = {"BILLINGPLAN", "VERTRAGSDAUER", "MSERP", "MSERP_BILLINGPERIOD"}

	@classmethod
	def sniff(cls, sample_bytes: bytes, filename: str) -> float:
		name = (filename or "").lower()

		# ZIP: Inhalt auspacken und die erste CSV-Kopfzeile prüfen. So funktioniert
		# die Erkennung auch bei umbenannten ZIPs.
		if name.endswith(".zip"):
			first_line = cls._peek_first_line_in_zip(sample_bytes)
			if first_line is None:
				# Kein CSV im ZIP zu sehen (vielleicht verschlüsselt oder zu groß
				# im Sample) — greifen zurück auf Namens-Heuristik.
				if "rechnungen" in name or "433148" in name:
					return 0.65
				return 0.0
			return cls._score_first_line(first_line)

		if not name.endswith(".csv"):
			return 0.0

		# CSV-Header inspizieren: erste Zeile (bis 8 KiB reicht)
		try:
			head = sample_bytes.decode("utf-8", errors="replace")
		except Exception:
			return 0.0

		first_line = head.split("\n", 1)[0]
		return cls._score_first_line(first_line)

	@classmethod
	def _score_first_line(cls, first_line: str) -> float:
		first_line = (first_line or "").lstrip("\ufeff").strip()
		if not first_line:
			return 0.0
		cols = {c.strip().upper() for c in first_line.split(";")}
		matching = cls._SIGNATURE_COLUMNS & cols
		if not matching:
			return 0.0
		ratio = len(matching) / len(cls._SIGNATURE_COLUMNS)
		base = 0.4 + 0.55 * ratio  # max ≈ 0.95
		# MS-Discriminatoren heben uns sicher von Hornet ab, das nur Vertrag
		# kennt: voller Bonus, wenn alle drei Spalten da sind, sonst anteilig.
		discriminators = cls._DISCRIMINATOR_COLUMNS & cols
		if discriminators:
			base = min(1.0, base + 0.05 * len(discriminators))
		else:
			# Ohne MS-Discriminatoren ist es entweder Hornet oder ein älterer
			# MS-Export — wir reichen unter 1.0, damit Hornet entscheiden kann.
			base = min(0.7, base)
		return min(1.0, base)

	@classmethod
	def _peek_first_line_in_zip(cls, sample_bytes: bytes) -> str | None:
		"""Öffnet das ZIP in-memory und gibt die erste Zeile der enthaltenen CSV
		zurück. None, wenn keine CSV gefunden oder der Sample zu klein ist."""
		import io
		import zipfile

		if not sample_bytes:
			return None
		try:
			with zipfile.ZipFile(io.BytesIO(sample_bytes)) as z:
				csvs = [m for m in z.namelist()
				        if m.lower().endswith(".csv") and not m.endswith("/")]
				if not csvs:
					return None
				with z.open(csvs[0]) as fh:
					head = fh.read(2048).decode("utf-8", errors="replace")
					return head.split("\n", 1)[0]
		except (zipfile.BadZipFile, EOFError, KeyError):
			return None

	# ------------------------------------------------------------------
	# Preview
	# ------------------------------------------------------------------

	@classmethod
	def preview(cls, file_path: str) -> PreviewResult:
		csv_path, temp_dir = cls._resolve_csv_path(file_path)
		try:
			parser = ADNMonthlyCSVParser()
			result = parser.parse(csv_path)

			customers: set[str] = set()
			products: set[str] = set()
			period_starts: list = []
			period_ends: list = []
			credit_lines = 0
			for r in result.rows:
				if r.customer_external_ref:
					customers.add(r.customer_external_ref)
				if r.vendor_product_id:
					products.add(r.vendor_product_id)
				if r.period_start:
					period_starts.append(r.period_start)
				if r.period_end:
					period_ends.append(r.period_end)
				if (r.qty or 0) < 0 or (r.amount or 0) < 0 or r.document_type == "Gutschrift":
					credit_lines += 1

			period_label = cls._format_period_label(period_starts, period_ends)

			# Passendes Supplier Import Profile vorschlagen: aktiviertes Profil mit
			# unserem parser_key (wenn vorhanden)
			suggested_profile = frappe.db.get_value(
				"Supplier Import Profile",
				{"parser_key": cls.handler_key, "enabled": 1},
				"name",
			)

			return PreviewResult(
				supplier_profile_suggested=suggested_profile,
				line_count=len(result.rows),
				customer_count=len(customers),
				product_count=len(products),
				period_label=period_label,
				format_drift=result.format_drift,
				credit_note_lines=credit_lines,
				warnings=list(result.warnings),
				extra={"invoice_date": str(result.invoice_date) if result.invoice_date else None},
			)
		finally:
			if temp_dir:
				shutil.rmtree(temp_dir, ignore_errors=True)

	# ------------------------------------------------------------------
	# Execute
	# ------------------------------------------------------------------

	@classmethod
	def execute(cls, file_path: str, *, config: dict,
	            progress: ProgressCallback | None = None) -> ExecuteResult:
		csv_path, temp_dir = cls._resolve_csv_path(file_path)
		created_run_name: str | None = None
		try:
			# Pfad zur Website-internen „private files"-URL normalisieren —
			# der Supplier Import Run-Orchestrator erwartet das.
			site_file_url = cls._ensure_site_file_url(csv_path)

			profile_name = config.get("profile") or cls._default_profile_name()
			if not profile_name:
				return ExecuteResult(status="Failed", message="Kein Profil gefunden/konfiguriert.")

			run_doc = frappe.get_doc({
				"doctype": "Supplier Import Run",
				"profile": profile_name,
				"file": site_file_url,
				"output_mode": config.get("output_mode") or None,
				"acknowledge_format_drift": 1 if config.get("acknowledge_format_drift") else 0,
			})
			run_doc.insert(ignore_permissions=True)
			created_run_name = run_doc.name
			frappe.db.commit()

			if progress:
				progress({"phase": "starting", "run": created_run_name})

			from msp.importers.run_orchestrator import execute_run
			summary = execute_run(run_doc)

			return ExecuteResult(
				status=summary.get("status", "Failed"),
				run_name=created_run_name,
				document_count=summary.get("document_count", 0),
				line_count=summary.get("line_count", 0),
				error_count=summary.get("error_count", 0),
				skipped_count=summary.get("skipped_count", 0),
			)
		finally:
			if temp_dir:
				shutil.rmtree(temp_dir, ignore_errors=True)

	# ------------------------------------------------------------------
	# Helpers
	# ------------------------------------------------------------------

	@classmethod
	def _resolve_csv_path(cls, file_path: str) -> tuple[str, str | None]:
		"""Wenn ``file_path`` ein ZIP ist, entpacken und Pfad der CSV zurückgeben.
		Rückgabe: (csv_path, temp_dir_to_clean_up_or_None)."""
		if is_zip_path(file_path):
			temp_dir, csv_path = unpack_single_csv(file_path)
			return csv_path, temp_dir
		return file_path, None

	@staticmethod
	def _format_period_label(starts: Iterable, ends: Iterable) -> str | None:
		starts = [d for d in starts if d]
		ends = [d for d in ends if d]
		if not (starts and ends):
			return None
		min_start = min(starts)
		max_end = max(ends)
		if min_start.strftime("%Y-%m") == max_end.strftime("%Y-%m"):
			return min_start.strftime("%m.%Y")
		return f"{min_start.strftime('%m.%Y')} – {max_end.strftime('%m.%Y')}"

	@staticmethod
	def _default_profile_name() -> str | None:
		return frappe.db.get_value(
			"Supplier Import Profile",
			{"parser_key": "adn_monthly_csv_v1", "enabled": 1},
			"name",
		)

	@staticmethod
	def _ensure_site_file_url(csv_path: str) -> str:
		"""Gibt den /private/files/...-Pfad zurück, den der Orchestrator erwartet.

		Wenn die CSV außerhalb des private-files-Verzeichnisses liegt (z. B. nach
		ZIP-Entpacken in /tmp), wird eine Kopie nach private/files/ angelegt und
		dieser Pfad zurückgegeben, damit das Supplier Import Run-File-Feld
		auflösbar ist.
		"""
		import shutil as _shutil

		site_path = os.path.abspath(frappe.get_site_path())
		private_files = os.path.join(site_path, "private", "files")
		csv_abs = os.path.abspath(csv_path)
		if csv_abs.startswith(private_files + os.sep):
			relative = csv_abs[len(private_files) + 1:]
			return f"/private/files/{relative}"

		# Kopie nach private/files/ mit Original-Dateinamen
		basename = os.path.basename(csv_abs)
		target = os.path.join(private_files, basename)
		if not os.path.exists(target):
			_shutil.copyfile(csv_abs, target)
		return f"/private/files/{basename}"
