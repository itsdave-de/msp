"""Temporärer Smoke-Test für den ADN-Parser.

Aufruf:
    bench --site <site> execute msp.importers._smoke_test.run --kwargs '{"path":"..."}'
"""

from __future__ import annotations

from collections import Counter
import json

from msp.importers.registry import resolve


def run(path: str) -> str:
	parser = resolve("adn_monthly_csv_v1")
	result = parser.parse(path)

	counters = {
		"rows": len(result.rows),
		"format_drift": result.format_drift,
		"warnings": result.warnings,
		"invoice_date": str(result.invoice_date) if result.invoice_date else None,
	}
	by_customer = Counter(r.customer_external_ref for r in result.rows)
	by_product = Counter(r.vendor_product_id for r in result.rows)
	by_billing_plan = Counter(r.billing_plan for r in result.rows)
	by_term = Counter(r.term_duration for r in result.rows)
	by_booking = Counter(r.booking_type for r in result.rows)
	doc_types = Counter(r.document_type for r in result.rows)

	sample = result.rows[0] if result.rows else None
	sample_dump = None
	if sample:
		sample_dump = {
			"customer_external_ref": sample.customer_external_ref,
			"vendor_product_id": sample.vendor_product_id,
			"qty": sample.qty,
			"amount": sample.amount,
			"period_start": str(sample.period_start) if sample.period_start else None,
			"period_end": str(sample.period_end) if sample.period_end else None,
			"subscription_external_id": sample.subscription_external_id,
			"billing_plan": sample.billing_plan,
			"term_duration": sample.term_duration,
			"booking_type": sample.booking_type,
		}

	return json.dumps({
		"counters": counters,
		"by_customer_top": by_customer.most_common(10),
		"by_product_top": by_product.most_common(10),
		"by_billing_plan": by_billing_plan,
		"by_term_duration": by_term,
		"by_booking_type": by_booking,
		"document_types": doc_types,
		"distinct_customers": len(by_customer),
		"distinct_products": len(by_product),
		"sample_first_row": sample_dump,
	}, default=str, ensure_ascii=False, indent=2)
