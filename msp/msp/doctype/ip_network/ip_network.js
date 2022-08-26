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
	displayLoader();

	frm.call('get_used_ips', {})
		.then((response) => {
			const container = document.getElementById("usage-overview-table");
			let tableBody = ``;

			response?.message?.forEach((element) => {
				tableBody += `
						<tr>
							<td
								${element?.ip_address_name ? 'style="cursor: pointer;"' : ''}
								data-doctype-name="${element?.ip_address_name ?? ''}"
								data-doctype-type="IP Address"
							>
								${(element?.ip_address === '') ? "-" : element?.ip_address}
							</td>
							<td
								${element?.ip_address_name ? 'style="cursor: pointer; text-decoration: underline;"' : ''}
								data-doctype-name="${element?.it_object_name ?? ''}"
								data-doctype-type="IT Object"
							>
								${(element?.title === '') ? __("no object assigned") : element?.title}
							</td>
							<td style="">${(element?.type === '') ? __("no type assigned") : element?.type}</td>
						</tr>
					`;
			});

			const table = tableBody ? `
					<table style="" class="table table-striped table-bordered">
						<thead class="thead-dark">
							<tr>
								<th scope="col">IP</th>
								<th scope="col">Name</th>
								<th scope="col">Type</th>
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
function displayLoader() {
	const container = document.getElementById("usage-overview-table");
	const loader = `
		<div class="line-wobble"></div>
		<style>
		.line-wobble {
			--uib-size: 80px;
			--uib-speed: 1.75s;
			--uib-color: black;
			--uib-line-weight: 5px;

			position: relative;
			margin: 0 auto;
			top: 45%;
			display: flex;
			align-items: center;
			justify-content: center;
			height: var(--uib-line-weight);
			width: var(--uib-size);
			border-radius: calc(var(--uib-line-weight) / 2);
			overflow: hidden;
			transform: translate3d(0, 0, 0);
		  }

		  .line-wobble::before {
			content: '';
			position: absolute;
			top: 0;
			left: 0;
			height: 100%;
			width: 100%;
			background-color: var(--uib-color);
			opacity: 0.1;
		  }

		  .line-wobble::after {
			content: '';
			height: 100%;
			width: 100%;
			border-radius: calc(var(--uib-line-weight) / 2);
			animation: wobble var(--uib-speed) ease-in-out infinite;
			transform: translateX(-95%);
			background-color: var(--uib-color);
		  }

		  @keyframes wobble {
			0%,
			100% {
			  transform: translateX(-95%);
			}
			50% {
			  transform: translateX(95%);
			}
		  }
		</style>
		`;

	// Set width and height to <div> parent element and to <form> grandparent element so relative width and height with % works greate
	container.parentElement.parentElement.style.width = '100%';
	container.parentElement.parentElement.style.height = '100%';
	container.parentElement.style.width = '100%';

	// Set this styles to showcase where the information will appear
	container.style.width = '100%';
	container.style.height = '100%';
	container.innerHTML = loader;
}

