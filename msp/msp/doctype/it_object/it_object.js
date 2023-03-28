// Copyright (c) 2021, itsdave GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on('IT Object', {
	refresh: function (frm) {

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

		const container = document.getElementById('oitc-output');

		// Set width and height to <div> parent element and to <form> grandparent element so relative width and height with % works greate
		container.parentElement.parentElement.style.width = '100%';
		container.parentElement.parentElement.style.height = '100%';
		container.parentElement.style.width = '100%';
		container.parentElement.style.height = '90%';

		// Set this styles to showcase where the information will appear
		container.style.width = '100%';
		container.style.height = '100%';
		container.style.background = 'rgba(212, 204, 203, 0.4)';
		container.innerHTML = loader;

		frm.call('get_oitc_host_status_data', {})
			.then((response) => {
				const container = document.getElementById('oitc-output');

				if (response.message.status !== 200) {
					container.innerHTML = response.message.response || 'An error occurred while fetching OITC data';
					return;
				}

				let background = response.message?.statusColors?.upStateColor;
				if (response.message?.host?.hostStatus?.currentState?.toUpperCase() === "DOWN") {
					background = response.message?.statusColors?.downStateColor;
				} else if (response.message?.host?.hostStatus?.currentState?.toUpperCase() === "UNREACHABLE") {
					background = response.message?.statusColors?.unreachableStateColor;
				}

				container.innerHTML = `
				<div class="js-oitc-output">
					<div>
						<h1 class="font-size-50" style="color: white;">
							${response.message?.host?.hostStatus?.currentState?.toUpperCase()}
						</h1>
					</div>
					<div>
						<div>Current State since</div>
						<h3 style="color: white; margin: 1rem 0;">
							${response.message?.host?.hostStatus?.currentStateSince}
						</h3>
					</div>
					<div>
						<div>Last check</div>
						<h3 style="color: white; margin: 1rem 0;">
							${response.message?.host?.hostStatus?.lastCheck}
						</h3>
					</div>
					<div>
						<div>Next check</div>
						<h3 style="color: white; margin: 1rem 0;">
							${response.message?.host?.hostStatus?.nextCheck}
						</h3>
					</div>
					<div>
						<div>Services</div>
						<h3 style="color: white; margin: 1rem 0;">
							Total Services: ${response.message?.host?.servicesStatus?.totalServices}
						</h3>
						<div>Services Status:</div>
						<h3 style="color: white; margin: 1rem 0;">
							<ul style="text-align:left;">
								<li>OK: ${response.message?.host?.servicesStatus?.state?.ok}</li>
								<li>CRITICAL: ${response.message?.host?.servicesStatus?.state?.critical}</li>
								<li>WARNING: ${response.message?.host?.servicesStatus?.state?.warning}</li>
								<li>UNKNOWN: ${response.message?.host?.servicesStatus?.state?.unknown}</li>
							</ul>
						</h3>
					</div>
				</div>
				`

				let statusData = document.querySelector('.js-oitc-output')
				statusData.style.textAlign = 'center';
				statusData.style.color = '#FFF';
				statusData.style.fontWeight = 'Bold';
				statusData.style.background = background;
				statusData.style.padding = '1rem';
			})

		if (frm.doc.admin_interface_link) {
			frm.add_custom_button('Open Admin Interface', () => frm.trigger('open_admin_interface'), 'Actions');
		};
		if (frm.doc.monitoring_link) {
			frm.add_custom_button('Open Monitoring', () => frm.trigger('open_monitoring'), 'Actions');
		};
		if (frm.doc.link) {
			frm.add_custom_button('Copy Main Admin Account User', () => frm.trigger('get_user'), 'Actions');
		};
		if (frm.doc.link) {
			frm.add_custom_button('Copy Main Admin Account PW', () => frm.trigger('get_pw'), 'Actions');
		};
	},
	open_admin_interface: function (frm) {
		window.open(frm.doc.admin_interface_link, '_blank').focus();
	},
	open_monitoring: function (frm) {
		window.open(frm.doc.monitoring_link, '_blank').focus();
	},
	get_pw: function(frm) {
        frm.call('copy_pw', {
            'user_agent': navigator.userAgent,
            'platform': navigator.platform,
        },
        (r) => {
			frm.events.CopyToClipboard(r.message)
        }
        );
    },
	get_user: function(frm) {
        frm.call('copy_user', {
            'user_agent': navigator.userAgent,
            'platform': navigator.platform,
        },
        (r) => {
			frm.events.CopyToClipboard(r.message)
        }
        );
    },
	CopyToClipboard: function(value) {
		var tempInput = document.createElement("input");
		tempInput.value = value;
		document.body.appendChild(tempInput);
		tempInput.select();
		document.execCommand("copy");
		document.body.removeChild(tempInput);
	},
	
});
