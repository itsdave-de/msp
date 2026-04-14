"""Lookup-Helper für License Coverage.

Stellt die Inklusiv-Mengen pro (customer, item) für einen Importlauf bereit.
Pro Run werden die relevanten Coverage-Einträge **einmal** geladen und danach
aus dem In-Memory-Cache geliefert — DB-Zugriffe pro Rechnungsposition werden
so vermieden.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

import frappe


@dataclass
class CoverageCache:
	"""Vorab geladene Coverage-Einträge für einen Importlauf."""

	# (customer, item) -> [(qty, valid_from, valid_to, coverage_name), ...]
	_entries: dict[tuple[str, str], list[tuple[int, date | None, date | None, str]]] = field(
		default_factory=lambda: defaultdict(list)
	)

	def add(self, customer: str, item: str, qty: int,
	        valid_from: date | None, valid_to: date | None,
	        coverage_name: str) -> None:
		self._entries[(customer, item)].append((qty, valid_from, valid_to, coverage_name))

	def get_covered_qty(self, customer: str, item: str, period: date | None) -> int:
		"""Liefert die gesamte inkludierte Menge für (customer, item) zum Stichtag."""
		if not (customer and item):
			return 0
		entries = self._entries.get((customer, item))
		if not entries:
			return 0
		total = 0
		for qty, vf, vt, _ in entries:
			if period is not None:
				if vf is not None and period < vf:
					continue
				if vt is not None and period > vt:
					continue
			total += qty
		return total


def load_coverage_cache(customer_refs: Iterable[str]) -> CoverageCache:
	"""Lädt alle aktiven Coverage-Items für die angegebenen Kunden."""
	customers = [c for c in customer_refs if c]
	cache = CoverageCache()
	if not customers:
		return cache

	rows = frappe.db.sql(
		"""
		SELECT c.name, c.customer, c.valid_from, c.valid_to,
		       ci.item, ci.qty
		FROM `tabLicense Coverage` c
		JOIN `tabLicense Coverage Item` ci ON ci.parent = c.name
		WHERE c.enabled = 1 AND c.customer IN %(customers)s
		""",
		{"customers": tuple(customers)},
		as_dict=True,
	)
	for r in rows:
		cache.add(
			customer=r["customer"],
			item=r["item"],
			qty=int(r["qty"] or 0),
			valid_from=r["valid_from"],
			valid_to=r["valid_to"],
			coverage_name=r["name"],
		)
	return cache
