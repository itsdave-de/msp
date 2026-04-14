from frappe.model.document import Document


class SupplierImportProfile(Document):
	def validate(self):
		if self.default_output_mode == "Delivery Note" and not self.default_warehouse:
			from frappe import throw, _
			throw(_('Für Output Mode „Delivery Note“ muss ein Default Warehouse gesetzt sein.'))
