"""FileHandler-Abstraktion für den Import-Assistenten.

Ein ``FileHandler`` weiß, ob er eine hochgeladene Datei verarbeiten kann
(``sniff``), liefert eine DB-freie Vorschau (``preview``) und kann den
eigentlichen Import ausführen (``execute``). Er ist die Einheit, die der
Dropzone-/Assistent-UI zugrunde liegt.

Bestehende Parser (``msp.importers.base.BaseSupplierParser``) bleiben
darunter erhalten — ein Handler nutzt sie als innere Mechanik.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


ProgressCallback = Callable[[dict], None]


@dataclass
class PreviewResult:
	"""Leichtgewichtige Statistik für die Dropzone-Karte."""

	supplier_profile_suggested: str | None = None   # Supplier Import Profile-Name
	line_count: int = 0
	customer_count: int = 0
	product_count: int = 0
	period_label: str | None = None     # z. B. „03.2026" oder „09/2025 – 02/2026"
	format_drift: bool = False
	credit_note_lines: int = 0
	warnings: list[str] = field(default_factory=list)
	extra: dict = field(default_factory=dict)


@dataclass
class ExecuteResult:
	"""Zusammenfassung eines fertigen Imports."""

	status: str                         # Succeeded / Partial / Failed
	run_name: str | None = None         # Supplier Import Run-Name, falls angelegt
	document_count: int = 0
	line_count: int = 0
	error_count: int = 0
	skipped_count: int = 0
	message: str | None = None


class BaseFileHandler:
	"""Basisklasse für alle Datei-Handler.

	Subklassen registrieren sich über :func:`msp.importers.handlers.registry.register`.
	"""

	#: Eindeutiger Schlüssel, unter dem der Handler in der Registry liegt.
	handler_key: str = ""

	#: Menschlich lesbarer Name (für UI-Karten).
	display_name: str = ""

	#: Welche Dateiendungen der Handler prinzipiell akzeptiert (kleingeschrieben, mit Punkt).
	accepted_extensions: list[str] = []

	#: Optionaler abweichender Wizard-Pfad. ``None`` ⇒ Default-Wizard wird genutzt.
	wizard_route: str | None = None

	# ------------------------------------------------------------------
	# Abstrakte Methoden — in Subklassen überschreiben
	# ------------------------------------------------------------------

	@classmethod
	def sniff(cls, sample_bytes: bytes, filename: str) -> float:
		"""Gibt Confidence 0.0–1.0 zurück, dass dieser Handler die Datei verarbeiten kann.

		``sample_bytes`` enthält die ersten ~8 KiB der (ggf. schon entpackten) Datei.
		``filename`` ist der ursprüngliche Dateiname (hilfreich bei Extension-Matching).
		"""
		raise NotImplementedError

	@classmethod
	def preview(cls, file_path: str) -> PreviewResult:
		"""Leichte Analyse ohne DB-Writes. Wird vom Dropzone-Analyze-Endpoint aufgerufen."""
		raise NotImplementedError

	@classmethod
	def execute(cls, file_path: str, *, config: dict,
	            progress: ProgressCallback | None = None) -> ExecuteResult:
		"""Führt den tatsächlichen Import durch.

		``config`` enthält mindestens: ``profile`` (Supplier Import Profile-Name),
		``output_mode`` (leer / "Sales Invoice" / "Delivery Note"),
		``acknowledge_format_drift`` (bool). Weitere Felder je Handler.
		``progress`` wird (falls gegeben) regelmäßig mit Fortschritts-Dicts aufgerufen,
		z. B. ``{"phase": "importing", "processed": 47, "total": 113}``.
		"""
		raise NotImplementedError


__all__ = ["BaseFileHandler", "PreviewResult", "ExecuteResult", "ProgressCallback"]
