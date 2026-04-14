"""Dev-Helper: End-to-End-Check für einen Handler (sniff + preview)."""

from __future__ import annotations

import json

from msp.importers.handlers.registry import detect_best_handler


def run(path: str) -> str:
	with open(path, "rb") as f:
		sample = f.read(8192)
	filename = path.rsplit("/", 1)[-1]
	best, conf, scores = detect_best_handler(sample, filename)
	out = {"filename": filename, "best": None, "confidence": conf, "scores": scores}
	if best:
		preview = best.preview(path)
		out["best"] = {
			"handler_key": best.handler_key,
			"display_name": best.display_name,
			"line_count": preview.line_count,
			"customer_count": preview.customer_count,
			"product_count": preview.product_count,
			"period_label": preview.period_label,
			"format_drift": preview.format_drift,
			"credit_note_lines": preview.credit_note_lines,
			"suggested_profile": preview.supplier_profile_suggested,
			"warnings": preview.warnings,
		}
	return json.dumps(out, default=str, indent=2, ensure_ascii=False)
