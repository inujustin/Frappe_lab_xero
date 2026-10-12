"""Payloads for the demo: ERPNext owns lines; Xero owns tax and totals."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, strip_html


def customer_to_contact(customer: Document) -> dict:
	if not customer.name or not customer.customer_name:
		frappe.throw(_("Customer code and name are required for Xero."))
	return {"ContactNumber": customer.name, "Name": customer.customer_name}


def sales_order_to_invoice(doc: Document, contact_id: str, settings: Document) -> dict:
	if doc.docstatus != 1:
		frappe.throw(_("Only a submitted Sales Order can create a Xero invoice."))
	if not contact_id or not doc.currency or not doc.transaction_date or not doc.items:
		frappe.throw(_("Contact, currency, order date and lines are required for Xero."))
	if not settings.default_account_code or not settings.default_tax_type:
		frappe.throw(_("Set the Xero revenue account and tax type before syncing."))
	if doc.taxes:
		frappe.throw(_("The Xero demo supports Sales Orders without ERPNext taxes or charges."))
	if _has_discount(doc):
		frappe.throw(_("The Xero demo supports Sales Orders without discounts."))
	company = frappe.get_doc("Company", doc.company, check_permission="read")
	if doc.currency != company.default_currency:
		frappe.throw(_("The Xero demo requires the Sales Order to use the Company currency."))

	date = getdate(doc.transaction_date).isoformat()
	return {
		"Type": "ACCREC",
		"Contact": {"ContactID": contact_id},
		"InvoiceNumber": doc.name,
		"Date": date,
		"DueDate": date,
		"CurrencyCode": doc.currency,
		"LineAmountTypes": "Exclusive",
		"Status": "AUTHORISED",
		"LineItems": [_line_item(item, settings) for item in doc.items],
	}


def _has_discount(doc: Document, fields: tuple[str, ...] = ("discount_amount", "additional_discount_percentage")) -> bool:
	return any(abs(flt(doc.get(field), doc.precision(field))) > 0
		for field in fields)


def _line_item(item: Document, settings: Document) -> dict:
	if _has_discount(item, ("discount_amount", "discount_percentage")):
		frappe.throw(_("The Xero demo supports Sales Order lines without discounts."))
	quantity = flt(item.qty, item.precision("qty"))
	rate = flt(item.rate, min(item.precision("rate") or 2, 4))
	# Many items have no description; the item name (or code) is what the customer should read then.
	description = strip_html(item.description or "").strip() or (item.item_name or item.item_code or "").strip()
	if quantity <= 0 or rate < 0 or not description:
		frappe.throw(_("Xero invoice lines require a description, positive quantity and nonnegative rate."))
	return {
		"Description": description,
		"Quantity": quantity,
		"UnitAmount": rate,
		"AccountCode": settings.default_account_code,
		"TaxType": settings.default_tax_type,
	}
