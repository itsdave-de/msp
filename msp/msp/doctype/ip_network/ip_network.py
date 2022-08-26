# -*- coding: utf-8 -*-
# Copyright (c) 2021, itsdave GmbH and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from ipaddress import IPv4Address, IPv4Network
from frappe.model.document import Document

class IPNetwork(Document):
	@frappe.whitelist()
	def get_used_ips(self):
		values = {'ip_network': self.name}
		used_ips = []
		used_ips = frappe.db.sql("""
			SELECT
				ipa.name as ip_address_name,
				ipa.ip_address,
				ito.name as it_object_name,
				ito.title,
				ito.type,
				ito.status
			FROM `tabIP Address` ipa
				LEFT JOIN `tabIT Object` ito
				ON ipa.it_object = ito.name
			WHERE ipa.ip_network = %(ip_network)s
		""", values=values, as_dict=1)

		unused_status = ['Decommissioned']
		for index, used_ip in enumerate(used_ips):
			if used_ip['status'] in unused_status: 
				del used_ips[index]

		for ip_network_reserved_range in self.ip_network_reserved_ranges_table:
			used_ips.append({
				'ip_address': ip_network_reserved_range.start,
				'title': ip_network_reserved_range.type,
				'type': 'DHCP Range Start'
			})
			used_ips.append({
				'ip_address': ip_network_reserved_range.end,
				'title': ip_network_reserved_range.type,
				'type': 'DHCP Range End'
			})

		return used_ips

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

