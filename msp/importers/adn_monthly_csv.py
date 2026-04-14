"""Parser für die monatlichen CSV-Abrechnungsdateien der ADN Distribution.

Format: Semikolon-getrennt, Zeichenkodierung UTF-8 (BOM erlaubt), deutsche
Dezimalschreibweise. Jede Zeile ist **eine** Rechnungsposition; Kopfdaten
(RECHNUNG, DATUM, …) sind pro Zeile redundant wiederholt.

Registrierung über :func:`msp.importers.registry.register`.
"""

from __future__ import annotations

import csv
import io
from typing import Iterable

from msp.importers.base import (
	BaseSupplierParser,
	CanonicalRow,
	ParseResult,
	normalize_billing_plan,
	normalize_booking_type,
	normalize_term_duration,
	parse_german_date,
	parse_german_decimal,
)
from msp.importers.registry import register


EXPECTED_HEADER = [
	"RECHNUNG", "DATUM", "KUNDENNR", "DEBITORKONTO", "SACHBEARBEITER",
	"LIEFERSCHEIN", "LIEFERSCHEINDATUM", "USTID",
	"RE_FIRMA", "RE_ADRESSE", "RE_PLZ", "RE_ORT", "RE_LAND",
	"LI_FIRMA", "LI_STRASSE", "LI_PLZ", "LI_ORT", "LI_LAND",
	"HA_FIRMA", "HA_STRASSE", "HA_PLZ", "HA_ORT", "HA_LAND",
	"WARENWERT", "MWST", "GESAMTBETRAG", "NETTOZAHLBARBIS",
	"LIEFERBEDINGUNGEN", "ZAHLUNGSBEDINGUNG",
	"ENDKUNDE", "POSITION", "ARTIKEL", "HERSTELLERNUMMER", "ARTIKELBEZ",
	"MENGE", "PREISME", "LISTPREIS", "RABATT", "EINZELPREIS", "POSITIONSPREIS",
	"WARTUNGSBEGINN", "WARTUNGSENDE", "VERTRAG",
	"MARKETPLACE_REF", "ORDER_REFERENCE", "ENDKUNDE_REFERENCE",
	"SUBSCRIPTION_ID_EXTERNAL", "SUBSCRIPTION_START_DATE", "BUCHUNGSTYP",
	"ORDERDATUM", "RECHNUNGSART", "MSERP", "MSERP_BILLINGPERIOD",
	"BILLINGPLAN", "VERTRAGSDAUER", "ADDITIONALID", "ADDITIONALDESCRIPTION",
]


def _strip_bom(value: str) -> str:
	return value.lstrip("\ufeff") if value else value


def _normalize_header(header: Iterable[str]) -> list[str]:
	return [_strip_bom(h).strip() for h in header]


def _customer_ref_from(raw_ref: str | None, endkunde_field: str | None) -> str | None:
	"""Extrahiert die ERP-Customer-Referenz.

	In älteren ADN-Feeds steht die Referenz in Klammern hinter dem Endkundennamen
	(``"Augenweide Optometrie [CUST-21385]"``); in neueren Versionen direkt in
	der Spalte ``ENDKUNDE_REFERENCE``.
	"""
	if raw_ref:
		return raw_ref.strip()
	if endkunde_field and "[" in endkunde_field and "]" in endkunde_field:
		inside = endkunde_field.split("[", 1)[1].split("]", 1)[0].strip()
		return inside or None
	return None


@register
class ADNMonthlyCSVParser(BaseSupplierParser):
	parser_key = "adn_monthly_csv_v1"
	description = "ADN Distribution — monatliche Rechnungs-CSV"

	def parse(self, file_path: str) -> ParseResult:
		result = ParseResult()

		with open(file_path, "r", encoding="utf-8", newline="") as fh:
			reader = csv.reader(fh, delimiter=";", quotechar='"')
			try:
				raw_header = next(reader)
			except StopIteration:
				result.warnings.append("Datei ist leer.")
				return result

			header = _normalize_header(raw_header)
			result.format_drift = not self._header_matches(header)

			for source_row, row in enumerate(reader, start=2):
				if not row or not any(cell.strip() for cell in row):
					continue
				data = self._row_to_dict(header, row)

				position = (data.get("POSITION") or "").strip()
				# Reine Kopfzeile (Position = "1" ohne Artikel) wird übersprungen;
				# ADN wiederholt die Rechnungskopfdaten als erste Zeile ohne Artikel.
				if not (data.get("ARTIKEL") or "").strip() and not (data.get("HERSTELLERNUMMER") or "").strip():
					continue

				canonical = self._to_canonical(data, source_row)
				if canonical is not None:
					result.rows.append(canonical)

			# Rechnungsdatum aus erster Zeile übernehmen (alle Zeilen gehören zu
			# derselben Lieferantenrechnung und tragen dasselbe Datum)
			if result.rows:
				first_raw = result.rows[0].raw
				result.invoice_date = parse_german_date(first_raw.get("DATUM"))

		return result

	# ---------------------------------------------------------------
	# internals
	# ---------------------------------------------------------------

	def _header_matches(self, actual: list[str]) -> bool:
		return [h.upper() for h in actual if h] == [h.upper() for h in EXPECTED_HEADER if h]

	def _row_to_dict(self, header: list[str], row: list[str]) -> dict[str, str]:
		# Robust gegen Zeilen mit abweichender Spaltenanzahl
		return {header[i]: row[i] for i in range(min(len(header), len(row)))}

	def _to_canonical(self, d: dict[str, str], source_row: int) -> CanonicalRow | None:
		raw_ref = (d.get("ENDKUNDE_REFERENCE") or "").strip() or None
		customer_ref = _customer_ref_from(raw_ref, d.get("ENDKUNDE"))

		# Negative Menge oder negative Positionspreise kennzeichnen Gutschriften
		qty = parse_german_decimal(d.get("MENGE")) or 0.0
		list_price = parse_german_decimal(d.get("LISTPREIS"))
		unit_price = parse_german_decimal(d.get("EINZELPREIS"))
		amount = parse_german_decimal(d.get("POSITIONSPREIS"))
		discount = parse_german_decimal(d.get("RABATT"))

		rechnungsart = (d.get("RECHNUNGSART") or "").strip()
		document_type = "Gutschrift" if "gutschrift" in rechnungsart.lower() else "Rechnung"
		if amount is not None and amount < 0:
			document_type = "Gutschrift"

		return CanonicalRow(
			source_row=source_row,
			supplier_invoice_no=(d.get("RECHNUNG") or "").strip() or None,
			customer_external_ref=customer_ref,
			customer_display_name=(d.get("ENDKUNDE") or "").strip() or None,
			vendor_product_id=(d.get("HERSTELLERNUMMER") or "").strip() or None,
			supplier_article_no=(d.get("ARTIKEL") or "").strip() or None,
			description=(d.get("ARTIKELBEZ") or "").strip() or None,
			qty=qty,
			list_price=list_price,
			discount_pct=discount,
			unit_price=unit_price,
			amount=amount,
			period_start=parse_german_date(d.get("WARTUNGSBEGINN")),
			period_end=parse_german_date(d.get("WARTUNGSENDE")),
			subscription_external_id=(d.get("SUBSCRIPTION_ID_EXTERNAL") or "").strip() or None,
			subscription_start=parse_german_date(d.get("SUBSCRIPTION_START_DATE")),
			billing_plan=normalize_billing_plan(d.get("BILLINGPLAN")),
			term_duration=normalize_term_duration(d.get("VERTRAGSDAUER")),
			booking_type=normalize_booking_type(d.get("BUCHUNGSTYP")),
			document_type=document_type,
			marketplace_ref=(d.get("MARKETPLACE_REF") or "").strip() or None,
			order_ref=(d.get("ORDER_REFERENCE") or "").strip() or None,
			raw=d,
		)
