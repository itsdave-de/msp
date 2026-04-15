"""DocumentBuilder — erzeugt Sales Invoices oder Delivery Notes aus kanonischen Zeilen."""

from __future__ import annotations

from dataclasses import dataclass, field

import frappe

from msp.importers.base import CanonicalRow
from msp.importers.coverage import CoverageCache
from msp.importers.resolution import resolve_customer, resolve_item
from msp.importers.subscriptions import (
	create_event,
	event_exists_for_period,
	upsert_supply_subscription,
)


@dataclass
class BuildResult:
	created_documents: list[tuple[str, str]] = field(default_factory=list)  # (doctype, name)
	line_outcomes: list[dict] = field(default_factory=list)
	errors: list[str] = field(default_factory=list)


class DocumentBuilder:
	def __init__(self, profile, coverage: CoverageCache | None = None):
		self.profile = profile
		self.coverage = coverage or CoverageCache()
		self.output_mode: str = "Sales Invoice"  # wird pro Gruppe gesetzt

	# -----------------------------------------------------------------
	# Public API
	# -----------------------------------------------------------------

	def build(self, rows: list[CanonicalRow], output_mode: str) -> BuildResult:
		"""Erzeugt Dokumente für *eine* Kunden-Gruppe (alle rows gehören demselben Kunden)."""
		self.output_mode = output_mode
		result = BuildResult()

		if not rows:
			return result

		# Gutschriften separieren (negative Positionspreise oder Rechnungsart=Gutschrift)
		invoice_rows = [r for r in rows if (r.amount or 0) >= 0 and r.document_type != "Gutschrift"]
		credit_rows = [r for r in rows if (r.amount or 0) < 0 or r.document_type == "Gutschrift"]

		if invoice_rows:
			self._build_one(invoice_rows, is_return=False, result=result)
		if credit_rows:
			self._build_one(credit_rows, is_return=True, result=result)

		return result

	# -----------------------------------------------------------------
	# Internals
	# -----------------------------------------------------------------

	def _build_one(self, rows: list[CanonicalRow], *, is_return: bool, result: BuildResult) -> None:
		first = rows[0]
		customer, is_fallback = resolve_customer(
			first.customer_external_ref, self.profile.fallback_customer,
			lookup_field=getattr(self.profile, "customer_lookup_field", None) or None,
		)
		if not customer:
			for r in rows:
				result.line_outcomes.append({
					"row": r, "status": "Error",
					"error": f"Customer nicht gefunden (ref={r.customer_external_ref})",
				})
			return

		doc = self._new_document(customer, first, is_return=is_return)

		outcomes_this_group: list[dict] = []
		for r in rows:
			outcome = self._append_line(doc, r, is_return=is_return)
			outcomes_this_group.append(outcome)
			result.line_outcomes.append(outcome)

		if not doc.items:
			# Kein Dokument erzeugen. Unterscheiden: all skipped vs. all errored.
			statuses = {o["status"] for o in outcomes_this_group}
			if statuses == {"Skipped"}:
				# Idempotent: alles schon da. Kein Fehler.
				return
			# Sonst waren echte Fehler im Spiel.
			result.errors.append(f"Kunde {customer}: keine gültigen Positionen, Dokument nicht erzeugt.")
			return

		try:
			doc.insert(ignore_permissions=True)
		except Exception as e:
			result.errors.append(f"Insert fehlgeschlagen ({customer}): {e}")
			# Aufräumen: bereits gesetzte Outcomes als Error markieren
			for o in result.line_outcomes[-len(rows):]:
				if o["status"] == "Created":
					o["status"] = "Error"
					o["error"] = str(e)
			return

		# Title nach Insert festnageln — ERPNext setzt ihn sonst über
		# title_field/autoname auf "{customer_name}" zurück.
		if doc.title and "{" not in doc.title:
			frappe.db.set_value(doc.doctype, doc.name, "title", doc.title)

		result.created_documents.append((doc.doctype, doc.name))

		# Erfolgreiche Outcomes mit dem Ziel-Dokument annotieren — damit der
		# Persist-Schritt im Run-Orchestrator die Zeilen rückverlinken kann,
		# auch wenn keine Subscription-Events erzeugt wurden (z. B. Hornet
		# ohne Vertrag-Spalte).
		for o in outcomes_this_group:
			if o.get("status") == "Created":
				o.setdefault("target_doctype", doc.doctype)
				o.setdefault("target_name", doc.name)
				o.setdefault("resolved_customer", customer)

		# Subscription-Events erst nach erfolgreichem Insert, damit wir die
		# echten Item-Row-IDs nutzen können.
		self._post_create_subscriptions(doc, rows, result)

	def _new_document(self, customer: str, first: CanonicalRow, *, is_return: bool):
		"""Erzeugt das Grundgerüst (ohne Zeilen) der Sales Invoice / Delivery Note."""
		profile = self.profile
		period = self._format_period_label(first)
		posting_date = self._coerce_german_date(first.raw.get("DATUM") or frappe.utils.today())
		title = self._render_title(customer, period, posting_date, is_return=is_return)

		if self.output_mode == "Sales Invoice":
			doc = frappe.new_doc("Sales Invoice")
			doc.customer = customer
			doc.company = profile.default_company
			doc.currency = frappe.db.get_value("Company", profile.default_company, "default_currency") or "EUR"
			doc.posting_date = posting_date
			doc.set_posting_time = 1
			if profile.default_cost_center:
				doc.cost_center = profile.default_cost_center
			if profile.default_taxes_and_charges:
				doc.taxes_and_charges = profile.default_taxes_and_charges
				self._copy_tax_template_rows(doc, profile.default_taxes_and_charges)
			if profile.default_payment_terms_template:
				doc.payment_terms_template = profile.default_payment_terms_template
			if profile.default_tc_name:
				doc.tc_name = profile.default_tc_name
			if profile.intro_text_invoice and not is_return:
				doc.introduction_text = profile.intro_text_invoice
			if profile.intro_text_credit_note and is_return:
				doc.introduction_text = profile.intro_text_credit_note
			if title:
				doc.title = title
			if is_return:
				doc.is_return = 1
			return doc

		# Delivery Note
		doc = frappe.new_doc("Delivery Note")
		doc.customer = customer
		doc.company = profile.default_company
		doc.posting_date = posting_date
		doc.set_posting_time = 1
		if profile.default_cost_center:
			doc.cost_center = profile.default_cost_center
		if profile.default_taxes_and_charges:
			doc.taxes_and_charges = profile.default_taxes_and_charges
			self._copy_tax_template_rows(doc, profile.default_taxes_and_charges)
		if title:
			doc.title = title
		if is_return:
			doc.is_return = 1
		return doc

	def _append_line(self, doc, row: CanonicalRow, *, is_return: bool) -> dict:
		item_code, reason = resolve_item(row.vendor_product_id)
		if not item_code:
			return {"row": row, "status": "Error",
			        "error": f"Item-Lookup {reason}: vendor_product_id={row.vendor_product_id}"}

		# Deduplizierung: bereits Event für diese Subscription+Period vorhanden?
		# Gutschriftzeilen (qty<0 oder amount<0) laufen IMMER durch — sie sind inhaltlich
		# eine Korrektur der bereits erfassten Rechnung, nie eine Dublette.
		is_credit_row = (row.qty or 0) < 0 or (row.amount or 0) < 0 or row.document_type == "Gutschrift"
		if (not is_credit_row
		    and row.subscription_external_id
		    and event_exists_for_period(
		        row.subscription_external_id, row.period_start, row.period_end)):
			return {"row": row, "status": "Skipped",
			        "error": "Bereits importiert (Subscription+Period existieren)"}

		qty = row.qty or 0
		if is_return and qty > 0:
			qty = -qty

		# WICHTIG: Kundenabrechnungen nutzen den LISTPREIS, nicht den Einkaufspreis.
		# Der Lieferanten-Rabatt (z. B. 17,5 % bei ADN) ist unsere Marge und
		# darf nicht an den Endkunden durchgereicht werden.
		# Fallback-Reihenfolge: list_price → unit_price → amount/qty
		if row.list_price is not None:
			rate = row.list_price
		elif row.unit_price is not None:
			rate = row.unit_price
		elif row.amount is not None and qty:
			rate = row.amount / qty
		else:
			rate = 0

		# License Coverage: ggf. Split in (kostenlose, abgedeckte) + (reguläre Rest-)Position.
		# Gilt nur für echte Rechnungen — nicht für Gutschriften, die die Originalposition
		# komplett reversieren.
		covered_qty = 0
		if not is_return:
			covered_qty = self.coverage.get_covered_qty(doc.customer, item_code, row.period_start)

		start_idx = len(doc.items)
		base_description = self._format_description(row)

		def _append(line_qty: float, description: str, is_covered: bool) -> None:
			line = {
				"item_code": item_code,
				"qty": line_qty,
				"rate": rate,
				"description": description,
			}
			if is_covered:
				line["discount_percentage"] = 100
			item = doc.append("items", line)
			if self.output_mode == "Delivery Note" and self.profile.default_warehouse:
				item.warehouse = self.profile.default_warehouse

		if covered_qty > 0 and qty > 0:
			covered_portion = min(qty, covered_qty)
			_append(covered_portion,
			        description=f"{base_description}<br><strong>ohne Berechnung</strong>",
			        is_covered=True)
			remaining = qty - covered_portion
			if remaining > 0:
				_append(remaining, description=base_description, is_covered=False)
		else:
			_append(qty, description=base_description, is_covered=False)

		produced_indices = list(range(start_idx, len(doc.items)))
		return {
			"row": row,
			"status": "Created",
			"error": None,
			"item_indices": produced_indices,
			"covered_qty": min(qty, covered_qty) if (covered_qty > 0 and qty > 0) else 0,
		}

	def _post_create_subscriptions(self, doc, rows: list[CanonicalRow], result: BuildResult) -> None:
		"""Erzeugt pro successful row ein Supply Subscription Event (sofern eine Subscription-ID vorhanden ist).

		Bei License-Coverage-Split kann eine kanonische Zeile 1–2 Item-Rows produziert haben.
		Wir verwenden die in _append_line gespeicherten ``item_indices``, um das erste
		(= „primäre") Item als Anker für Subscription + Link-Feld zu nutzen, und setzen
		den supply_subscription-Link auf *allen* zur Zeile gehörenden Item-Rows.
		"""
		created_rows = [o for o in result.line_outcomes[-len(rows):] if o["status"] == "Created"]

		for outcome in created_rows:
			r: CanonicalRow = outcome["row"]
			indices = outcome.get("item_indices") or []
			if not indices:
				continue
			item_rows = [doc.items[i] for i in indices if i < len(doc.items)]
			if not item_rows:
				continue
			primary = item_rows[0]

			if not r.subscription_external_id:
				continue

			vendor = self.profile.vendor
			supplier = self.profile.supplier
			sub_name = upsert_supply_subscription(
				r, customer=doc.customer, supplier=supplier, vendor=vendor, item=primary.item_code,
			)
			if not sub_name:
				continue
			try:
				event_name = create_event(
					r,
					supply_subscription=sub_name,
					target_doctype=doc.doctype,
					target_name=doc.name,
					target_row=primary.name,
				)
				# Link auf allen zur kanonischen Zeile gehörenden Item-Rows setzen
				for ir in item_rows:
					frappe.db.set_value(
						f"{doc.doctype} Item", ir.name,
						"supply_subscription", sub_name,
					)
				outcome["event"] = event_name
				outcome["supply_subscription"] = sub_name
			except Exception as e:
				outcome["subscription_error"] = str(e)

	# -----------------------------------------------------------------
	# Formatter / Helpers
	# -----------------------------------------------------------------

	def _format_description(self, row: CanonicalRow) -> str:
		parts = []
		if row.description:
			parts.append(row.description)
		if row.period_start and row.period_end:
			parts.append(f"Zeitraum von {row.period_start.strftime('%d.%m.%Y')} bis {row.period_end.strftime('%d.%m.%Y')}")
		if row.subscription_external_id:
			parts.append(f"Subscription: {row.subscription_external_id}")
		return "<br>".join(parts) if parts else (row.description or "")

	def _format_period_label(self, row: CanonicalRow) -> str:
		"""Monats-/Jahreslabel für den Dokumenttitel — z. B. '02.2026'."""
		d = row.period_end or row.period_start
		if d:
			return d.strftime("%m.%Y")
		from datetime import date as _d
		from msp.importers.base import parse_german_date
		invdate = parse_german_date(row.raw.get("DATUM")) if row.raw else None
		if invdate:
			return invdate.strftime("%m.%Y")
		return _d.today().strftime("%m.%Y")

	def _render_title(self, customer: str, period: str, posting_date, *, is_return: bool) -> str:
		"""Rendert den Beleg-Titel aus dem konfigurierten Template (mit Fallback).

		Platzhalter: {prefix}, {period}, {customer}, {customer_name},
		{vendor}, {posting_date}, {document_type}.
		"""
		profile = self.profile
		template = (profile.title_template_credit_note if is_return else profile.title_template) or ""
		prefix = (profile.title_prefix_credit_note if is_return else profile.title_prefix) or ""
		template = template.strip()
		if not template:
			# Backwards-compat: bisheriges Verhalten "{prefix} {period}".
			return f"{prefix.strip()} {period}".strip()

		customer_name = frappe.db.get_value("Customer", customer, "customer_name") or customer
		invoice_month = (
			posting_date.strftime("%m.%Y") if hasattr(posting_date, "strftime") else ""
		)
		try:
			rendered = template.format(
				prefix=prefix.strip(),
				period=period,
				invoice_month=invoice_month,
				customer=customer,
				customer_name=customer_name,
				vendor=profile.vendor or "",
				posting_date=posting_date.strftime("%d.%m.%Y") if hasattr(posting_date, "strftime") else str(posting_date),
				document_type=self.output_mode or "",
			)
		except (KeyError, IndexError) as e:
			# Unbekannter Platzhalter — robust auf Fallback zurückfallen, aber dem Run
			# trotzdem einen Hinweis mitgeben, indem wir den Profilfehler in die Logs schreiben.
			frappe.log_error(
				f"Title-Template enthält ungültigen Platzhalter ({e}); fällt auf '{{prefix}} {{period}}' zurück.",
				"Supplier Import Builder",
			)
			rendered = f"{prefix.strip()} {period}".strip()
		# Mehrfach-Whitespace zusammenfassen
		return " ".join(rendered.split())

	@staticmethod
	def _copy_tax_template_rows(doc, template_name: str) -> None:
		"""Kopiert die Zeilen des Sales-Taxes-and-Charges-Templates explizit in doc.taxes.

		Hintergrund: Frappe populiert die taxes-Tabelle bei reinem Setzen von
		``taxes_and_charges`` nicht zuverlässig mit den korrekten Raten. Im Ergebnis
		führte das dazu, dass Zeilen ohne item_tax_template vollständig aus der
		Steuerberechnung fielen. Explizites Kopieren stellt sicher, dass die Rate
		am Dokument auf dem Template-Wert steht.
		"""
		template = frappe.get_cached_doc("Sales Taxes and Charges Template", template_name)
		for tax in template.taxes:
			doc.append("taxes", {
				"charge_type": tax.charge_type,
				"account_head": tax.account_head,
				"rate": tax.rate,
				"description": tax.description,
				"cost_center": tax.cost_center,
				"included_in_print_rate": tax.included_in_print_rate,
			})

	@staticmethod
	def _coerce_german_date(value):
		"""Akzeptiert strings oder date-Objekte; liefert date-tauglichen Wert für Frappe."""
		if not value:
			from datetime import date
			return date.today()
		if hasattr(value, "strftime"):
			return value
		from msp.importers.base import parse_german_date
		return parse_german_date(value) or frappe.utils.getdate(value)
