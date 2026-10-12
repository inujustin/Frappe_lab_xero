"""Background jobs that bring Xero's truth back onto Sales Orders.

Xero owns the invoice: status, amount due, amount paid, amount credited. These jobs copy those
values into the lab_xero_* fields and never calculate anything themselves. Every write overwrites
with Xero's current value, so running a pull twice gives the same result.
"""

import datetime
from zoneinfo import ZoneInfo

import frappe
from frappe.utils import add_to_date, flt, get_datetime, get_system_timezone, now_datetime

from lab_core.integrations.xero.client import get_client
from lab_core.lab_xero import inbound

SALES_ORDER = "Sales Order"
SETTINGS = "Lab Xero Settings"
# Ask Xero for a little more than strictly needed: clocks differ, and re-reading is harmless.
OVERLAP_SECONDS = 120


def pull_sales_order(sales_order: str) -> None:
	"""Refresh one order from Xero. Queued by the "Refresh from Xero" button."""
	client = get_client()  # first: a token refresh inside it may commit
	invoice_id = frappe.get_doc(SALES_ORDER, sales_order).lab_xero_invoice_id
	if not invoice_id:
		return  # nothing in Xero to read yet

	_apply_invoices(client.get_invoices(ids=[invoice_id]))
	# Credit notes cannot be asked for by invoice, so read them all; only ours are recorded.
	inbound.apply_credit_notes(client.get_credit_notes())


def pull_changes() -> None:
	"""Refresh every order whose Xero invoice changed since the last pull. Run by the scheduler."""
	client = get_client()  # first: a token refresh inside it may commit
	settings = frappe.get_doc(SETTINGS)
	started = now_datetime()

	if settings.last_pull_at:
		since = _xero_utc(settings.last_pull_at)
		invoices = client.get_invoices(modified_since=since)
		credit_notes = client.get_credit_notes(modified_since=since)
	else:
		# First pull: read only the invoices we created, not the whole organisation.
		invoices = client.get_invoices(ids=_known_invoice_ids())
		credit_notes = client.get_credit_notes()
	_apply_invoices(invoices)
	inbound.apply_credit_notes(credit_notes)
	# An allocation changes the invoice's credited and due amounts. Read those invoices again
	# by id, in case Xero does not report them as modified on their own.
	credited_ids = sorted({a["invoice_id"] for note in credit_notes for a in note["allocations"]})
	_apply_invoices(client.get_invoices(ids=credited_ids))

	# The pointer moves only now, in the same transaction as the updates above:
	# if anything failed before this line, the next run starts from the old pointer.
	settings.last_pull_at = started
	settings.save()


def _apply_invoices(invoices: list[dict]) -> None:
	"""Overwrite the Xero fields of each order that owns one of these invoices."""
	by_id = {invoice["id"]: invoice for invoice in invoices}
	if not by_id:
		return

	orders = frappe.get_list(
		SALES_ORDER,
		filters={"lab_xero_invoice_id": ["in", list(by_id)]},
		fields=["name", "lab_xero_invoice_id"],
		limit_page_length=0,
	)
	for row in orders:
		invoice = by_id[row.lab_xero_invoice_id]
		order = frappe.get_doc(SALES_ORDER, row.name)
		# The order is submitted (or cancelled): only its allow-on-submit fields change, by db_set.
		order.db_set(
			{
				"lab_xero_invoice_number": invoice["number"],
				"lab_xero_invoice_status": invoice["status"],
				"lab_xero_amount_due": _money(order, "lab_xero_amount_due", invoice["amount_due"]),
				"lab_xero_amount_paid": _money(order, "lab_xero_amount_paid", invoice["amount_paid"]),
				"lab_xero_amount_credited": _money(order, "lab_xero_amount_credited", invoice["amount_credited"]),
				"lab_xero_last_synced_at": now_datetime(),
			}
		)


def _known_invoice_ids() -> list[str]:
	rows = frappe.get_list(
		SALES_ORDER,
		filters={"lab_xero_invoice_id": ["is", "set"]},
		fields=["lab_xero_invoice_id"],
		limit_page_length=0,
	)
	return [row.lab_xero_invoice_id for row in rows]


def _money(order, fieldname: str, value) -> float:
	return flt(value, order.precision(fieldname))


def _xero_utc(site_time) -> str:
	"""Turn a datetime stored in the site's time zone into the UTC text Xero expects."""
	local = get_datetime(add_to_date(site_time, seconds=-OVERLAP_SECONDS))
	utc = local.replace(tzinfo=ZoneInfo(get_system_timezone())).astimezone(datetime.UTC)
	return utc.strftime("%Y-%m-%dT%H:%M:%S")
