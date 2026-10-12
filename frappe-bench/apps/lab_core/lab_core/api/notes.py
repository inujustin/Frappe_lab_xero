"""Lab Note endpoints for the SPA. Thin on purpose: permission, then the use case."""

import frappe

from lab_core.lab_core import notes


@frappe.whitelist(methods=["GET"])
def list_notes(start: int = 0, limit: int = 20) -> dict:
	frappe.has_permission("Lab Note", "read", throw=True)
	return notes.list_notes(start=start, limit=limit)


@frappe.whitelist(methods=["GET"])
def get_note(name: str) -> dict:
	frappe.has_permission("Lab Note", "read", throw=True)
	return notes.get_note(name)


@frappe.whitelist(methods=["POST"])
def create_note(title: str, content: str = "") -> dict:
	frappe.has_permission("Lab Note", "create", throw=True)
	return notes.create_note(title=title, content=content)
