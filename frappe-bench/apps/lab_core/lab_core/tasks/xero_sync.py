"""Background job: send one outbox row to Xero. Runs in a worker, in its own transaction."""

import frappe
from frappe.utils import cint

from lab_core.integrations.xero.client import XeroRejected, XeroTimeout, get_client
from lab_core.lab_xero.outbox import OUTBOX


def process_outbox(outbox_name: str) -> None:
	outbox = frappe.get_doc(OUTBOX, outbox_name, for_update=True)
	if outbox.status == "Done":
		return  # a duplicate job: nothing left to do

	doc = frappe.get_doc(outbox.reference_doctype, outbox.reference_name)
	client = get_client()
	key = outbox.idempotency_key
	outbox.attempts = cint(outbox.attempts) + 1

	try:
		# Ask first: an earlier attempt may have arrived without us learning the answer.
		xero_id = client.find_by_key(key) or client.create_invoice(key, {"title": doc.title})
	except XeroTimeout:
		# Outcome unknown. Xero's answer decides, not our guess.
		xero_id = client.find_by_key(key)
		if not xero_id:
			_mark_failed(outbox, doc, "No answer from Xero and no invoice found for this key.")
			return
	except XeroRejected as e:
		_mark_failed(outbox, doc, str(e))
		return

	outbox.status = "Done"
	outbox.xero_id = xero_id
	outbox.error = None
	outbox.save()

	doc.xero_id = xero_id
	doc.sync_status = "Synced"
	doc.save()


def _mark_failed(outbox, doc, reason: str) -> None:
	"""The compensation of this flow: nothing exists in Xero, so say so on both records.
	The outbox row stays, so the attempt can be retried."""
	outbox.status = "Failed"
	outbox.error = reason
	outbox.save()

	doc.sync_status = "Failed"
	doc.save()
