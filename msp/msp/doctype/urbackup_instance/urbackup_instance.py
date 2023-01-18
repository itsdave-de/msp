# Copyright (c) 2022, itsdave GmbH and contributors
# For license information, please see license.txt

import frappe
import urbackup_api
from frappe.model.document import Document
from pprint import pprint
from json import dumps

class UrBackupInstance(Document):
	@frappe.whitelist()
	def import_clients(self):
		server = urbackup_api.urbackup_server(self.address, self.user, self.get_password())
		clients = server.get_status()
		if not clients:
			frappe.throw("No Data Returned. Check credentials and connectivity to address.")
		
		existing_clients = self._get_existing_clients()
		
		for client in clients:
			client_dict = self._get_client_dict(client)
			if str(client["name"]).lower() in existing_clients:
				print(str(client["name"]).lower() + " allready exists")
				self._check_for_client_update(client_dict)
				client_status = server.get_clientbackups(client["id"])
				pprint(client_status)

				continue
			
			client_doc = frappe.get_doc(client_dict)
			client_doc.insert()

			
	
	def _get_existing_clients(self):
		client_list = []
		existing_clients = frappe.get_all("UrBackup Client", filters={"urbackup_instance": self.name}, fields=["client_name"])
		for ec in existing_clients:
			client_list.append(str(ec["client_name"]).lower())
		return client_list

	def _get_client_dict(self, client):
		client["processes"] = dumps(client["processes"])
		client_dict = {
				"doctype": "UrBackup Client",
				"client_name": str(client["name"]).lower(),
				"urbackup_instance": self.name,
				"client_status": client["status"],
				**client
			}
		return client_dict

	def _check_for_client_update(self, client_dict):
		clients_for_name = frappe.get_all("UrBackup Client", filters={"client_name": client_dict["client_name"]})
		if len(clients_for_name) != 1:
			frappe.throw("Multiple Clients found for Client Name: " + str(client_dict["client_name"]))
		name = clients_for_name[0]["name"]
		existing_client_doc = frappe.get_doc("UrBackup Client", name)
		for k in client_dict.keys():
			if k in ("doctype", "client_name", "urbackup_instance", "name"):
				continue
			if isinstance(client_dict[k], bool):
				client_dict[k] = 1 if client_dict[k] == True else 0
			if k == "status":
				k = "client_status"

			old = client_dict[k]
			new = getattr(existing_client_doc, k)

			if new != old:
				print("change found for " + k + ": old=" + str(old) + " new=" + str(new))

			