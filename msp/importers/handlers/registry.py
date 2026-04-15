"""Registry und Dispatch der FileHandler."""

from __future__ import annotations

from typing import Type

from msp.importers.handlers.base import BaseFileHandler


_HANDLERS: dict[str, Type[BaseFileHandler]] = {}


def register(handler_cls: Type[BaseFileHandler]) -> Type[BaseFileHandler]:
	key = getattr(handler_cls, "handler_key", "")
	if not key:
		raise ValueError(f"{handler_cls.__name__} ohne handler_key kann nicht registriert werden")
	if key in _HANDLERS:
		raise ValueError(f"handler_key bereits belegt: {key}")
	_HANDLERS[key] = handler_cls
	return handler_cls


def get(handler_key: str) -> Type[BaseFileHandler]:
	_autoload()
	if handler_key not in _HANDLERS:
		raise KeyError(f"Kein Handler mit key='{handler_key}' registriert. "
		               f"Verfügbar: {sorted(_HANDLERS)}")
	return _HANDLERS[handler_key]


def all_handlers() -> list[Type[BaseFileHandler]]:
	_autoload()
	return list(_HANDLERS.values())


def detect_best_handler(sample_bytes: bytes, filename: str,
                        *, min_confidence: float = 0.5,
                        ) -> tuple[Type[BaseFileHandler] | None, float, list[dict]]:
	"""Sniff alle Handler, liefert besten Match + Score + komplette Ranking-Liste.

	Rückgabe:
	    ``(best_handler_cls | None, best_confidence, scores)`` — best_handler_cls ist
	    ``None``, wenn keiner über ``min_confidence`` liegt.
	    ``scores`` ist eine nach Confidence absteigend sortierte Liste
	    ``[{"handler_key": ..., "display_name": ..., "confidence": ...}]``.
	"""
	_autoload()
	scores = []
	for cls in _HANDLERS.values():
		try:
			c = float(cls.sniff(sample_bytes, filename) or 0)
		except Exception:
			c = 0.0
		scores.append({
			"handler_key": cls.handler_key,
			"display_name": cls.display_name,
			"confidence": c,
		})
	scores.sort(key=lambda x: x["confidence"], reverse=True)
	top = scores[0] if scores else None
	best_cls = _HANDLERS.get(top["handler_key"]) if top and top["confidence"] >= min_confidence else None
	best_conf = top["confidence"] if top else 0.0
	return best_cls, best_conf, scores


def _autoload() -> None:
	"""Importiert bekannte Handler-Module, damit @register-Dekoratoren laufen."""
	from msp.importers.handlers import adn_monthly_csv_handler  # noqa: F401
	from msp.importers.handlers import adn_hornet_csv_handler  # noqa: F401
