import frappe
from datetime import datetime

@frappe.whitelist()
def get_ssh_keys_for_landscape(landscape):
    keys = frappe.get_all("SSH Public Key", filters={"it_landscape": landscape, "status": "active"})
    print(keys)
    if len(keys) >= 1:
        keys_str = ""
        for key in keys:
            kd = frappe.get_doc("SSH Public Key", key["name"])
            company_str = str(frappe.get_doc("Employee", kd.employee).company)
            c_str = datetime.strftime(kd.creation, "%d.%m.%Y")
            o_str = datetime.strftime(datetime.now(), "%d.%m.%Y %H:%M")
            comment = "#"+ company_str + "|" + str(kd.employee_name) + "@" + str(kd.host_name) + " ITL:" + str(kd.it_landscape) + " C:" + c_str + " O:" + o_str
            keys_str += comment + "\n" + kd.ssh_public_key + "\n"
        return keys_str
    else:
        return "No keys found."

