import frappe
from frappe.model.document import Document


class SupplySubscriptionEvent(Document):
	def before_save(self):
		# Marge berechnen, sofern beide Seiten bekannt sind
		if self.amount is not None and self.cost_amount is not None:
			self.margin_amount = float(self.amount) - float(self.cost_amount)

	def on_update(self):
		self._refresh_subscription_denormals()

	def on_trash(self):
		self._refresh_subscription_denormals()

	def _refresh_subscription_denormals(self):
		"""Aktualisiert last_event_date / last_booking_type / current_period_end
		auf der übergeordneten Supply Subscription auf Basis des letzten Events."""
		if not self.supply_subscription:
			return
		latest = frappe.db.get_all(
			"Supply Subscription Event",
			filters={"supply_subscription": self.supply_subscription},
			fields=["period_end", "booking_type", "qty"],
			order_by="period_end desc",
			limit=1,
		)
		if not latest:
			frappe.db.set_value("Supply Subscription", self.supply_subscription, {
				"last_event_date": None,
				"last_booking_type": None,
			})
			return
		row = latest[0]
		frappe.db.set_value("Supply Subscription", self.supply_subscription, {
			"last_event_date": row["period_end"],
			"last_booking_type": row["booking_type"],
			"current_period_end": row["period_end"],
			"qty_current": row.get("qty") or 0,
		})
