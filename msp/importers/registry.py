"""Registry der verfügbaren Parser.

Parser werden über ihren ``parser_key`` aus einem Supplier Import Profile referenziert.
Neue Lieferanten ⇒ neuer Parser + Eintrag hier.
"""

from __future__ import annotations

from typing import Type

from msp.importers.base import BaseSupplierParser


_REGISTRY: dict[str, Type[BaseSupplierParser]] = {}


def register(parser_cls: Type[BaseSupplierParser]) -> Type[BaseSupplierParser]:
	"""Dekorator zum Registrieren einer Parser-Klasse anhand ihres ``parser_key``."""
	key = getattr(parser_cls, "parser_key", "")
	if not key:
		raise ValueError(f"{parser_cls.__name__} ohne parser_key kann nicht registriert werden")
	if key in _REGISTRY:
		raise ValueError(f"Parser-Key bereits belegt: {key}")
	_REGISTRY[key] = parser_cls
	return parser_cls


def resolve(parser_key: str) -> BaseSupplierParser:
	"""Gibt eine Instanz des Parsers zum gegebenen Schlüssel zurück."""
	if parser_key not in _REGISTRY:
		_autoload()
	if parser_key not in _REGISTRY:
		raise KeyError(f"Kein Parser für Key '{parser_key}' registriert. "
		               f"Verfügbar: {sorted(_REGISTRY)}")
	return _REGISTRY[parser_key]()


def available_keys() -> list[str]:
	_autoload()
	return sorted(_REGISTRY)


def _autoload() -> None:
	"""Importiert bekannte Parser-Module, damit ihre @register-Decorators laufen."""
	# Noqa — Imports dienen nur der Registrierung
	from msp.importers import adn_monthly_csv  # noqa: F401
