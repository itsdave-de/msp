# -*- coding: utf-8 -*-
# Copyright (c) 2021, itsdave GmbH and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class ITLandscape(Document):
    pass
    
def get_timeline_data(doctype, name):
    """views for linked objects"""
    return dict(frappe.db.sql("""select unix_timestamp(l.creation), sum(1) as `count`
        from `tabView Log` as l where
        (`reference_doctype` = "IT Object" and `reference_name` in (select `name` from `tabIT Object` where `it_landscape` = %s))
        or
        (`reference_doctype` = "IP Network" and `reference_name` in (select `name` from `tabIP Network` where `it_landscape` = %s))
        or
        (`reference_doctype` = "IP Address" and `reference_name` in (select `name` from `tabIP Address` where `it_landscape` = %s))
        or
        (`reference_doctype` = "IT User Account" and `reference_name` in (select `name` from `tabIT User Account` where `it_landscape` = %s))
        or
        (`reference_doctype` = "IT Landscape" and `reference_name` = %s)
        and
        creation > date_sub(curdate(), interval 1 year)
        group by date(l.creation);""", (name,name,name,name,name)))
