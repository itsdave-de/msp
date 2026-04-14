"""Helper zum Entpacken von ZIPs, die genau eine CSV enthalten.

ADN liefert die Monatsrechnungen gezippt (eine CSV pro ZIP). Dieser Helper
extrahiert die CSV in ein Temp-Verzeichnis und gibt den Pfad zurück. Aufrufer
sind dafür verantwortlich, das Temp-Verzeichnis nach Verarbeitung wieder
aufzuräumen.
"""

from __future__ import annotations

import os
import tempfile
import zipfile
from pathlib import Path


class ZipUnpackError(Exception):
	pass


def is_zip_path(path: str) -> bool:
	return path.lower().endswith(".zip")


def unpack_single_csv(zip_path: str) -> tuple[str, str]:
	"""Entpackt ein ZIP in ein Temp-Verzeichnis und erwartet genau eine CSV drin.

	Rückgabe: ``(temp_dir_path, csv_file_path)``. Aufrufer muss ``temp_dir_path``
	aufräumen (z. B. ``shutil.rmtree(temp_dir_path)``).
	"""
	if not zipfile.is_zipfile(zip_path):
		raise ZipUnpackError(f"Keine gültige ZIP-Datei: {zip_path}")

	with zipfile.ZipFile(zip_path, "r") as z:
		csv_members = [m for m in z.namelist()
		               if m.lower().endswith(".csv") and not m.endswith("/")]
		if len(csv_members) == 0:
			raise ZipUnpackError("ZIP enthält keine CSV-Datei.")
		if len(csv_members) > 1:
			raise ZipUnpackError(
				f"ZIP enthält {len(csv_members)} CSV-Dateien; genau eine wird erwartet. "
				f"Gefunden: {csv_members[:3]}{' …' if len(csv_members) > 3 else ''}"
			)
		member = csv_members[0]
		temp_dir = tempfile.mkdtemp(prefix="msp_import_unzip_")
		z.extract(member, temp_dir)
		# Normalisieren: Mitglieder-Pfad kann Unterverzeichnisse enthalten
		extracted = os.path.join(temp_dir, member)
		# Falls ZIP ein führendes Verzeichnis hatte, in den temp_dir-root mappen
		final_path = os.path.join(temp_dir, Path(member).name)
		if extracted != final_path:
			os.replace(extracted, final_path)
		return temp_dir, final_path
