import frappe
from frappe.utils.password import get_decrypted_password

import requests
import json
from pprint import pprint

@frappe.whitelist()
def get_agents_pretty(documentation):
    documentation_doc = frappe.get_doc("MSP Documentation", documentation)

    if not documentation_doc.tactical_rmm_tenant_caption:
        frappe.throw("Tennant Caption missing")

    client_name = documentation_doc.tactical_rmm_tenant_caption

    agents = get_all_agents()

    agent_list = []
    for agent in agents:
        if agent["client_name"] == client_name:
            agent_list.append(agent)
    
    output = make_agent_md_output(agent_list)

    documentation_doc.system_list = output
    documentation_doc.save()
    return agent_list


def get_all_agents():
    settings = frappe.get_single("MSP Settings")
    if not settings.api_key:
        frappe.throw("API Key is missing")
    if not settings.api_url:
        frappe.throw("API URL is missing")
    
    API = settings.api_url
    HEADERS = {
        "Content-Type": "application/json",
        "X-API-KEY": get_decrypted_password("MSP Settings", "MSP Settings", "api_key", raise_exception=True),
    }

    agents = requests.get(f"{API}/agents/?detail=true", headers=HEADERS)

    return agents.json()


def make_agent_md_output(agents):
    md_output = ""
    for agent in agents:
        md_output += f'''
#### {agent["hostname"]}
- OS:  {agent["operating_system"]}
- CPU: {agent["cpu_model"]}
- GPU: {agent["graphics"]}
- Disks: {agent["physical_disks"]}
- Model: {render_model(agent["make_model"])}
- Type: {agent["monitoring_type"]}
- Site: {agent["site_name"]}
- Last User: {agent["logged_username"]}
'''
    if agent["description"]:
         md_output += f'''Description: 
{agent["description"]}
'''

    return md_output


def render_model(model):
    if model == "System manufacturer System Product Name":
        return "not specified"
    if model == "Xen HVM domU":
        return "Virtual Mashine running on Xen Hypervisor"
    return model



""" 
{'agent_id': 'mXXJYhUHwrMPcAAuvsmGMFhcVsjWVMQqHKaVCfBN',
23:31:32 web.1            |  'alert_template': None,
23:31:32 web.1            |  'block_policy_inheritance': False,
23:31:32 web.1            |  'boot_time': 1675142998.0,
23:31:32 web.1            |  'checks': {'failing': 0,
23:31:32 web.1            |             'has_failing_checks': False,
23:31:32 web.1            |             'info': 0,
23:31:32 web.1            |             'passing': 0,
23:31:32 web.1            |             'total': 0,
23:31:32 web.1            |             'warning': 0},
23:31:32 web.1            |  'client_name': 'Cohrs Werkstaetten',
23:31:32 web.1            |  'cpu_model': ['Intel(R) Core(TM) i7-6700K CPU @ 4.00GHz'],
23:31:32 web.1            |  'description': '',
23:31:32 web.1            |  'goarch': 'amd64',
23:31:32 web.1            |  'graphics': 'NVIDIA Quadro K2000D',
23:31:32 web.1            |  'has_patches_pending': False,
23:31:32 web.1            |  'hostname': 'CWWS13',
23:31:32 web.1            |  'italic': False,
23:31:32 web.1            |  'last_seen': '2023-01-31T14:34:41.479173Z',
23:31:32 web.1            |  'local_ips': '192.168.24.161',
23:31:32 web.1            |  'logged_username': 'o.ruschmeyer',
23:31:32 web.1            |  'maintenance_mode': False,
23:31:32 web.1            |  'make_model': 'System manufacturer System Product Name',
23:31:32 web.1            |  'monitoring_type': 'workstation',
23:31:32 web.1            |  'needs_reboot': False,
23:31:32 web.1            |  'operating_system': 'Windows 10 Pro, 64 bit v22H2 (build 19045.2486)',
23:31:32 web.1            |  'overdue_dashboard_alert': False,
23:31:32 web.1            |  'overdue_email_alert': False,
23:31:32 web.1            |  'overdue_text_alert': False,
23:31:32 web.1            |  'pending_actions_count': 0,
23:31:32 web.1            |  'physical_disks': ['Kingston SHPM2280P2/240G 224GB IDE'],
23:31:32 web.1            |  'plat': 'windows',
23:31:32 web.1            |  'public_ip': '90.187.0.65',
23:31:32 web.1            |  'site_name': 'Fallingbostel',
23:31:32 web.1            |  'status': 'overdue',
23:31:32 web.1            |  'version': '2.4.4'} """