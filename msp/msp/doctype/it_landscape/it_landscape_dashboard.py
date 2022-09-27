from __future__ import unicode_literals
from frappe import _

def get_data():
	return {
		'heatmap': True,
		'heatmap_message': _('Based on Views of linked Objects and this Landscape.'),
		'fieldname': 'it_landscape',
		'transactions': [
			{
				'label': _('Objects'),
				'items': ['IT Object', 'IT User Account', 'IP Network', 'IP Address', 'SSH Public Key' ]
			},
			{
				'label': _('Processes'),
				'items': ['IT Contract', 'ToDo']
			}
		]
	}
