import frappe
from frappe import _
from frappe.model.document import Document


class LicenseCoverage(Document):
	def validate(self):
		self._validate_period()
		self._warn_on_duplicate_items()

	def _validate_period(self):
		if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
			frappe.throw(_("Valid From darf nicht nach Valid To liegen."))

	def _warn_on_duplicate_items(self):
		seen: set[str] = set()
		for row in self.coverage_items or []:
			if row.item in seen:
				# Mehrere Zeilen für dasselbe Item innerhalb eines Records sind erlaubt
				# (z. B. unterschiedliche Notizen), werden beim Lookup summiert — aber als
				# Hinweis ausgeben, damit der Anwender das bewusst tut.
				frappe.msgprint(
					_("Item {0} kommt mehrfach in diesem Coverage-Record vor — Mengen werden beim Import summiert.").format(row.item),
					alert=True,
				)
				return
			seen.add(row.item)
