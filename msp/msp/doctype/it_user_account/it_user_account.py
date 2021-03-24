# -*- coding: utf-8 -*-
# Copyright (c) 2021, itsdave GmbH and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class ITUserAccount(Document):

    @frappe.whitelist()
    def copy_pw(self, user_agent, platform):
        """
        pw_access_doc = frappe.get_doc({
            "doctype": "User Account Password Access",
            "access_datetime": frappe.utils.datetime.datetime.now(),
            "user": frappe.session.user,
            "ip": frappe.local.request_ip,
            "method": "copy_pw",
            "platform": platform,
            "user_agent": user_agent})
        self.append("access_history", pw_access_doc)
        self.save()
        """
        return(self.get_password("password"))
