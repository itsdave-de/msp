from __future__ import unicode_literals
from frappe import _

def get_data():
	return {
		'heatmap': False,
		'fieldname': 'ip_network',
		'transactions': [
			{
				'label': _('Objects'),
				'items': ['IP Address' ]
			}
		]
	}
