"""What arrives from Xero and belongs to one of our Sales Orders.

A credit note is created by the accountant in Xero. It belongs to a Sales Order only when it
is allocated to that order's invoice. We record it as a "Lab Xero Credit Note" row and say so
once on the order's timeline. Nothing on the order itself is changed here: its amounts come
from the invoice (see lab_core/tasks/xero_pull.py).
"""

import frappe
from frappe import _
from frappe.utils import flt

SALES_ORDER = "Sales Order"
CREDIT_NOTE = "Lab Xero Credit Note"


def apply_credit_notes(credit_notes: list[dict]) -> None:
	"""Create or update one row per credit note. Safe to run again with the same data."""
	for note in credit_notes:
		allocated = _allocated_to_our_orders(note)
		existing = frappe.db.exists(CREDIT_NOTE, {"xero_credit_note_id": note["id"]})

		if not allocated:
			if existing:
				# It was allocated before and no longer is: keep the row, show the new facts.
				_save(frappe.get_doc(CREDIT_NOTE, existing), note, allocated_amount=0)
			continue  # not allocated to any invoice of ours: it is not ours to record

		# Demo scope: one credit note belongs to one order. If Xero allocated it to several
		# of our invoices, the first one (by invoice id) is recorded.
		invoice_id, order_name, amount = allocated[0]
		if existing:
			_save(frappe.get_doc(CREDIT_NOTE, existing), note, amount, order_name, invoice_id)
		else:
			_save(frappe.new_doc(CREDIT_NOTE), note, amount, order_name, invoice_id)
			_say_on_timeline(order_name, note, amount)


def _allocated_to_our_orders(note: dict) -> list[tuple[str, str, float]]:
	"""Return (invoice id, Sales Order name, amount) for allocations that hit our invoices."""
	amounts: dict[str, float] = {}
	for allocation in note["allocations"]:
		amounts[allocation["invoice_id"]] = amounts.get(allocation["invoice_id"], 0) + flt(allocation["amount"])
	if not amounts:
		return []

	orders = frappe.get_list(
		SALES_ORDER,
		filters={"lab_xero_invoice_id": ["in", list(amounts)]},
		fields=["name", "lab_xero_invoice_id"],
		order_by="lab_xero_invoice_id asc",
		limit_page_length=0,
	)
	return [(row.lab_xero_invoice_id, row.name, amounts[row.lab_xero_invoice_id]) for row in orders]


def _save(row, note: dict, allocated_amount, order_name: str | None = None, invoice_id: str | None = None) -> None:
	row.xero_credit_note_id = note["id"]
	row.credit_note_number = note["number"]
	row.status = note["status"]
	row.date = note["date"]
	row.total = flt(note["total"], row.precision("total"))
	row.allocated_amount = flt(allocated_amount, row.precision("allocated_amount"))
	if order_name:
		row.sales_order = order_name
		row.xero_invoice_id = invoice_id
	row.save()  # inserts a new row, updates an existing one


def _say_on_timeline(order_name: str, note: dict, amount) -> None:
	"""Only on the first sighting, so pulling again never repeats the comment."""
	order = frappe.get_doc(SALES_ORDER, order_name)
	order.add_comment(
		"Info",
		_("Xero credit note {0}: {1} allocated to this order's invoice.").format(
			note["number"], flt(amount, order.precision("lab_xero_amount_credited"))
		),
	)
