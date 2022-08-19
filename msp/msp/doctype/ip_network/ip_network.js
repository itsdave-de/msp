// Copyright (c) 2021, itsdave GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on('IP Network', {

	refresh(frm) {
		frm.add_custom_button('Calculate Network Data', function(){
			frappe.call({ 
				method: 'msp.msp.doctype.ip_network.ip_network.calculate_network_data', 
				args: { doc: frm.doc.name },
				callback:function(r){
					console.log(r.message)
					frm.reload_doc()
				}
			})
		})
		getUsedIpsInNetwork(frm);
	}
});

function getUsedIpsInNetwork(frm) {
	frm.call('get_used_ips', {})
		.then((response) => {
			const container = document.getElementById("usage-overview-table");
			let tableBody = ``;

			response?.message?.forEach((element) => {
				tableBody += `
						<tr>
							<td
								style="border: 1px solid #000; padding: 0.5rem 1rem; text-align: left; ${element?.ip_address_name ? 'cursor: pointer;' : ''}"
								data-doctype-name="${element?.ip_address_name ?? ''}"
								data-doctype-type="IP Address"
							>
								${element?.ip_address ?? "-"}
							</td>
							<td
								style="border: 1px solid #000; padding: 0.5rem 1rem; text-align: left; ${element?.ip_address_name ? 'cursor: pointer;' : ''}"
								data-doctype-name="${element?.it_object_name ?? ''}"
								data-doctype-type="IT Object"
							>
								${element?.title ?? "-"}
							</td>
							<td style="border: 1px solid #000; padding: 0.5rem 1rem; text-align: left;">${element?.type ?? "-"}</td>
						</tr>
					`;
			});

			const table = tableBody ? `
					<table style="border-collapse: collapse; border: 2px solid #000; text-align: left; width: 100%; color: #000;">
						<thead>
							<tr>
								<th scope="col" style="border: 1px solid #000; padding: 0.5rem 1rem;">IP</th>
								<th scope="col" style="border: 1px solid #000; padding: 0.5rem 1rem;">Name</th>
								<th scope="col" style="border: 1px solid #000; padding: 0.5rem 1rem;">Type</th>
							</tr>
						</thead>
						<tbody>
							${tableBody}
						</tbody>
					</table>
				` : 'No IPs used for this network';

			container.innerHTML = table;

			document.querySelectorAll('[data-doctype-name]').forEach(element => {
				element.addEventListener('click', (event) => {
					event.preventDefault();
					if (event.target.dataset?.doctypeName === '') {
						return;
					}

					frappe.set_route('Form', event.target.dataset?.doctypeType, event.target.dataset?.doctypeName);
				});
			});
		})
}
