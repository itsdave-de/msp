"""Basis-Klassen und Datenstrukturen für das Supplier-Import-Framework.

Parser dürfen **keine** Frappe-/DB-Zugriffe tun. Sie lesen eine Datei und geben
eine Sequenz von :class:`CanonicalRow`-Objekten zurück. Validierung und Persistenz
übernimmt der DocumentBuilder / Orchestrator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Iterator


# ---------------------------------------------------------------------------
# Kanonische Datenstruktur — gilt für *alle* Lieferanten nach Normalisierung
# ---------------------------------------------------------------------------

@dataclass
class CanonicalRow:
	# Identifikation
	source_row: int = 0                      # Zeilennummer in der Quelldatei
	supplier_invoice_no: str | None = None   # z. B. ADN RECHNUNG

	# Kunde
	customer_external_ref: str | None = None  # z. B. "CUST-21254"
	customer_display_name: str | None = None  # Langname aus der Quelldatei

	# Produkt
	vendor_product_id: str | None = None      # z. B. "CFQ7TTC0LCHC:0002"
	supplier_article_no: str | None = None    # interne Artikelnummer des Lieferanten
	description: str | None = None

	# Mengen & Preise
	qty: float = 0.0
	list_price: float | None = None
	discount_pct: float | None = None
	unit_price: float | None = None
	amount: float | None = None

	# Laufzeit & Billing
	period_start: date | None = None
	period_end: date | None = None
	subscription_external_id: str | None = None
	subscription_start: date | None = None
	billing_plan: str | None = None     # normalisiert: "Monthly" / "Annual" / "Triennial"
	term_duration: str | None = None    # normalisiert: "P1M" / "P1Y" / "P3Y"
	booking_type: str | None = None     # normalisiert: "New" / "Renewal" / "Billing" / "Upgrade" / "Cancel"
	document_type: str | None = None    # "Rechnung" / "Gutschrift"

	# Referenzen
	marketplace_ref: str | None = None
	order_ref: str | None = None

	# Forensik
	raw: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Parse-Ergebnis inkl. Kopfdaten & Warnungen
# ---------------------------------------------------------------------------

@dataclass
class ParseResult:
	rows: list[CanonicalRow] = field(default_factory=list)
	warnings: list[str] = field(default_factory=list)
	format_drift: bool = False   # Spalten wichen vom erwarteten Layout ab
	invoice_date: date | None = None  # falls alle Zeilen aus einer Lieferantenrechnung stammen


# ---------------------------------------------------------------------------
# Basis-Parser
# ---------------------------------------------------------------------------

class BaseSupplierParser:
	"""Alle Lieferanten-Parser erben hiervon und implementieren :meth:`parse`.

	Kein DB-Zugriff — reine Datei-in → Objekte-out-Logik.
	"""

	#: Eindeutiger Schlüssel in der Registry (z. B. ``adn_monthly_csv_v1``).
	parser_key: str = ""

	#: Für Menschen lesbare Beschreibung.
	description: str = ""

	def parse(self, file_path: str) -> ParseResult:
		raise NotImplementedError


# ---------------------------------------------------------------------------
# Hilfsfunktionen zur Wert-Normalisierung
# ---------------------------------------------------------------------------

def normalize_billing_plan(raw: str | None) -> str | None:
	if not raw:
		return None
	r = raw.strip().lower()
	if r in ("month", "monthly", "monatlich"):
		return "Monthly"
	if r in ("year", "annual", "yearly", "jährlich", "jaehrlich"):
		return "Annual"
	if r in ("triennial", "3years", "3y"):
		return "Triennial"
	return None


def normalize_term_duration(raw: str | None) -> str | None:
	if not raw:
		return None
	r = raw.strip().lower()
	if r in ("monthly", "month", "p1m", "1m"):
		return "P1M"
	if r in ("annual", "yearly", "p1y", "1y"):
		return "P1Y"
	if r in ("triennial", "p3y", "3y"):
		return "P3Y"
	return None


def normalize_booking_type(raw: str | None) -> str | None:
	if not raw:
		return None
	r = raw.strip().lower()
	mapping = {
		"new": "New",
		"neu": "New",
		"renewal": "Renewal",
		"verlängerung": "Renewal",
		"billing": "Billing",
		"abrechnung": "Billing",
		"upgrade": "Upgrade",
		"cancel": "Cancel",
		"cancellation": "Cancel",
		"kündigung": "Cancel",
	}
	return mapping.get(r)


def parse_german_decimal(value: str | None) -> float | None:
	if value is None:
		return None
	s = str(value).strip()
	if not s:
		return None
	# deutsches Format: Komma als Dezimaltrenner, evtl. Punkt als Tausendertrenner
	s = s.replace(".", "").replace(",", ".") if s.count(",") == 1 and s.count(".") <= 1 else s.replace(",", ".")
	try:
		return float(s)
	except ValueError:
		return None


def parse_german_date(value: str | None) -> date | None:
	if not value:
		return None
	s = str(value).strip()
	if not s or s in ("0", "-"):
		return None
	# Verbreitete ADN-Formate: TT.MM.JJJJ oder JJJJ-MM-TT
	from datetime import datetime
	for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
		try:
			return datetime.strptime(s, fmt).date()
		except ValueError:
			continue
	# Häufiger ADN-Fehler: "226.02.2025" → führender Tippfehler, erste Ziffer droppen
	if len(s) == 11 and s[0].isdigit() and s[1].isdigit() and s[2] == ".":
		try:
			return datetime.strptime(s[1:], "%d.%m.%Y").date()
		except ValueError:
			pass
	return None


def iter_parser_output(parse_result: ParseResult) -> Iterator[CanonicalRow]:
	"""Kleine Convenience: Iteration nur über Rows."""
	yield from parse_result.rows


__all__ = [
	"CanonicalRow",
	"ParseResult",
	"BaseSupplierParser",
	"normalize_billing_plan",
	"normalize_term_duration",
	"normalize_booking_type",
	"parse_german_decimal",
	"parse_german_date",
	"iter_parser_output",
]
