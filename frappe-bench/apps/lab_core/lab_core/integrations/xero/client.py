"""Xero Accounting API client. Call only from background jobs."""

import json
import re
from urllib.parse import quote

import frappe
import requests
from frappe.utils import add_to_date, getdate

API_URL = "https://api.xero.com/api.xro/2.0/"
HTTP_TIMEOUT = (10, 30)


def get_client(*, require_tenant: bool = True) -> "XeroClient":
	"""Obtain before taking outbox locks: Frappe's token refresh can commit."""
	settings = frappe.get_doc("Lab Xero Settings")
	if not settings.connected_app or not settings.connected_user:
		raise XeroAuthLost("Xero connection settings are incomplete; ask a System Manager to connect Xero.")
	if require_tenant and not settings.tenant_id:
		raise XeroAuthLost("Xero tenant is not configured; run the tenant discovery job first.")
	app = frappe.get_doc("Connected App", settings.connected_app)
	token = app.get_active_token(user=settings.connected_user)
	if not token:
		raise XeroAuthLost("Xero authorization is unavailable; reconnect Xero.")
	try:
		headers = token.get_auth_header()
	except frappe.DoesNotExistError:
		raise XeroAuthLost("Xero access token is missing; reconnect Xero.") from None
	return XeroClient(settings.tenant_id, headers)


class XeroError(Exception):
	pass


class XeroRejected(XeroError):
	"""Xero refused the request. Retrying the same data will fail again."""


class XeroTimeout(XeroError):
	"""No answer arrived. The request may or may not have been processed."""


class XeroBusy(XeroError):
	def __init__(self, retry_after: int | None = None):
		self.retry_after = retry_after
		super().__init__("Xero is busy; retry later.")


class XeroAuthLost(XeroError):
	"""The saved connection cannot authorize this request."""


class XeroClient:
	def __init__(self, tenant_id: str | None, auth_headers: dict):
		self.headers = {**auth_headers, "Accept": "application/json"}
		if tenant_id:
			self.headers["xero-tenant-id"] = tenant_id

	def get_connections(self) -> list[dict]:
		"""Discover authorized tenants without needing a tenant header first."""
		return self._request("GET", "connections", None)

	def find_contact(self, contact_number: str) -> str | None:
		return self._find("Contacts", "ContactNumber", contact_number, "ContactID")

	def create_contact(self, key: str, payload: dict) -> str:
		return self._create("Contacts", "ContactID", key, payload)

	def find_invoice(self, invoice_number: str) -> str | None:
		return self._find("Invoices", "InvoiceNumber", invoice_number, "InvoiceID", 'Type=="ACCREC"')

	def create_invoice(self, key: str, payload: dict) -> str:
		return self._create("Invoices", "InvoiceID", key, payload)

	def void_invoice(self, key: str, invoice_id: str) -> None:
		path = "Invoices/" + quote(invoice_id, safe="")
		rows = self._request("GET", path, "Invoices")
		if len(rows) != 1 or rows[0].get("InvoiceID") != invoice_id:
			raise XeroRejected("Xero invoice was not found.")
		if rows[0].get("Status") == "VOIDED":
			return
		rows = self._request("POST", path, "Invoices", key=key,
			payload={"Invoices": [{"InvoiceID": invoice_id, "Status": "VOIDED"}]})
		if len(rows) != 1 or rows[0].get("Status") != "VOIDED":
			raise XeroTimeout("Xero did not confirm that the invoice was voided; look it up before retrying.")

	def get_invoices(self, ids: list[str] | None = None, modified_since: str | None = None) -> list[dict]:
		"""modified_since must be an ISO UTC timestamp, not the site's local time."""
		if ids is not None and modified_since is not None:
			raise XeroRejected("Use invoice IDs or modified_since, not both.")
		if ids == []:
			return []
		params = {"where": 'Type=="ACCREC"'}
		if ids is not None:
			params["IDs"] = ",".join(ids)
		rows = self._pages("Invoices", params, modified_since)
		try:
			return [{"id": row["InvoiceID"], "number": row["InvoiceNumber"], "status": row["Status"],
				"amount_due": row["AmountDue"], "amount_paid": row["AmountPaid"],
				"amount_credited": row["AmountCredited"]} for row in rows]
		except KeyError:
			raise XeroTimeout("Xero returned incomplete invoice data; no amounts should be saved.") from None

	def get_credit_notes(self, modified_since: str | None = None) -> list[dict]:
		"""Return sales credit notes, with amounts copied directly from Xero."""
		rows = self._pages("CreditNotes", {"where": 'Type=="ACCRECCREDIT"'}, modified_since)
		try:
			return [{"id": row["CreditNoteID"], "number": row["CreditNoteNumber"],
				"status": row["Status"], "date": _xero_date(row["Date"]), "total": row["Total"],
				"allocations": [{"invoice_id": allocation["Invoice"]["InvoiceID"],
					"amount": allocation["Amount"]} for allocation in row["Allocations"]
					if not allocation.get("IsDeleted")]} for row in rows]
		except (KeyError, ValueError, TypeError):
			raise XeroTimeout("Xero returned incomplete credit note data; no allocations should be saved.") from None

	def _find(self, resource: str, field: str, value: str, id_field: str, extra: str = "") -> str | None:
		if not value:
			raise XeroRejected("A Xero lookup requires a nonempty identifier.")
		where = f"{field}=={json.dumps(value)}"
		if extra:
			where += " AND " + extra
		rows = self._request("GET", resource, resource, params={"where": where, "page": 1})
		if not rows:
			return None
		if len(rows) != 1 or not rows[0].get(id_field) or rows[0].get(field) != value:
			raise XeroRejected("Xero lookup did not return one matching record.")
		return rows[0][id_field]

	def _create(self, resource: str, id_field: str, key: str, payload: dict) -> str:
		# PUT creates; POST may update an existing record. The job must look up before creating.
		params = {"unitdp": 4} if resource == "Invoices" else None
		rows = self._request("PUT", resource, resource, key=key, payload={resource: [payload]}, params=params)
		if len(rows) != 1 or not rows[0].get(id_field):
			raise XeroTimeout("Xero did not confirm the created record; look it up before retrying.")
		return rows[0][id_field]

	def _pages(self, resource: str, params: dict, modified_since: str | None) -> list[dict]:
		rows = []
		page = 1
		while True:
			batch = self._request("GET", resource, resource,
				params={**params, "page": page}, modified_since=modified_since)
			if not batch:
				return rows
			rows.extend(batch)
			page += 1

	def _request(self, method: str, path: str, resource: str | None, *, params: dict | None = None,
		payload: dict | None = None, key: str | None = None, modified_since: str | None = None) -> list[dict]:
		headers = dict(self.headers)
		url = API_URL + path
		if resource is None:
			url = "https://api.xero.com/connections"
			headers.pop("xero-tenant-id", None)
		elif "xero-tenant-id" not in headers:
			raise XeroAuthLost("Xero tenant is not configured; run the tenant discovery job first.")
		if key is not None:
			if not key or len(key) > 128:
				raise XeroRejected("Xero idempotency key must contain 1 to 128 characters.")
			headers["Idempotency-Key"] = key
		if modified_since:
			headers["If-Modified-Since"] = modified_since
		try:
			response = requests.request(method, url, headers=headers, params=params,
				json=payload, timeout=HTTP_TIMEOUT, allow_redirects=False)
		except requests.exceptions.RequestException:
			raise XeroTimeout("No reliable response from Xero; look up the record before retrying a write.") from None
		if response.status_code in (401, 403):
			raise XeroAuthLost("Xero authorization was refused; check access and reconnect Xero.")
		if response.status_code == 429 or response.status_code >= 500:
			retry_after = response.headers.get("Retry-After", "")
			raise XeroBusy(int(retry_after) if retry_after.isdigit() else None)
		try:
			body = response.json()
		except ValueError:
			raise XeroTimeout("Xero returned an unreadable response; look up before retrying a write.") from None
		if resource is None:
			if not 200 <= response.status_code < 300:
				raise XeroRejected(f"Xero refused tenant discovery (HTTP {response.status_code}).")
			if not isinstance(body, list) or any(not isinstance(row, dict) for row in body):
				raise XeroTimeout("Xero returned an unexpected connections response.")
			return body
		if not isinstance(body, dict):
			raise XeroTimeout("Xero returned an unexpected response.")
		rows = body.get(resource, [])
		elements = body.get("Elements", [])
		if not isinstance(rows, list) or not isinstance(elements, list):
			raise XeroTimeout("Xero returned an unexpected record collection.")
		messages = _validation_messages(elements + rows)
		if messages:
			raise XeroRejected("; ".join(messages))
		if not 200 <= response.status_code < 300:
			raise XeroRejected(f"Xero refused the request (HTTP {response.status_code}).")
		rows = body.get(resource)
		if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
			raise XeroTimeout("Xero response is missing the expected records.")
		return rows


def _validation_messages(rows: list[dict]) -> list[str]:
	messages = []
	for row in rows:
		if not isinstance(row, dict):
			raise XeroTimeout("Xero returned an unexpected record.")
		errors = row.get("ValidationErrors", [])
		if not isinstance(errors, list):
			raise XeroTimeout("Xero returned unreadable validation errors.")
		for error in errors:
			if not isinstance(error, dict) or not isinstance(error.get("Message"), str):
				raise XeroTimeout("Xero returned unreadable validation errors.")
			messages.append(error["Message"])
	return messages


def _xero_date(value: str) -> str:
	match = re.fullmatch(r"/Date\((-?\d+)(?:[+-]\d{4})?\)/", value)
	if match:
		value = add_to_date("1970-01-01 00:00:00", seconds=int(match[1]) / 1000, as_string=True)
	date = getdate(value)
	if date is None:
		raise ValueError("Invalid Xero date")
	return date.isoformat()
