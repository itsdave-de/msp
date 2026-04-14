import frappe
from frappe.model.document import Document


class SupplierImportRun(Document):
	@frappe.whitelist()
	def do_import(self):
		"""Delegiert den eigentlichen Import an msp.importers.run_orchestrator.
		Die Implementation folgt in Phase 1; hier nur die Einstiegsstelle."""
		from msp.importers.run_orchestrator import execute_run
		return execute_run(self)
