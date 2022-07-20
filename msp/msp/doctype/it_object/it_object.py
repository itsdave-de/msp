# -*- coding: utf-8 -*-
# Copyright (c) 2021, itsdave GmbH and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import requests
from frappe.model.document import Document

class ITObject(Document):

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
