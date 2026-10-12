"""Xero demo fields on ERPNext documents, applied after migrate."""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def apply() -> None:
	"""Create or update the demo fields without copying Xero identities on amend."""
	create_custom_fields(
		{
			"Customer": [
				_field("lab_xero_contact_id", "Xero Contact ID", "Data", "customer_name", unique=1),
			],
			"Sales Order": [
				_field("lab_xero_section", "Xero", "Section Break", "amended_from"),
				_field(
					"lab_xero_sync_status",
					"Xero Sync Status",
					"Select",
					"lab_xero_section",
					options="Not Synced\nQueued\nSynced\nFailed",
					default="Not Synced",
				),
				_field("lab_xero_invoice_id", "Xero Invoice ID", "Data", "lab_xero_sync_status", unique=1),
				_field("lab_xero_invoice_number", "Xero Invoice Number", "Data", "lab_xero_invoice_id"),
				_field("lab_xero_invoice_status", "Xero Invoice Status", "Data", "lab_xero_invoice_number"),
				_field("lab_xero_amount_due", "Xero Amount Due", "Currency", "lab_xero_invoice_status", options="currency"),
				_field("lab_xero_amount_paid", "Xero Amount Paid", "Currency", "lab_xero_amount_due", options="currency"),
				_field("lab_xero_amount_credited", "Xero Amount Credited", "Currency", "lab_xero_amount_paid", options="currency"),
				_field("lab_xero_last_synced_at", "Xero Last Synced At", "Datetime", "lab_xero_amount_credited"),
				_field("lab_xero_error", "Xero Error", "Small Text", "lab_xero_last_synced_at"),
			],
		},
		update=True,
	)


def _field(fieldname: str, label: str, fieldtype: str, insert_after: str, **properties) -> dict:
	return {
		"fieldname": fieldname,
		"label": label,
		"fieldtype": fieldtype,
		"insert_after": insert_after,
		"read_only": 1,
		"no_copy": 1,
		"allow_on_submit": 1,
		**properties,
	}
