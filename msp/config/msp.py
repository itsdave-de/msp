from __future__ import unicode_literals
from frappe import _



def get_data():
    return [
        {
            "label": _("Objects"),
            "items": [
                {
                    "type": "doctype",
                    "name": "IT Object",
                    "label": _("IT Object"),
                    "description": _("IT Object")
                },
                {
                    "type": "doctype",
                    "name": "IP Network",
                    "label": _("IP Network"),
                    "description": _("IP Network")
                },
                {
                    "type": "doctype",
                    "name": "IP Address",
                    "label": _("IP Address"),
                    "description": _("IP Address")
                },
                {
                    "type": "doctype",
                    "name": "IT User Account",
                    "label": _("IT User Account"),
                    "description": _("IT User Account")
                },
                {
                    "type": "doctype",
                    "name": "IT Backup",
                    "label": _("IT Backup"),
                    "description": _("IT Backup")
                }
            ]
        },
        {
            "label": _("Master Data"),
            "items": [
                {
                    "type": "doctype",
                    "name": "IT Landscape",
                    "label": _("IT Landscape"),
                    "description": _("IT Landscape")
                },
                {
                    "type": "doctype",
                    "name": "IT Object Type",
                    "label": _("IT Object Type"),
                    "description": _("IT Object Type")
                },
                {
                    "type": "doctype",
                    "name": "IT Contract",
                    "label": _("IT Contract"),
                    "description": _("IT Contract")
                },
                {
                    "type": "doctype",
                    "name": "IT Contract Type",
                    "label": _("IT Contract Type"),
                    "description": _("IT Contract Type")
                },
                {
                    "type": "doctype",
                    "name": "IT User Account Type",
                    "label": _("IT User Account Type"),
                    "description": _("IT User Account Type")
                },
            ]
        },
        {
            "label": _("Process Management"),
            "items": [
                {
                    "type": "doctype",
                    "name": "IT Checklist",
                    "label": _("IT Checklist"),
                    "description": _("IT Checklist")
                },
                {
                    "type": "doctype",
                    "name": "IT Checklist Template",
                    "label": _("IT Checklist Template"),
                    "description": _("IT Checklist Template")
                }
            ]
        }
    ]