import frappe
from frappe import _


@frappe.whitelist(methods=["GET"])
def hello() -> dict[str, str]:
    if frappe.session.user == "Guest":
        frappe.throw(_("Please log in."), frappe.PermissionError)

    return {
        "message": "Hello from Lab Core",
        "user": frappe.session.user,
    }
