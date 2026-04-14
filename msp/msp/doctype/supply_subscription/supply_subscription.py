import frappe
from frappe.model.document import Document


class SupplySubscription(Document):
	def before_save(self):
		self.title = self._compose_title()

	def _compose_title(self) -> str:
		parts = [self.customer or "?", self.item_name or self.item or self.vendor_product_id or "?"]
		if self.vendor:
			parts.append(self.vendor)
		return " · ".join(p for p in parts if p)
