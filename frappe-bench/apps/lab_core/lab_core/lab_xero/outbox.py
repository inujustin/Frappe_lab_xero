"""The outbox: a row written in the same transaction as the business change, saying
"this still has to reach Xero". A background job reads it after the commit."""

import frappe

OUTBOX = "Lab Xero Outbox"
SYNC_JOB = "lab_core.tasks.xero_sync.process_outbox"


def queue(doc, operation: str = "create_invoice") -> str:
	"""Write (or reopen) the outbox row for this document and queue the job. Return the row's name.

	The idempotency key is fixed per document and operation, so a retry reuses the same row
	and Xero sees the same key.
	"""
	key = f"{doc.doctype}:{doc.name}:{operation}"
	name = frappe.db.exists(OUTBOX, {"idempotency_key": key})
	if name:
		outbox = frappe.get_doc(OUTBOX, name, for_update=True)
		outbox.status = "Pending"
		outbox.error = None
		outbox.save()
	else:
		outbox = frappe.new_doc(OUTBOX)
		outbox.reference_doctype = doc.doctype
		outbox.reference_name = doc.name
		outbox.operation = operation
		outbox.idempotency_key = key
		outbox.status = "Pending"
		outbox.insert()

	# After the commit: the worker must be able to see the row and the document.
	frappe.enqueue(
		SYNC_JOB,
		queue="default",
		enqueue_after_commit=True,
		job_id=f"lab-xero-sync:{outbox.name}",
		deduplicate=True,
		outbox_name=outbox.name,
	)
	return outbox.name
