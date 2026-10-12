import unittest

import frappe
from frappe.tests import IntegrationTestCase, set_user

from lab_core.api.notes import create_note, get_note, list_notes, retry_sync
from lab_core.errors import LabConflictError
from lab_core.tasks.xero_sync import process_outbox

LAB_USER = "lab-user@example.test"
OUTSIDER = "lab-outsider@example.test"
OUTBOX = "Lab Xero Outbox"


def ensure_user(email: str, roles: list[str]) -> None:
	if frappe.db.exists("User", email):
		return
	user = frappe.new_doc("User")
	user.email = email
	user.first_name = email.split("@", 1)[0]
	user.send_welcome_email = 0
	for role in roles:
		user.append("roles", {"role": role})
	user.insert()


def outbox_of(note_name: str):
	name = frappe.db.exists(OUTBOX, {"reference_doctype": "Lab Note", "reference_name": note_name})
	return frappe.get_doc(OUTBOX, name)


class TestNotes(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# The role and its permission rows on Lab Note and Lab Xero Outbox are made in Desk.
		if not frappe.db.exists("Role", "Lab User"):
			raise unittest.SkipTest("Role 'Lab User' is missing: do the Desk preparation of docs/plan/SPRINT.md")
		ensure_user(LAB_USER, ["Lab User"])
		ensure_user(OUTSIDER, [])

	# --- who may call ---

	def test_user_without_the_role_cannot_list(self):
		with set_user(OUTSIDER), self.assertRaises(frappe.PermissionError):
			list_notes()

	def test_user_without_the_role_cannot_create(self):
		with set_user(OUTSIDER), self.assertRaises(frappe.PermissionError):
			create_note(title="not allowed")

	def test_user_without_the_role_cannot_read_or_retry(self):
		with set_user(LAB_USER):
			name = create_note(title="private")["name"]
		with set_user(OUTSIDER):
			with self.assertRaises(frappe.PermissionError):
				get_note(name)
			with self.assertRaises(frappe.PermissionError):
				retry_sync(name)

	def test_lab_user_creates_and_lists(self):
		with set_user(LAB_USER):
			name = create_note(title="hello", content="body")["name"]
			note = get_note(name)
			listed = [row["name"] for row in list_notes()["items"]]

		self.assertEqual(note["sync_status"], "Queued")
		self.assertIn(name, listed)
		self.assertEqual(outbox_of(name).status, "Pending")

	# --- the sync job ---

	def test_same_outbox_row_twice_gives_one_xero_id(self):
		with set_user(LAB_USER):
			name = create_note(title="invoice me")["name"]
			outbox = outbox_of(name)
			process_outbox(outbox.name)
			first = get_note(name)
			process_outbox(outbox.name)
			second = get_note(name)

		self.assertEqual(first["sync_status"], "Synced")
		self.assertTrue(first["xero_id"])
		self.assertEqual(first["xero_id"], second["xero_id"])
		self.assertEqual(outbox_of(name).attempts, 1)

	def test_timeout_still_ends_with_one_xero_id(self):
		with set_user(LAB_USER):
			name = create_note(title="timeout case")["name"]
			process_outbox(outbox_of(name).name)
			note = get_note(name)

		self.assertEqual(note["sync_status"], "Synced")
		self.assertEqual(note["xero_id"], outbox_of(name).xero_id)

	def test_rejected_note_fails_then_retry_works(self):
		with set_user(LAB_USER):
			name = create_note(title="please fail")["name"]
			process_outbox(outbox_of(name).name)
			self.assertEqual(get_note(name)["sync_status"], "Failed")
			self.assertEqual(outbox_of(name).status, "Failed")

			note = frappe.get_doc("Lab Note", name)
			note.title = "fixed"
			note.save()
			self.assertEqual(retry_sync(name), {"queued": True})
			process_outbox(outbox_of(name).name)
			self.assertEqual(get_note(name)["sync_status"], "Synced")

	def test_retry_on_a_synced_note_is_a_conflict(self):
		with set_user(LAB_USER):
			name = create_note(title="done already")["name"]
			process_outbox(outbox_of(name).name)
			with self.assertRaises(LabConflictError):
				retry_sync(name)
