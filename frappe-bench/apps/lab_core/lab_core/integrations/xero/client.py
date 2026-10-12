"""A stand-in for Xero, so the outbox flow can be built and tested with no outside account.

It behaves like an API with idempotency keys: the same key always gives the same invoice id.
Two note titles trigger failures on purpose:
- contains "fail":    Xero rejects the invoice; nothing is created.
- contains "timeout": the invoice IS created, but the answer never arrives (the call raises).
"""

import frappe

CACHE_PREFIX = "lab_fake_xero:"


class XeroError(Exception):
	pass


class XeroRejected(XeroError):
	"""Xero refused the request. Retrying the same data will fail again."""


class XeroTimeout(XeroError):
	"""No answer arrived. The request may or may not have been processed."""


class FakeXeroClient:
	# The "remote" store lives in the cache. Clearing the cache makes this fake forget its
	# invoices, which a real Xero would not.

	def find_by_key(self, idempotency_key: str) -> str | None:
		"""Return the id of the invoice created with this key, if any."""
		return frappe.cache.get_value(CACHE_PREFIX + idempotency_key)

	def create_invoice(self, idempotency_key: str, payload: dict) -> str:
		existing = self.find_by_key(idempotency_key)
		if existing:
			return existing

		title = (payload.get("title") or "").lower()
		if "fail" in title:
			raise XeroRejected("Xero rejected the invoice: the title contains 'fail'.")

		xero_id = "FAKE-" + frappe.generate_hash(length=10).upper()
		frappe.cache.set_value(CACHE_PREFIX + idempotency_key, xero_id)

		if "timeout" in title:
			raise XeroTimeout("No answer from Xero.")
		return xero_id


def get_client() -> FakeXeroClient:
	return FakeXeroClient()
