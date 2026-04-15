"""Parser für die ADN-Hornetsecurity-Abrechnungs-CSVs.

Das Format ist nahezu identisch zum monatlichen Microsoft-CSV (gleiche
Spaltenfamilie für Kopfdaten / Endkunde / Position), unterscheidet sich
inhaltlich aber in vier Punkten:

* Die Subscription-Identifikation läuft über ``Vertrag`` (statt
  ``SUBSCRIPTION_ID_EXTERNAL``).
* Mengen werden anteilig auf den Abrechnungsmonat heruntergerechnet
  (``Wartungsbeginn``/``Wartungsende`` ergeben einen Faktor).
* Hornet-CSVs enthalten **nicht** die Microsoft-spezifischen Spalten
  ``BILLINGPLAN`` / ``MSERP`` / ``VERTRAGSDAUER``.
* Die Endkunden-Referenz ist eine Mail-Domain (``Customer.hornet_domain``)
  und keine ERP-Customer-ID — die Auflösung übernimmt der Builder über
  das Profilfeld ``customer_lookup_field``.
"""

from __future__ import annotations

import calendar
import csv
from datetime import date
from typing import Iterable

from msp.importers.base import (
	BaseSupplierParser,
	CanonicalRow,
	ParseResult,
	parse_german_date,
	parse_german_decimal,
)
from msp.importers.registry import register


# Die Spaltenliste basiert auf der Validierung im legacy adnconnect.adn_hornet_import
# Modul. ADN exportiert seit jeher in mixed case; wir vergleichen aber
# case-insensitiv und tolerieren Drift.
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
	"ORDERDATUM", "RECHNUNGSART",
]


def _strip_bom(value: str) -> str:
	return value.lstrip("\ufeff") if value else value


def _normalize_header(header: Iterable[str]) -> list[str]:
	return [_strip_bom(h).strip() for h in header]


@register
class ADNHornetCSVParser(BaseSupplierParser):
	parser_key = "adn_hornet_csv_v1"
	description = "ADN Distribution — Hornetsecurity-Abrechnungs-CSV"

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

				# Header-Wiederholung pro Rechnung überspringen (Position 1 ohne Artikel)
				if not (data.get("ARTIKEL") or "").strip() and not (data.get("HERSTELLERNUMMER") or "").strip():
					continue

				canonical = self._to_canonical(data, source_row)
				if canonical is not None:
					result.rows.append(canonical)

			if result.rows:
				first_raw = result.rows[0].raw
				result.invoice_date = parse_german_date(first_raw.get("DATUM"))

		return result

	# ------------------------------------------------------------------
	# Internals
	# ------------------------------------------------------------------

	def _header_matches(self, actual: list[str]) -> bool:
		actual_upper = {h.upper() for h in actual if h}
		expected_upper = {h.upper() for h in EXPECTED_HEADER if h}
		return expected_upper.issubset(actual_upper)

	def _row_to_dict(self, header: list[str], row: list[str]) -> dict[str, str]:
		# Robust gegen Zeilen mit abweichender Spaltenanzahl. Wir ziehen die
		# Schlüssel zudem auf upper, damit Mixed-Case-Header (Endkunde vs.
		# ENDKUNDE) keine Lookups vereiteln.
		out: dict[str, str] = {}
		for i in range(min(len(header), len(row))):
			out[header[i].upper()] = row[i]
		return out

	def _to_canonical(self, d: dict[str, str], source_row: int) -> CanonicalRow | None:
		# ADN-Hornet-CSVs lassen ENDKUNDE_REFERENCE in der Praxis fast immer
		# leer und tragen die Mail-Domain stattdessen direkt in ENDKUNDE ein.
		# Legacy-Verhalten (adnconnect.adn_hornet_import.get_invoice_dict_from_csv)
		# fällt in dem Fall auf ENDKUNDE als Domain zurück.
		raw_ref = (d.get("ENDKUNDE_REFERENCE") or "").strip() or None
		endkunde = (d.get("ENDKUNDE") or "").strip() or None
		if not raw_ref and endkunde and "." in endkunde and " " not in endkunde:
			# Sieht nach einer Domain aus → als Hornet-Lookup-Schlüssel nutzen.
			raw_ref = endkunde

		raw_qty = parse_german_decimal(d.get("MENGE")) or 0.0
		list_price = parse_german_decimal(d.get("LISTPREIS"))
		unit_price = parse_german_decimal(d.get("EINZELPREIS"))
		amount = parse_german_decimal(d.get("POSITIONSPREIS"))
		discount = parse_german_decimal(d.get("RABATT"))

		period_start = parse_german_date(d.get("WARTUNGSBEGINN"))
		period_end = parse_german_date(d.get("WARTUNGSENDE"))

		# Anteilige Menge: bei Hornet wird zwischen Wartungsbeginn und -ende
		# tageweise abgerechnet (z. B. neue Subscription mitten im Monat). Wir
		# multiplizieren daher mit (Wartungstage / Tage des Startmonats), wie
		# in adnconnect.adn_hornet_import._do_import.
		qty = self._apportion_quantity(raw_qty, period_start, period_end)

		rechnungsart = (d.get("RECHNUNGSART") or "").strip()
		document_type = "Gutschrift" if "gutschrift" in rechnungsart.lower() else "Rechnung"
		if amount is not None and amount < 0:
			document_type = "Gutschrift"

		# Vertrag fungiert als Subscription-Identifier — eindeutig pro Hornet-
		# Vertrag, damit der Idempotenz-Check (Event existiert für period?)
		# greift.
		subscription_id = (d.get("VERTRAG") or "").strip() or None

		return CanonicalRow(
			source_row=source_row,
			supplier_invoice_no=(d.get("RECHNUNG") or "").strip() or None,
			customer_external_ref=raw_ref,
			customer_display_name=(d.get("ENDKUNDE") or "").strip() or None,
			vendor_product_id=(d.get("HERSTELLERNUMMER") or "").strip() or None,
			supplier_article_no=(d.get("ARTIKEL") or "").strip() or None,
			description=(d.get("ARTIKELBEZ") or "").strip() or None,
			qty=qty,
			list_price=list_price,
			discount_pct=discount,
			unit_price=unit_price,
			amount=amount,
			period_start=period_start,
			period_end=period_end,
			subscription_external_id=subscription_id,
			subscription_start=parse_german_date(d.get("SUBSCRIPTION_START_DATE")),
			document_type=document_type,
			marketplace_ref=(d.get("MARKETPLACE_REF") or "").strip() or None,
			order_ref=(d.get("ORDER_REFERENCE") or "").strip() or None,
			raw=d,
		)

	@staticmethod
	def _apportion_quantity(qty: float, start: date | None, end: date | None) -> float:
		"""Skaliert die Menge anteilig auf den Abrechnungsmonat.

		Ist die Wartung gleich lang wie der Monat (üblicher Fall), bleibt die
		Menge unverändert. Bei mitten im Monat startenden Subscriptions
		entspricht die Menge dem Tagesanteil.
		"""
		if not start or not end or qty == 0:
			return qty
		days_in_month = calendar.monthrange(start.year, start.month)[1]
		warranty_days = (end - start).days + 1
		if days_in_month <= 0 or warranty_days <= 0:
			return qty
		factor = warranty_days / days_in_month
		# Volle Monate runden auf den Originalwert (Schutz gegen 31/30-Rauschen)
		if 0.97 <= factor <= 1.03:
			return qty
		return round(qty * factor, 4)
