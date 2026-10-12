"""Errors raised by lab_core code. Each carries its HTTP status; endpoints raise them and catch nothing.

Not found and not permitted reuse Frappe's own classes (404 and 403):
frappe.DoesNotExistError, frappe.PermissionError.
"""

import frappe


class LabConflictError(frappe.ValidationError):
	"""The request is valid but the document is in a state that does not allow it."""

	http_status_code = 409
