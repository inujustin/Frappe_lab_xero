"""Xero buttons of the Sales Order form. Thin on purpose: permission, state check, queue a job.

Nothing here calls Xero. Both endpoints only put work on the queue; the jobs under
lab_core/tasks/ talk to Xero after this request has committed.
"""

import frappe
from frappe import _

from lab_core.errors import LabConflictError
from lab_core.lab_xero import outbox

SALES_ORDER = "Sales Order"
PULL_JOB = "lab_core.tasks.xero_pull.pull_sales_order"

SUBMITTED = 1
CANCELLED = 2


@frappe.whitelist(methods=["POST"])
def retry_sync(sales_order: str) -> dict:
	"""Queue the outbound sync of this order again: the invoice if the order is submitted,
	the void if it is cancelled."""
	doc = frappe.get_doc(SALES_ORDER, sales_order, check_permission="write")

	if doc.docstatus not in (SUBMITTED, CANCELLED):
		frappe.throw(
			_("Sales Order {0} is a draft. Only a submitted order goes to Xero.").format(sales_order),
			LabConflictError,
		)
	if doc.lab_xero_sync_status == "Synced":
		frappe.throw(
			_("Sales Order {0} is already synced to Xero.").format(sales_order),
			LabConflictError,
		)

	operation = "void_invoice" if doc.docstatus == CANCELLED else "create_invoice"
	# The order is submitted, so only its allow-on-submit Xero fields may change: db_set, not save.
	doc.db_set({"lab_xero_sync_status": "Queued", "lab_xero_error": None})
	outbox.queue(doc, operation=operation)
	return {"queued": True}


@frappe.whitelist(methods=["POST"])
def refresh(sales_order: str) -> dict:
	"""Queue a pull of this order's invoice status and credit notes from Xero."""
	doc = frappe.get_doc(SALES_ORDER, sales_order, check_permission="write")

	if not doc.lab_xero_invoice_id:
		frappe.throw(
			_("Sales Order {0} has no Xero invoice yet, so there is nothing to refresh.").format(sales_order),
			LabConflictError,
		)

	frappe.enqueue(
		PULL_JOB,
		queue="default",
		enqueue_after_commit=True,
		job_id=f"lab-xero-pull:{doc.name}",
		deduplicate=True,
		sales_order=doc.name,
	)
	return {"queued": True}
