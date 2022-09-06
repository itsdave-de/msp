# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from . import __version__ as app_version

app_name = "msp"
app_title = "MSP"
app_publisher = "itsdave GmbH"
app_description = "App for Managed Service Providers"
app_icon = "octicon octicon-rocket"
app_color = "grey"
app_email = "dev@itsdave.de"
app_license = "GPLv3"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/msp/css/msp.css"
app_include_js = "/assets/msp/js/customer_quick_entry.js"

jenv = {
	"methods": [
		"jinja_get_item_price:msp.things.get_item_price_for_label",
		"jinja_get_epc_code:msp.things.get_epc_inline",
		"jinja_get_qr_code:msp.things.get_qr_code_inline"
	]
}

# include js, css files in header of web template
# web_include_css = "/assets/msp/css/msp.css"
# web_include_js = "/assets/msp/js/msp.js"

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Website user home page (by function)
# get_website_user_home_page = "msp.utils.get_home_page"

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "msp.install.before_install"
# after_install = "msp.install.after_install"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "msp.notifications.get_notification_config"

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

doc_events = {
	"Location": {
		"before_save": "msp.tools.hooks_methods.build_full_location_path"
	}
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"msp.tasks.all"
# 	],
# 	"daily": [
# 		"msp.tasks.daily"
# 	],
# 	"hourly": [
# 		"msp.tasks.hourly"
# 	],
# 	"weekly": [
# 		"msp.tasks.weekly"
# 	]
# 	"monthly": [
# 		"msp.tasks.monthly"
# 	]
# }

# Testing
# -------

# before_tests = "msp.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "msp.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "msp.task.get_dashboard_data"
# }

