// Xero buttons on the Sales Order form. Both only ask the server to queue a job;
// the result arrives later in the lab_xero_* fields, so the form is reloaded afterwards.

frappe.ui.form.on("Sales Order", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.docstatus === 0) {
			return; // a draft never goes to Xero
		}

		if (frm.doc.lab_xero_sync_status !== "Synced") {
			frm.add_custom_button(
				__("Retry"),
				() => lab_xero_call(frm, "lab_core.api.xero.retry_sync", __("Sync to Xero queued")),
				__("Xero")
			);
		}

		if (frm.doc.lab_xero_invoice_id) {
			frm.add_custom_button(
				__("Refresh from Xero"),
				() => lab_xero_call(frm, "lab_core.api.xero.refresh", __("Refresh from Xero queued")),
				__("Xero")
			);
		}
	},
});

function lab_xero_call(frm, method, queued_message) {
	frappe.call({
		method: method,
		args: { sales_order: frm.doc.name },
		freeze: true,
		callback() {
			frappe.show_alert(queued_message);
			// The job runs after this request; give it a moment, then show the new status.
			setTimeout(() => frm.reload_doc(), 3000);
		},
	});
}
