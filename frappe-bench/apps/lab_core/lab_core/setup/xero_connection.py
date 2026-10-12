"""Apply the demo's Xero connection configuration after migrate."""

import frappe


CONNECTED_APP_NAME = "xero"
SCOPES = (
	"offline_access",
	"accounting.invoices",
	"accounting.contacts",
	"accounting.settings.read",
)
SETTINGS_CONFIG = {
	"connected_user": "xero_connected_user",
	"default_account_code": "xero_default_account_code",
	"default_tax_type": "xero_default_tax_type",
}


def apply() -> None:
	"""Update the fixed connection; skip missing config without clearing saved values."""
	values = _read_config()
	_apply_connected_app(values)
	_apply_settings(values)


def _read_config() -> dict:
	keys = ("xero_client_id", "xero_client_secret", *SETTINGS_CONFIG.values())
	values = {}
	for key in keys:
		value = frappe.conf.get(key)
		if value is None or value == "":
			print(f"[xero setup] Missing site config: {key}; skipping that configuration.")
		else:
			values[key] = value
	return values


def _apply_connected_app(values: dict) -> None:
	other_apps = frappe.get_list(
		"Connected App",
		filters={"provider_name": "Xero", "name": ["!=", CONNECTED_APP_NAME]},
		fields=["name"],
		limit_page_length=0,
	)
	for app in other_apps:
		print(f"[xero setup] Existing Connected App {app.name} left unchanged; setup uses xero.")

	if "xero_client_id" not in values or "xero_client_secret" not in values:
		print("[xero setup] Skipping Connected App: both credential keys are required.")
		return

	exists = frappe.db.exists("Connected App", CONNECTED_APP_NAME)
	app = (
		frappe.get_doc("Connected App", CONNECTED_APP_NAME)
		if exists
		else frappe.get_doc({"doctype": "Connected App"})
	)
	app.provider_name = "Xero"
	app.authorization_uri = "https://login.xero.com/identity/connect/authorize"
	app.token_uri = "https://identity.xero.com/connect/token"
	app.client_id = values["xero_client_id"]
	app.client_secret = values["xero_client_secret"]
	if tuple(row.scope for row in app.scopes or []) != SCOPES:
		app.set("scopes", [{"scope": scope} for scope in SCOPES])
	if exists:
		app.save()
	else:
		app.insert(set_name=CONNECTED_APP_NAME)
	print(f"[xero setup] Connected App xero ready; Redirect URI: {app.redirect_uri}")


def _apply_settings(values: dict) -> None:
	if not frappe.db.exists("DocType", "Lab Xero Settings"):
		print("[xero setup] Missing DocType: Lab Xero Settings; skipping Settings.")
		return

	settings = frappe.get_single("Lab Xero Settings")
	changed = False
	if frappe.db.exists("Connected App", CONNECTED_APP_NAME):
		if settings.connected_app != CONNECTED_APP_NAME:
			settings.connected_app = CONNECTED_APP_NAME
			changed = True
	else:
		print("[xero setup] Missing Connected App xero; skipping Settings.connected_app.")

	for field, key in SETTINGS_CONFIG.items():
		if key in values and settings.get(field) != values[key]:
			settings.set(field, values[key])
			changed = True
	if changed:
		settings.save()
