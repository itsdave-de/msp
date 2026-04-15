"""FileHandler für ADN-Hornet-Abrechnungen.

Wrap-Schicht über :class:`msp.importers.adn_hornet_csv.ADNHornetCSVParser`.
Nutzt denselben Run-Orchestrator wie der Microsoft-Handler — Hornet-spezifisch
sind nur Sniff (Spalten-Heuristik + Filename-Hint) und der Parser.
"""

from __future__ import annotations

import os
import shutil
from typing import Iterable

import frappe

from msp.importers.adn_hornet_csv import EXPECTED_HEADER, ADNHornetCSVParser
from msp.importers.handlers.base import (
	BaseFileHandler,
	ExecuteResult,
	PreviewResult,
	ProgressCallback,
)
from msp.importers.handlers.registry import register
from msp.importers.zip_unpack import is_zip_path, unpack_single_csv


@register
class ADNHornetCSVHandler(BaseFileHandler):
	handler_key = "adn_hornet_csv_v1"
	display_name = "ADN Hornet CSV (Hornetsecurity)"
	accepted_extensions = [".csv", ".zip"]

	# ------------------------------------------------------------------
	# Sniff
	# ------------------------------------------------------------------

	# Pflicht-Spalten zur Hornet-Erkennung; gleiche Familie wie Microsoft,
	# aber {VERTRAG, WARTUNGSBEGINN, WARTUNGSENDE} sind bei Hornet stets
	# inhaltlich gefüllt.
	_SIGNATURE_COLUMNS = {
		"RECHNUNG", "DATUM", "ENDKUNDE", "HERSTELLERNUMMER",
		"ENDKUNDE_REFERENCE", "VERTRAG",
		"WARTUNGSBEGINN", "WARTUNGSENDE",
	}
	# Spalten, die exklusiv im Microsoft-Format vorkommen — sind sie da,
	# spricht das gegen Hornet.
	_NEGATIVE_COLUMNS = {"BILLINGPLAN", "VERTRAGSDAUER", "MSERP", "ADDITIONALID"}

	@classmethod
	def sniff(cls, sample_bytes: bytes, filename: str) -> float:
		name = (filename or "").lower()

		if name.endswith(".zip"):
			first_line = cls._peek_first_line_in_zip(sample_bytes)
			if first_line is None:
				if "hornet" in name:
					return 0.65
				return 0.0
			score = cls._score_first_line(first_line)
			if "hornet" in name:
				score = min(1.0, score + 0.1)
			return score

		if not name.endswith(".csv"):
			return 0.0

		try:
			head = sample_bytes.decode("utf-8", errors="replace")
		except Exception:
			return 0.0

		first_line = head.split("\n", 1)[0]
		score = cls._score_first_line(first_line)
		if "hornet" in name:
			score = min(1.0, score + 0.1)
		return score

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
		# Hard penalty wenn MS-Discriminatoren da sind: dann ist's Microsoft.
		if cls._NEGATIVE_COLUMNS & cols:
			base = base * 0.4
		return min(1.0, base)

	@classmethod
	def _peek_first_line_in_zip(cls, sample_bytes: bytes) -> str | None:
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
			parser = ADNHornetCSVParser()
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
	# Helpers — kongruent zur Microsoft-Variante, damit sich beide Handler
	# operativ identisch anfühlen.
	# ------------------------------------------------------------------

	@classmethod
	def _resolve_csv_path(cls, file_path: str) -> tuple[str, str | None]:
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
			{"parser_key": "adn_hornet_csv_v1", "enabled": 1},
			"name",
		)

	@staticmethod
	def _ensure_site_file_url(csv_path: str) -> str:
		import shutil as _shutil

		site_path = os.path.abspath(frappe.get_site_path())
		private_files = os.path.join(site_path, "private", "files")
		csv_abs = os.path.abspath(csv_path)
		if csv_abs.startswith(private_files + os.sep):
			relative = csv_abs[len(private_files) + 1:]
			return f"/private/files/{relative}"

		basename = os.path.basename(csv_abs)
		target = os.path.join(private_files, basename)
		if not os.path.exists(target):
			_shutil.copyfile(csv_abs, target)
		return f"/private/files/{basename}"
