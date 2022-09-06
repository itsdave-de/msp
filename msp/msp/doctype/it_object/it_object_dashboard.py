from __future__ import unicode_literals
from frappe import _

def get_data():
	return {
		'heatmap': False,
		'fieldname': 'it_object',
		'transactions': [
			{
				'label': _('Processes'),
				'items': ['ToDo']
			}
		]
	}
