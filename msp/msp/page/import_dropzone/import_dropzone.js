/**
 * Frappe-Page „Lieferanten-Import" — Drag-&-Drop-Dropzone für CSV/ZIP mit
 * automatischer Format-Erkennung.
 *
 * Pro Datei: Upload → Analyse (msp.importers.assistant.analyze_file) →
 * Karte mit Statistik und „Assistent öffnen"-Button. Unbekannte Formate
 * bieten manuelle Handler-Auswahl an.
 */

frappe.pages["import-dropzone"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Lieferanten-Import"),
		single_column: true,
	});

	// Frappe übergibt ``page.main`` als jQuery-Wrapper — wir brauchen das native Element.
	const root = page.main[0] || page.main;
	root.innerHTML = `
		<div class="msp-dropzone-page">
			<div class="msp-dropzone" tabindex="0">
				<div class="msp-dropzone__icon">⬆</div>
				<div class="msp-dropzone__label">${__("Dateien per Drag & Drop ablegen oder")}
					<button class="btn btn-primary btn-sm msp-dropzone__browse">
						${__("Datei auswählen")}
					</button>
				</div>
				<div class="msp-dropzone__hint">
					${__("Unterstützt: CSV · ZIP (mit einer CSV)")}
				</div>
				<input type="file" class="msp-dropzone__input" multiple hidden
					accept=".csv,.zip,application/zip,application/x-zip-compressed,text/csv" />
			</div>
			<div class="msp-dropzone-cards"></div>
		</div>
	`;

	// Styles inline — spart einen zusätzlichen Bundle-Step.
	const style = document.createElement("style");
	style.textContent = `
		.msp-dropzone-page { padding: 10px; }
		.msp-dropzone {
			border: 2px dashed var(--border-color);
			border-radius: 8px;
			padding: 40px 24px;
			text-align: center;
			transition: background-color .15s, border-color .15s;
			cursor: pointer;
			background: var(--bg-color);
		}
		.msp-dropzone.is-dragover {
			border-color: var(--primary);
			background: var(--bg-light-gray);
		}
		.msp-dropzone__icon { font-size: 42px; opacity: .6; margin-bottom: 8px; }
		.msp-dropzone__label { font-size: 15px; margin-bottom: 6px; }
		.msp-dropzone__hint { color: var(--text-muted); font-size: 12px; }
		.msp-dropzone__browse { margin-left: 6px; }
		.msp-dropzone-cards {
			display: flex; flex-direction: column; gap: 12px;
			margin-top: 20px;
		}
		.msp-card {
			border: 1px solid var(--border-color);
			border-radius: 6px;
			padding: 14px 16px;
			background: var(--card-bg, var(--fg-color));
			display: flex; gap: 16px; align-items: flex-start;
		}
		.msp-card__icon {
			width: 40px; height: 40px; border-radius: 6px;
			display: flex; align-items: center; justify-content: center;
			font-size: 18px; flex: 0 0 40px;
			background: var(--bg-light-gray);
		}
		.msp-card__body { flex: 1; min-width: 0; }
		.msp-card__title { font-weight: 600; margin-bottom: 2px; display: flex; gap: 8px; align-items: baseline; }
		.msp-card__subtitle { color: var(--text-muted); font-size: 12px; }
		.msp-card__stats { margin-top: 8px; font-size: 13px; color: var(--text-color); }
		.msp-card__stats .stat { display: inline-block; margin-right: 14px; }
		.msp-card__stats .stat strong { color: var(--heading-color); }
		.msp-card__warn { color: var(--orange-500); font-size: 12px; margin-top: 6px; }
		.msp-card__error { color: var(--red-600); font-size: 12px; margin-top: 6px; white-space: pre-wrap; }
		.msp-card__actions { display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; }
		.msp-card--uploading, .msp-card--analyzing { opacity: .85; }
		.msp-card--matched { border-left: 3px solid var(--green-500); }
		.msp-card--unmatched { border-left: 3px solid var(--orange-500); }
		.msp-card--error { border-left: 3px solid var(--red-500); }
	`;
	root.appendChild(style);

	const dz = root.querySelector(".msp-dropzone");
	const cards = root.querySelector(".msp-dropzone-cards");
	const fileInput = root.querySelector(".msp-dropzone__input");

	// Drag & Drop
	["dragenter", "dragover"].forEach((ev) =>
		dz.addEventListener(ev, (e) => {
			e.preventDefault();
			e.stopPropagation();
			dz.classList.add("is-dragover");
		})
	);
	["dragleave", "drop"].forEach((ev) =>
		dz.addEventListener(ev, (e) => {
			e.preventDefault();
			e.stopPropagation();
			dz.classList.remove("is-dragover");
		})
	);
	dz.addEventListener("drop", (e) => handle_files(e.dataTransfer.files));
	dz.addEventListener("click", (e) => {
		if (e.target.classList.contains("msp-dropzone__browse") || e.target === dz) {
			fileInput.click();
		}
	});
	fileInput.addEventListener("change", (e) => handle_files(e.target.files));

	function handle_files(file_list) {
		if (!file_list || !file_list.length) return;
		for (const file of file_list) {
			process_one_file(file);
		}
	}

	// Für manuelle Zuordnung: Liste aller Handler beim Seitenaufruf laden
	let HANDLERS = [];
	frappe.call({
		method: "msp.importers.assistant.list_handlers",
		callback: (r) => (HANDLERS = r.message || []),
	});

	async function process_one_file(file) {
		const card = make_card(file);
		cards.prepend(card.el);

		try {
			card.set_state("uploading");
			const file_url = await upload_file(file, (pct) => card.set_progress(pct));

			card.set_state("analyzing");
			const analysis = await frappe.call({
				method: "msp.importers.assistant.analyze_file",
				args: { file_url },
			});
			render_analysis(card, analysis.message, file_url);
		} catch (err) {
			console.error(err);
			card.set_error(err && err.message ? err.message : String(err));
		}
	}

	function make_card(file) {
		const el = document.createElement("div");
		el.className = "msp-card msp-card--uploading";
		el.innerHTML = `
			<div class="msp-card__icon">${icon_for(file.name)}</div>
			<div class="msp-card__body">
				<div class="msp-card__title">
					<span class="name"></span>
					<span class="msp-card__subtitle"></span>
				</div>
				<div class="msp-card__state"><span class="spinner">⏳</span> ${__("Warte …")}</div>
				<div class="msp-card__stats" hidden></div>
				<div class="msp-card__warn" hidden></div>
				<div class="msp-card__error" hidden></div>
				<div class="msp-card__actions" hidden></div>
			</div>
		`;
		el.querySelector(".name").textContent = file.name;
		el.querySelector(".msp-card__subtitle").textContent = format_size(file.size);

		return {
			el,
			set_state(state, text) {
				el.classList.remove(
					"msp-card--uploading", "msp-card--analyzing",
					"msp-card--matched", "msp-card--unmatched", "msp-card--error"
				);
				el.classList.add(`msp-card--${state}`);
				const state_el = el.querySelector(".msp-card__state");
				const label = {
					uploading: __("Lade hoch …"),
					analyzing: __("Analysiere …"),
				}[state] || text || "";
				if (label) state_el.innerHTML = `<span class="spinner">⏳</span> ${label}`;
				else state_el.innerHTML = "";
			},
			set_progress(pct) {
				el.querySelector(".msp-card__state").innerHTML =
					`<span class="spinner">⏳</span> ${__("Lade hoch …")} ${Math.round(pct)}%`;
			},
			set_error(msg) {
				el.classList.add("msp-card--error");
				el.querySelector(".msp-card__state").innerHTML = `❌ ${__("Fehler")}`;
				const err_el = el.querySelector(".msp-card__error");
				err_el.hidden = false;
				err_el.textContent = msg;
			},
		};
	}

	function render_analysis(card, result, file_url) {
		const el = card.el;
		const state_el = el.querySelector(".msp-card__state");
		const stats_el = el.querySelector(".msp-card__stats");
		const warn_el = el.querySelector(".msp-card__warn");
		const err_el = el.querySelector(".msp-card__error");
		const actions_el = el.querySelector(".msp-card__actions");

		if (result.error) {
			card.set_error(result.error);
			return;
		}

		if (!result.handler_key) {
			// Format nicht erkannt — manuelle Zuordnung ermöglichen
			el.classList.remove("msp-card--analyzing");
			el.classList.add("msp-card--unmatched");
			state_el.innerHTML = `⚠ ${__("Format nicht erkannt")}`;
			warn_el.hidden = false;
			warn_el.textContent = __(
				"Keiner der verfügbaren Handler konnte die Datei zuverlässig erkennen. Bitte manuell zuordnen:"
			);
			actions_el.hidden = false;
			actions_el.innerHTML = `
				<select class="form-control form-control-sm" style="max-width: 280px;">
					<option value="">${__("Handler wählen …")}</option>
					${HANDLERS.map((h) =>
						`<option value="${h.handler_key}">${frappe.utils.escape_html(h.display_name)}</option>`
					).join("")}
				</select>
				<button class="btn btn-default btn-sm btn-open-assistant" disabled>
					${__("Assistent öffnen")}
				</button>
			`;
			const select = actions_el.querySelector("select");
			const btn = actions_el.querySelector(".btn-open-assistant");
			select.addEventListener("change", () => {
				btn.disabled = !select.value;
			});
			btn.addEventListener("click", () => open_assistant(file_url, select.value));
			return;
		}

		// Erkannt
		el.classList.remove("msp-card--analyzing");
		el.classList.add("msp-card--matched");
		state_el.innerHTML = `✓ ${__("Erkannt")}: <strong>${frappe.utils.escape_html(result.display_name)}</strong>`
			+ ` <span class="msp-card__subtitle">(${Math.round(result.confidence * 100)}%)</span>`;

		const preview = result.preview || {};
		const stat_parts = [];
		if (preview.line_count != null) stat_parts.push(`<span class="stat"><strong>${preview.line_count}</strong> ${__("Zeilen")}</span>`);
		if (preview.customer_count != null) stat_parts.push(`<span class="stat"><strong>${preview.customer_count}</strong> ${__("Kunden")}</span>`);
		if (preview.product_count != null) stat_parts.push(`<span class="stat"><strong>${preview.product_count}</strong> ${__("Produkte")}</span>`);
		if (preview.period_label) stat_parts.push(`<span class="stat">${frappe.utils.escape_html(preview.period_label)}</span>`);
		if (preview.credit_note_lines) stat_parts.push(`<span class="stat">${preview.credit_note_lines} ${__("Gutschriftzeilen")}</span>`);
		stats_el.hidden = false;
		stats_el.innerHTML = stat_parts.join(" ");

		const warnings = preview.warnings || [];
		if (preview.format_drift) warnings.unshift(__("Format weicht vom erwarteten Layout ab"));
		if (warnings.length) {
			warn_el.hidden = false;
			warn_el.innerHTML = warnings.map((w) => `⚠ ${frappe.utils.escape_html(w)}`).join("<br>");
		}

		actions_el.hidden = false;
		actions_el.innerHTML = `
			<button class="btn btn-primary btn-sm btn-open-assistant">
				${__("Assistent öffnen")} →
			</button>
		`;
		actions_el
			.querySelector(".btn-open-assistant")
			.addEventListener("click", () =>
				open_assistant(
					file_url,
					result.handler_key,
					{
						wizard_route: result.wizard_route,
						format_drift: preview.format_drift,
						suggested_profile: preview.suggested_profile,
						display_name: result.display_name,
					},
					result
				)
			);
	}

	function open_assistant(file_url, handler_key, opts = {}, analysis = {}) {
		// Kontext für den Wizard in route_options ablegen — Frappe überträgt das
		// beim set_route in die Ziel-Page, dort wird es ausgelesen und sofort
		// gelöscht.
		frappe.route_options = {
			file_url,
			handler_key,
			display_name: analysis.display_name || opts.display_name || "",
			suggested_profile: opts.suggested_profile || "",
			format_drift: !!opts.format_drift,
			preview: analysis.preview || null,
		};
		const route = opts.wizard_route || "import-assistant";
		frappe.set_route(route);
	}

	async function upload_file(file, on_progress) {
		return new Promise((resolve, reject) => {
			const form = new FormData();
			form.append("file", file, file.name);
			form.append("is_private", "1");
			form.append("folder", "Home");

			const xhr = new XMLHttpRequest();
			xhr.open("POST", "/api/method/upload_file");
			xhr.setRequestHeader("X-Frappe-CSRF-Token", frappe.csrf_token);

			xhr.upload.onprogress = (e) => {
				if (on_progress && e.lengthComputable) on_progress((e.loaded / e.total) * 100);
			};
			xhr.onload = () => {
				if (xhr.status >= 200 && xhr.status < 300) {
					try {
						const json = JSON.parse(xhr.responseText);
						const file_url = (json.message || {}).file_url;
						if (!file_url) return reject(new Error("Upload: keine file_url in Antwort"));
						resolve(file_url);
					} catch (e) {
						reject(e);
					}
				} else {
					reject(new Error(`Upload fehlgeschlagen (HTTP ${xhr.status})`));
				}
			};
			xhr.onerror = () => reject(new Error("Upload-Netzwerkfehler"));
			xhr.send(form);
		});
	}

	function format_size(bytes) {
		if (bytes < 1024) return bytes + " B";
		if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
		return (bytes / 1024 / 1024).toFixed(1) + " MB";
	}

	function icon_for(filename) {
		const name = (filename || "").toLowerCase();
		if (name.endsWith(".zip")) return "🗜️";
		if (name.endsWith(".csv")) return "📄";
		if (name.endsWith(".xlsx") || name.endsWith(".xls")) return "📊";
		return "📎";
	}
};
