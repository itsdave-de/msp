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

		# ZIP: Inhalt auspacken und die ersten Zeilen prüfen.
		if name.endswith(".zip"):
			lines = cls._peek_lines_in_zip(sample_bytes)
			if not lines:
				if "rechnungen" in name or "433148" in name:
					return 0.65
				return 0.0
			return cls._score_lines(lines)

		if not name.endswith(".csv"):
			return 0.0

		try:
			head = sample_bytes.decode("utf-8", errors="replace")
		except Exception:
			return 0.0

		lines = head.split("\n", 5)[:5]
		return cls._score_lines(lines)

	@classmethod
	def _score_lines(cls, lines: list[str]) -> float:
		if not lines:
			return 0.0
		header_line = (lines[0] or "").lstrip("\ufeff").strip()
		if not header_line:
			return 0.0
		header_cols = [c.strip() for c in header_line.split(";")]
		header_upper = {c.upper() for c in header_cols if c}
		matching = cls._SIGNATURE_COLUMNS & header_upper
		if not matching:
			return 0.0
		ratio = len(matching) / len(cls._SIGNATURE_COLUMNS)
		base = 0.4 + 0.55 * ratio  # max ≈ 0.95

		# Inhaltsbasierter Discriminator: ADN exportiert für Hornet dieselbe
		# Spaltenstruktur (inkl. BILLINGPLAN/MSERP), füllt die MS-spezifischen
		# Spalten dort aber nicht. Wir prüfen darum die ersten Datenzeilen auf
		# Werte in BILLINGPLAN / MSERP / VERTRAGSDAUER.
		ms_evidence = cls._has_ms_payload(header_cols, lines[1:])
		if ms_evidence:
			base = min(1.0, base + 0.15)
		else:
			# Spalten da, Werte aber leer → typisch Hornet, MS verliert.
			base = min(0.55, base)
		return min(1.0, base)

	@staticmethod
	def _has_ms_payload(header_cols: list[str], data_lines: list[str]) -> bool:
		header_upper = [c.strip().upper() for c in header_cols]
		ms_indices = [i for i, c in enumerate(header_upper)
		              if c in {"BILLINGPLAN", "MSERP", "VERTRAGSDAUER"}]
		if not ms_indices:
			return False
		for line in data_lines:
			if not line or not line.strip():
				continue
			cells = [c.strip().strip('"') for c in line.split(";")]
			if any(i < len(cells) and cells[i] for i in ms_indices):
				return True
		return False

	@classmethod
	def _peek_lines_in_zip(cls, sample_bytes: bytes) -> list[str]:
		"""Öffnet das ZIP in-memory und gibt die ersten ~5 Zeilen der enthaltenen
		CSV zurück. Leere Liste, wenn keine CSV gefunden oder Sample zu klein."""
		import io
		import zipfile

		if not sample_bytes:
			return []
		try:
			with zipfile.ZipFile(io.BytesIO(sample_bytes)) as z:
				csvs = [m for m in z.namelist()
				        if m.lower().endswith(".csv") and not m.endswith("/")]
				if not csvs:
					return []
				with z.open(csvs[0]) as fh:
					head = fh.read(8192).decode("utf-8", errors="replace")
					return head.split("\n", 5)[:5]
		except (zipfile.BadZipFile, EOFError, KeyError):
			return []

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
