# Copyright (c) 2026, KhoiNgo and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from lab_core.lab_xero import outbox


class LabNote(Document):
	def before_insert(self):
		self.sync_status = "Queued"

	def after_insert(self):
		# Same transaction as the insert: either the note and its outbox row both exist, or neither.
		# Runs for notes made in Desk and in the SPA alike.
		outbox.queue(self)
