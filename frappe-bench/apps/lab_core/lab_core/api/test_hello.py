from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.handler import is_valid_http_method
from frappe.tests import UnitTestCase

from lab_core.api.hello import hello


class TestHello(UnitTestCase):
    def test_get_returns_greeting_for_authenticated_callers(self):
        for user in ("Administrator", "lab-user@example.test"):
            with self.subTest(user=user), self.request_context(user, "GET"):
                frappe.is_whitelisted(hello)
                is_valid_http_method(hello)

                self.assertEqual(
                    hello(),
                    {"message": "Hello from Lab Core", "user": user},
                )

    def test_guest_is_refused_by_rpc_permission_check(self):
        with self.request_context("Guest", "GET"):
            with self.assertRaises(frappe.PermissionError):
                frappe.is_whitelisted(hello)

    def test_guest_is_refused_when_called_directly(self):
        with self.request_context("Guest", "GET"):
            with self.assertRaises(frappe.PermissionError):
                hello()

    def test_post_is_refused_for_authenticated_caller(self):
        with self.request_context("lab-user@example.test", "POST"):
            frappe.is_whitelisted(hello)

            with self.assertRaises(frappe.PermissionError):
                is_valid_http_method(hello)

    def test_request_context_restores_runner_state_after_exception(self):
        session = frappe.local.session
        user = session.user
        missing = object()
        original = {
            name: getattr(frappe.local, name, missing)
            for name in ("request", "response", "message_log")
        }

        with self.assertRaisesRegex(ValueError, "test failure"):
            with self.request_context("Guest", "GET"):
                self.assertEqual(frappe.session.user, "Guest")
                raise ValueError("test failure")

        self.assertIs(frappe.local.session, session)
        self.assertEqual(frappe.session.user, user)
        for name, value in original.items():
            with self.subTest(attribute=name):
                self.assertIs(getattr(frappe.local, name, missing), value)

    @contextmanager
    def request_context(self, user: str, method: str):
        # Exercise permission checks without creating users or HTTP sessions.
        values = {
            "request": SimpleNamespace(method=method),
            "response": frappe._dict(),
            "message_log": [],
        }
        missing = object()
        original = {name: getattr(frappe.local, name, missing) for name in values}

        # Local stores context attributes outside __dict__; restore them explicitly.
        with patch.dict(frappe.local.session, {"user": user}):
            try:
                for name, value in values.items():
                    setattr(frappe.local, name, value)
                yield
            finally:
                for name, value in original.items():
                    if value is missing:
                        delattr(frappe.local, name)
                    else:
                        setattr(frappe.local, name, value)
