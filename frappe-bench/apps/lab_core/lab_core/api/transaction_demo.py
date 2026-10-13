"""Track A experiment: request completion decides whether an insert is kept."""

import frappe
from frappe import _

from lab_core.lab_core import notes


@frappe.whitelist(methods=["GET", "POST"])
def create_note(title: str, fail: int = 0) -> dict:
	frappe.only_for("System Manager")
	frappe.has_permission("Lab Note", "create", throw=True)
	if not title.strip():
		frappe.throw(_("A title is required for the transaction experiment."))
	if fail not in (0, 1):
		frappe.throw(_("Use fail=0 or fail=1 for the transaction experiment."))

	result = notes.create_note(title=title.strip())
	if fail:
		frappe.throw(_("Intentional error after inserting the note: this request must roll back."))
	return result
