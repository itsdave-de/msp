# -*- coding: utf-8 -*-
# Copyright (c) 2021, itsdave GmbH and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import requests
from frappe.model.document import Document

class ITObject(Document):
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.set_it_object_data_in_ip_address_doctype()
    
    @frappe.whitelist()
    def copy_pw(self, user_agent, platform):
        if self.link:
            account_doc = frappe.get_doc("IT User Account", self.link)
        return(account_doc.get_password("password"))

    @frappe.whitelist()
    def copy_user(self, user_agent, platform):
        if self.link:
            account_doc = frappe.get_doc("IT User Account", self.link)
        return(account_doc.username)

    def set_it_object_data_in_ip_address_doctype(self):
        if not self.main_ip:
            return

        ip_address_name_with_it_object = frappe.db.get_value("IP Address", {'it_object': self.name}, ['name'])
        if ip_address_name_with_it_object:
            current_ip_address_with_it_object_doctype = frappe.get_doc("IP Address", ip_address_name_with_it_object)
            current_ip_address_with_it_object_doctype.it_object = None
            current_ip_address_with_it_object_doctype.it_object_name = None
            current_ip_address_with_it_object_doctype.save()

        ip_address_doctype = frappe.get_doc("IP Address", self.main_ip)
        ip_address_doctype.it_object = self.name
        ip_address_doctype.it_object_name = self.title
        ip_address_doctype.save()
        frappe.db.commit()

    def get_host_status_from_hosts_data(self, hosts_data, msp_settings_doc):

        host_data_response = {
            'status': 204,
            'response': f'Host with UUID {self.oitc_host_uuid} was not found in OITC. Check if the UUID is correct'
        } 

        for host_data in hosts_data['all_hosts']:

            if host_data['Host']['uuid'] != self.oitc_host_uuid:
                continue

            host_data_response = {
                'status': 200,
                'host': {
                    'id': host_data['Host']['id'],
                    'uuid': host_data['Host']['uuid'],
                    'hostStatus': {
                        'currentState': host_data['Hoststatus']['humanState'],
                        'lastCheck': host_data['Hoststatus']['lastCheckInWords'],
                        'nextCheck': host_data['Hoststatus']['nextCheckInWords'],
                        'currentStateSince': host_data['Hoststatus']['last_state_change_in_words']
                    },
                    'servicesStatus': {
                        'totalServices': host_data['ServicestatusSummary']['total'],
                        'state': {
                            'ok': host_data['ServicestatusSummary']['state']['ok'],
                            'critical': host_data['ServicestatusSummary']['state']['critical'],
                            'unknown': host_data['ServicestatusSummary']['state']['unknown'],
                            'warning': host_data['ServicestatusSummary']['state']['warning']
                        }
                    }
                },
                'statusColors': {
                    'upStateColor': msp_settings_doc.oitc_status_up_color,
                    'downStateColor': msp_settings_doc.oitc_status_down_color,
                    'unreachableStateColor': msp_settings_doc.oitc_status_unreachable_color
                }
            }

        return host_data_response


    @frappe.whitelist()
    def get_oitc_host_status_data(self):
        msp_settings_doc = frappe.get_doc('MSP Settings')

        if not self.oitc_host_uuid:
            return {
                'status': 422,
                'response': "This host does not have any OITC Host UUID stored. Please store an OITC Host UUID in the 'External References' section to get its status data."
            }

        try:
            endpoint = f'{msp_settings_doc.oitc_url}hosts/index.json?angular=true&scroll=true&filter[Hosts.uuid]={self.oitc_host_uuid}'
            api_authorization = f'{msp_settings_doc.oitc_api_key_header_string}' + msp_settings_doc.get_password('oitc_api_key')
            headers = {'Authorization': api_authorization}

            hosts_data = requests.get(url=endpoint, headers=headers, verify=False)

            return self.get_host_status_from_hosts_data(hosts_data.json(), msp_settings_doc)
        except Exception as exception:
            return {
                'status': 500,
                'response': f'Data could not be fetched from {msp_settings_doc.oitc_url}. Error -> {str(exception)}'
            }

def set_it_object_data_in_ip_address_doctype_for_existing_it_objects():
        it_objects = frappe.db.get_all("IT Object", fields=['name'])
        for it_object in it_objects:
            it_object_doctype = frappe.get_doc("IT Object", it_object['name'])
            it_object_doctype.set_it_object_data_in_ip_address_doctype()
