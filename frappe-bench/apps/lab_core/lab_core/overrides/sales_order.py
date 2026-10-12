"""Sales Order event handlers for the Xero demo. No HTTP calls in the request."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from lab_core.errors import LabConflictError
from lab_core.lab_xero import outbox


def on_submit(doc: Document, method: str | None = None) -> None:
	if doc.docstatus != 1:
		return
	doc.db_set({"lab_xero_sync_status": "Queued", "lab_xero_error": None})
	outbox.queue(doc, operation="create_invoice")


def on_cancel(doc: Document, method: str | None = None) -> None:
	if doc.docstatus != 2:
		return
	if flt(doc.lab_xero_amount_paid, doc.precision("lab_xero_amount_paid")) > 0:
		frappe.throw(
			_("Cannot cancel Sales Order {0}: its Xero invoice has payments applied.").format(doc.name),
			LabConflictError,
		)
	if flt(doc.lab_xero_amount_credited, doc.precision("lab_xero_amount_credited")) > 0:
		frappe.throw(
			_("Cannot cancel Sales Order {0}: its Xero invoice has credit applied.").format(doc.name),
			LabConflictError,
		)

	doc.db_set({"lab_xero_sync_status": "Queued", "lab_xero_error": None})
	outbox.queue(doc, operation="void_invoice")
