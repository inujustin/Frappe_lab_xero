import unittest

import frappe
from frappe.tests import IntegrationTestCase, set_user

from lab_core.api.notes import create_note, get_note, list_notes

LAB_USER = "lab-user@example.test"
OUTSIDER = "lab-outsider@example.test"


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


class TestNotes(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# The role and its permission rows on Lab Note are made in Desk.
		if not frappe.db.exists("Role", "Lab User"):
			raise unittest.SkipTest("Role 'Lab User' is missing: do the Desk preparation of docs/plan/SPRINT.md")
		ensure_user(LAB_USER, ["Lab User"])
		ensure_user(OUTSIDER, [])

	def test_user_without_the_role_cannot_list(self):
		with set_user(OUTSIDER), self.assertRaises(frappe.PermissionError):
			list_notes()

	def test_user_without_the_role_cannot_create(self):
		with set_user(OUTSIDER), self.assertRaises(frappe.PermissionError):
			create_note(title="not allowed")

	def test_user_without_the_role_cannot_read(self):
		with set_user(LAB_USER):
			name = create_note(title="private")["name"]
		with set_user(OUTSIDER), self.assertRaises(frappe.PermissionError):
			get_note(name)

	def test_lab_user_creates_and_lists(self):
		with set_user(LAB_USER):
			name = create_note(title="hello", content="body")["name"]
			note = get_note(name)
			listed = [row["name"] for row in list_notes()["items"]]

		self.assertEqual(note["title"], "hello")
		self.assertEqual(note["content"], "body")
		self.assertIn(name, listed)
