"""Lab Note use cases. Endpoints in lab_core/api/notes.py call these and nothing else."""

import frappe
from frappe.utils import cint

NOTE = "Lab Note"
MAX_PAGE = 100


def list_notes(start: int = 0, limit: int = 20) -> dict:
	start = max(cint(start), 0)
	limit = min(max(cint(limit), 1), MAX_PAGE)
	# get_list applies the caller's permissions. One extra row tells whether a next page exists.
	rows = frappe.get_list(
		NOTE,
		fields=["name", "title"],
		order_by="creation desc",
		limit_start=start,
		limit_page_length=limit + 1,
	)
	return {"items": rows[:limit], "has_next": len(rows) > limit}


def get_note(name: str) -> dict:
	note = frappe.get_doc(NOTE, name, check_permission="read")
	return {
		"name": note.name,
		"title": note.title,
		"content": note.content,
	}


def create_note(title: str, content: str = "") -> dict:
	note = frappe.new_doc(NOTE)
	note.title = title
	note.content = content
	note.insert()  # checks create permission
	return {"name": note.name}
