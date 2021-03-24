# -*- coding: utf-8 -*-
# Copyright (c) 2021, itsdave GmbH and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from ipaddress import IPv4Address, IPv4Network
from frappe.model.document import Document

class IPNetwork(Document):
	pass

@frappe.whitelist()
def calculate_network_data(doc):
	net_doc = frappe.get_doc("IP Network", doc)
	network = IPv4Network(net_doc.network_address + "/" + net_doc.cidr_mask)
	net_doc.host_min = str(min(list(network.hosts())))
	net_doc.host_max = str(max(list(network.hosts())))
	net_doc.number_of_hosts = len(list(network.hosts()))
	net_doc.subnet_mask = str(network.netmask)
	net_doc.broadcast = str(network.broadcast_address)
	net_doc.save()
	return "please refresh"

