app_name = "lab_core"
app_title = "Lab Core"
app_publisher = "KhoiNgo"
app_description = "This is lab app for testing stacks"
app_email = "khoingo@gmail.com"
app_license = "mit"

website_route_rules = [
	{"from_route": "/lab/<path:app_path>", "to_route": "lab"},
]

# Xero demo: configuration lives in code and is applied after every migrate.
after_migrate = [
	"lab_core.setup.xero_connection.apply",
	"lab_core.setup.customizations.apply",
]

doc_events = {
	"Sales Order": {
		"on_submit": "lab_core.overrides.sales_order.on_submit",
		"on_cancel": "lab_core.overrides.sales_order.on_cancel",
	},
}

doctype_js = {"Sales Order": "public/js/sales_order.js"}

scheduler_events = {
	"cron": {"*/5 * * * *": ["lab_core.tasks.xero_pull.pull_changes"]},
}

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "lab_core",
# 		"logo": "/assets/lab_core/logo.png",
# 		"title": "Lab Core",
# 		"route": "/lab_core",
# 		"has_permission": "lab_core.api.permission.has_app_permission",
# 	}
# ]

# The dock, the rail down the left of the desk, is a document rather than a hook. Author it in
# Manage Dock on a developer-mode site and press Export to App, and it is written to
# `lab_core/dock/lab_core/lab_core.json` for git to carry. An app that ships none has no
# rail: its sidebar gets a switcher in the header instead.
#
# A companion app, one that extends a host app rather than standing on its own, says so with
# `mount_on` on that same record, and its entries are appended to the host's rail. Mounting keeps
# the companion off the apps screen, so it takes precedence over any add_to_apps_screen above.

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/lab_core/css/lab_core.css"
# app_include_js = "/assets/lab_core/js/lab_core.js"

# include js, css files in header of web template
# web_include_css = "/assets/lab_core/css/lab_core.css"
# web_include_js = "/assets/lab_core/js/lab_core.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "lab_core/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_kanban_js = {"doctype" : "public/js/doctype_kanban.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "lab_core/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "lab_core.utils.jinja_methods",
# 	"filters": "lab_core.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "lab_core.install.before_install"
# after_install = "lab_core.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "lab_core.uninstall.before_uninstall"
# after_uninstall = "lab_core.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "lab_core.utils.before_app_install"
# after_app_install = "lab_core.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "lab_core.utils.before_app_uninstall"
# after_app_uninstall = "lab_core.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "lab_core.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "lab_core.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["lab_core.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"lab_core.tasks.all"
# 	],
# 	"daily": [
# 		"lab_core.tasks.daily"
# 	],
# 	"hourly": [
# 		"lab_core.tasks.hourly"
# 	],
# 	"weekly": [
# 		"lab_core.tasks.weekly"
# 	],
# 	"monthly": [
# 		"lab_core.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "lab_core.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "lab_core.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "lab_core.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "lab_core.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["lab_core.utils.before_request"]
# after_request = ["lab_core.utils.after_request"]

# Job Events
# ----------
# before_job = ["lab_core.utils.before_job"]
# after_job = ["lab_core.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"lab_core.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

