"""Xero tenant discovery and outbound Sales Order jobs."""

from decimal import Decimal, InvalidOperation
from hashlib import sha256

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, now_datetime

from lab_core.integrations.xero.client import XeroBusy, XeroClient, XeroError, XeroRejected, get_client
from lab_core.lab_xero.mapping import customer_to_contact, sales_order_to_invoice
from lab_core.lab_xero.outbox import OUTBOX


def discover_tenant(tenant_id: str | None = None) -> None:
	"""Store the sole connected organisation, or an explicitly selected tenant."""
	frappe.only_for("System Manager")
	settings = frappe.get_doc("Lab Xero Settings", check_permission="write")
	try:
		# Token refresh can commit; do all local writes after the HTTP call.
		connections = get_client(require_tenant=False).get_connections()
		organisations = [row for row in connections if row.get("tenantType") == "ORGANISATION"]
		settings.reload()
		settings.check_permission("write")
		if tenant_id and settings.tenant_id and tenant_id != settings.tenant_id:
			frappe.throw(_("Tenant discovery cannot replace an existing Xero organisation."))
		selected_id = tenant_id or settings.tenant_id
		matches = organisations
		if selected_id:
			matches = [row for row in organisations if row.get("tenantId") == selected_id]
		if len(matches) != 1:
			frappe.throw(_("Expected one connected Xero organisation. If several are connected, pass its tenant_id explicitly."))
		connection = matches[0]
		if not connection.get("tenantId") or not connection.get("tenantName"):
			frappe.throw(_("Xero did not return the organisation ID and name."))
		settings.tenant_id = connection["tenantId"]
		settings.tenant_name = connection["tenantName"]
		settings.save()
	except Exception:
		frappe.log_error(title="Xero tenant discovery failed", message="Tenant discovery failed; inspect the failed background job and retry after correcting the connection.")
		raise


def process_outbox(outbox_name: str) -> None:
	if frappe.get_doc(OUTBOX, outbox_name, check_permission="write").status == "Done":
		return
	try:
		client = get_client()  # Refresh before any lock or business write: refresh may commit.
		outbox = frappe.get_doc(OUTBOX, outbox_name, for_update=True, check_permission="write")
		if outbox.status == "Done":
			return
		if outbox.reference_doctype != "Sales Order":
			frappe.throw(_("Only Sales Orders are supported by the Xero outbox."))
		doc = frappe.get_doc("Sales Order", outbox.reference_name, for_update=True, check_permission="write")
		outbox.attempts = cint(outbox.attempts) + 1
		if outbox.operation == "create_invoice":
			invoice_id = _create_invoice(client, doc, outbox.idempotency_key)
		elif outbox.operation == "void_invoice":
			invoice_id = _void_invoice(client, doc, outbox.idempotency_key)
		else:
			frappe.throw(_("Unsupported Xero outbox operation: {0}.").format(outbox.operation))
		outbox.status = "Done"
		outbox.xero_id = invoice_id
		outbox.error = None
		outbox.save()
	except Exception as error:
		# Remote writes cannot roll back. Retry recovers them by number before creating.
		frappe.db.rollback()
		_record_failure(outbox_name, _failure_reason(error))
		frappe.log_error(title="Xero outbound sync failed", message="Sales Order sync failed; see the outbox error and retry after correcting it.")
		raise


def _create_invoice(client: XeroClient, doc: Document, key: str) -> str | None:
	if doc.docstatus == 2:
		return None  # Cancel won before this job: leave the void job's status alone.
	if doc.docstatus != 1:
		frappe.throw(_("Only a submitted Sales Order can create a Xero invoice."))
	invoice_id = _find_invoice(client, doc)
	if not invoice_id:
		settings = frappe.get_doc("Lab Xero Settings")
		customer = frappe.get_doc("Customer", doc.customer, for_update=True, check_permission="write")
		# Validate the invoice before creating a contact in Xero.
		payload = sales_order_to_invoice(doc, "pending-contact", settings)
		contact_id = client.find_contact(customer.name)
		if customer.lab_xero_contact_id and customer.lab_xero_contact_id != contact_id:
			frappe.throw(_("The saved Xero contact does not match the Customer lookup."))
		if not contact_id:
			contact_id = client.create_contact(_key(f"Customer:{customer.name}:create_contact"), customer_to_contact(customer))
		customer.db_set("lab_xero_contact_id", contact_id)
		payload["Contact"]["ContactID"] = contact_id
		invoice_id = client.create_invoice(_key(key), payload)
	invoice = _read_invoice(client, doc, invoice_id)
	if invoice["status"] not in ("AUTHORISED", "PAID"):
		frappe.throw(_("The Xero invoice is not approved or paid; its state is outside this demo."))
	_save_invoice(doc, invoice)
	return invoice_id


def _void_invoice(client: XeroClient, doc: Document, key: str) -> str | None:
	if doc.docstatus != 2:
		frappe.throw(_("Only a cancelled Sales Order can void its Xero invoice."))
	invoice_id = _find_invoice(client, doc)
	if not invoice_id:
		# The create job also locks this order and skips cancelled orders.
		doc.db_set({"lab_xero_sync_status": "Synced", "lab_xero_error": None})
		return None
	client.void_invoice(_key(key), invoice_id)
	invoice = _read_invoice(client, doc, invoice_id)
	if invoice["status"] != "VOIDED":
		frappe.throw(_("Xero has not confirmed that the invoice is voided."))
	_save_invoice(doc, invoice)
	return invoice_id


def _find_invoice(client: XeroClient, doc: Document) -> str | None:
	invoice_id = client.find_invoice(doc.name)
	if doc.lab_xero_invoice_id and doc.lab_xero_invoice_id != invoice_id:
		frappe.throw(_("The saved Xero invoice does not match the Sales Order number lookup."))
	return invoice_id


def _read_invoice(client: XeroClient, doc: Document, invoice_id: str) -> dict:
	rows = client.get_invoices(ids=[invoice_id])
	if len(rows) != 1 or rows[0]["id"] != invoice_id or rows[0]["number"] != doc.name:
		raise XeroRejected("Xero did not return the invoice belonging to this Sales Order.")
	return rows[0]


def _save_invoice(doc: Document, invoice: dict) -> None:
	values = {
		"lab_xero_invoice_id": invoice["id"],
		"lab_xero_invoice_number": invoice["number"],
		"lab_xero_invoice_status": invoice["status"],
		"lab_xero_sync_status": "Synced",
		"lab_xero_error": None,
		"lab_xero_last_synced_at": now_datetime(),
	}
	for field in ("amount_due", "amount_paid", "amount_credited"):
		value = invoice[field]
		try:
			valid = Decimal(str(value)).is_finite()
		except InvalidOperation:
			valid = False
		if not valid:
			raise XeroRejected("Xero returned an invalid invoice amount; no amount was saved.")
		values["lab_xero_" + field] = flt(value, doc.precision("lab_xero_" + field))
	doc.db_set(values)


def _record_failure(outbox_name: str, reason: str) -> None:
	outbox = frappe.get_doc(OUTBOX, outbox_name, for_update=True, check_permission="write")
	if outbox.status == "Done":
		return  # Another worker completed it after rollback released the lock.
	outbox.attempts = cint(outbox.attempts) + 1
	outbox.status = "Failed"
	outbox.error = reason
	outbox.save()
	if outbox.reference_doctype == "Sales Order":
		doc = frappe.get_doc("Sales Order", outbox.reference_name, for_update=True, check_permission="write")
		if not (outbox.operation == "create_invoice" and doc.docstatus == 2):
			doc.db_set({"lab_xero_sync_status": "Failed", "lab_xero_error": reason})
	# Preserve failure indicators before re-raising into the worker's rollback.
	frappe.db.commit()


def _failure_reason(error: Exception) -> str:
	if isinstance(error, XeroBusy):
		if error.retry_after is not None:
			return _("Xero is busy. Retry after {0} seconds.").format(error.retry_after)
		return _("Xero is busy. Retry later.")
	if isinstance(error, (XeroError, frappe.ValidationError)):
		return str(error)
	return _("Xero sync failed unexpectedly. Ask a System Manager to inspect the failed job before retrying.")


def _key(value: str) -> str:
	return sha256(value.encode()).hexdigest()
