/**
 * Frappe-Page „Import-Assistent" — Wizard, der den Import einer einzelnen
 * Datei (vom Dropzone-Flow übergeben) Schritt für Schritt durchführt.
 *
 * Aufruf: frappe.route_options = { file_url, handler_key, display_name,
 *   suggested_profile, format_drift, preview }
 *         frappe.set_route("import-assistant");
 *
 * Schritte (Stepper):
 *   1. Zusammenfassung + Konfiguration
 *   2. Import (Live-Progress)
 *   3. Ergebnis mit Links zu den erzeugten Dokumenten
 */

frappe.pages["import-assistant"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Import-Assistent"),
		single_column: true,
	});
	const root = page.main[0] || page.main;

	const ctx = frappe.route_options || {};
	// route_options werden in Frappe nach dem ersten Lesen verworfen — lokal halten
	frappe.route_options = {};

	if (!ctx.file_url || !ctx.handler_key) {
		root.innerHTML = `
			<div class="msp-assistant-empty">
				${__("Kein Kontext. Bitte eine Datei über die")}
				<a href="/app/import-dropzone">${__("Dropzone")}</a> ${__("einwerfen.")}
			</div>`;
		inject_style(root);
		return;
	}

	inject_style(root);

	// Falls keine Preview mitgereicht wurde (z. B. bei manueller Handler-Zuordnung
	// in der Dropzone), hole sie jetzt nach — damit Stats angezeigt und die
	// Drift-Checkbox korrekt positioniert werden kann.
	if (!ctx.preview) {
		root.innerHTML = `<div class="msp-assistant-empty">${__("Analysiere Datei …")}</div>`;
		frappe.call({
			method: "msp.importers.assistant.analyze_file",
			args: { file_url: ctx.file_url },
			callback: (r) => {
				const m = r.message || {};
				if (m.preview) ctx.preview = m.preview;
				if (m.display_name) ctx.display_name = ctx.display_name || m.display_name;
				if (m.preview && m.preview.format_drift) ctx.format_drift = true;
				render_page(root, ctx, page);
			},
		});
		return;
	}

	render_page(root, ctx, page);
};

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

function render_page(root, ctx, page) {
	const state = {
		step: 1,                          // 1 = config, 2 = running, 3 = done
		config: {
			profile: ctx.suggested_profile || "",
			output_mode: "",
			acknowledge_format_drift: !!ctx.format_drift,
		},
		result: null,                     // füllt sich in Schritt 3
		profiles: [],
	};

	root.innerHTML = `
		<div class="msp-assistant">
			<div class="msp-stepper">
				<div class="step" data-step="1"><span class="num">1</span> ${__("Konfiguration")}</div>
				<div class="step" data-step="2"><span class="num">2</span> ${__("Import")}</div>
				<div class="step" data-step="3"><span class="num">3</span> ${__("Ergebnis")}</div>
			</div>
			<div class="msp-panel" data-panel="1">
				${render_config_panel(ctx)}
			</div>
			<div class="msp-panel" data-panel="2" hidden>
				${render_running_panel()}
			</div>
			<div class="msp-panel" data-panel="3" hidden>
				<!-- wird nach Import dynamisch gefüllt -->
			</div>
		</div>
	`;

	set_step(root, state.step);

	// Profile laden für Dropdown (Filter: parser_key = handler_key)
	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Supplier Import Profile",
			filters: { parser_key: ctx.handler_key, enabled: 1 },
			fields: ["name", "profile_name"],
			limit_page_length: 50,
		},
		callback: (r) => {
			state.profiles = r.message || [];
			populate_profile_select(root, state);
		},
	});

	// Handlers
	const btn_start = root.querySelector(".btn-start-import");
	btn_start.addEventListener("click", () => kick_off_import(root, state, ctx));
}

function render_config_panel(ctx) {
	const p = ctx.preview || {};
	const stat_parts = [];
	if (p.line_count != null) stat_parts.push(`<span class="stat"><strong>${p.line_count}</strong> ${__("Zeilen")}</span>`);
	if (p.customer_count != null) stat_parts.push(`<span class="stat"><strong>${p.customer_count}</strong> ${__("Kunden")}</span>`);
	if (p.product_count != null) stat_parts.push(`<span class="stat"><strong>${p.product_count}</strong> ${__("Produkte")}</span>`);
	if (p.period_label) stat_parts.push(`<span class="stat">${frappe.utils.escape_html(p.period_label)}</span>`);
	if (p.credit_note_lines) stat_parts.push(`<span class="stat pill-warn">${p.credit_note_lines} ${__("Gutschriftzeilen")}</span>`);

	return `
		<section class="msp-config">
			<header>
				<h3>${__("Zusammenfassung")}</h3>
				<div class="file-line">
					<span class="icon">${icon_for(ctx.file_url)}</span>
					<span class="name">${frappe.utils.escape_html(filename_of(ctx.file_url))}</span>
					<span class="sep">·</span>
					<span class="handler">${frappe.utils.escape_html(ctx.display_name || ctx.handler_key)}</span>
				</div>
				<div class="stats">${stat_parts.join(" ")}</div>
			</header>
			<div class="config-grid">
				<div class="form-row">
					<label>${__("Profil")}</label>
					<select class="form-control field-profile">
						<option value="">${__("Lade Profile …")}</option>
					</select>
					<div class="hint">${__("Legt Defaults wie Steuertemplate, AGBs und Titel fest.")}</div>
				</div>
				<div class="form-row">
					<label>${__("Ziel-Dokument")}</label>
					<select class="form-control field-output-mode">
						<option value="">${__("Profil-Default verwenden")}</option>
						<option value="Sales Invoice">${__("Ausgangsrechnung erzwingen")}</option>
						<option value="Delivery Note">${__("Lieferschein erzwingen")}</option>
					</select>
					<div class="hint">${__("Leer = der Customer.billing_mode entscheidet pro Kunde.")}</div>
				</div>
				<div class="form-row field-drift-wrapper">
					<label>
						<input type="checkbox" class="field-ack-drift"
							${ctx.format_drift ? "checked" : ""} />
						${__("Abweichendes Format akzeptieren")}
					</label>
					<div class="hint ${ctx.format_drift ? "warn" : ""}">
						${ctx.format_drift
							? __("Die Analyse hat ein abweichendes CSV-Layout erkannt. Nur aktivieren, wenn du die Quelle kennst.")
							: __("Aktivieren, falls der Parser die Datei ablehnt, obwohl sie inhaltlich passt.")}
					</div>
				</div>
			</div>
			<footer>
				<button class="btn btn-primary btn-start-import">
					${__("Import starten")} →
				</button>
			</footer>
		</section>
	`;
}

function render_running_panel() {
	return `
		<section class="msp-running">
			<div class="spin">⏳</div>
			<div class="label">${__("Import läuft …")}</div>
			<div class="hint">${__("Parst Zeilen, erzeugt Dokumente, aktualisiert Supply Subscriptions.")}</div>
			<div class="progress-note" hidden></div>
		</section>
	`;
}

function populate_profile_select(root, state) {
	const sel = root.querySelector(".field-profile");
	if (!sel) return;
	if (!state.profiles.length) {
		sel.innerHTML = `<option value="">${__("Kein aktives Profil gefunden")}</option>`;
		sel.disabled = true;
		return;
	}
	sel.innerHTML = state.profiles
		.map((p) => {
			const selected = p.name === state.config.profile ? "selected" : "";
			const label = p.profile_name || p.name;
			return `<option value="${frappe.utils.escape_html(p.name)}" ${selected}>${frappe.utils.escape_html(label)}</option>`;
		})
		.join("");
}

async function kick_off_import(root, state, ctx) {
	// Werte aus Form einsammeln
	state.config.profile = root.querySelector(".field-profile").value;
	state.config.output_mode = root.querySelector(".field-output-mode").value;
	state.config.acknowledge_format_drift =
		root.querySelector(".field-ack-drift")?.checked ? 1 : 0;

	if (!state.config.profile) {
		frappe.msgprint({ title: __("Profil fehlt"), message: __("Bitte ein Import-Profil auswählen."), indicator: "orange" });
		return;
	}

	set_step(root, 2);

	try {
		const response = await frappe.call({
			method: "msp.importers.assistant.process_file",
			args: {
				file_url: ctx.file_url,
				handler_key: ctx.handler_key,
				config: JSON.stringify(state.config),
			},
		});
		state.result = response.message || {};
		show_result(root, state, ctx);
	} catch (err) {
		state.result = { status: "Failed", message: extract_error_message(err) };
		show_result(root, state, ctx);
	}
}

function extract_error_message(err) {
	if (!err) return "Unbekannter Fehler";
	// Frappe-RPC-Errors kommen als { exc, exception, _server_messages, ... }
	if (err._server_messages) {
		try {
			const msgs = JSON.parse(err._server_messages);
			const first = Array.isArray(msgs) ? msgs[0] : msgs;
			const parsed = typeof first === "string" ? JSON.parse(first) : first;
			if (parsed && parsed.message) return parsed.message;
		} catch (_) { /* fallthrough */ }
	}
	if (typeof err === "string") return err;
	if (err.exception) return String(err.exception);
	if (err.message && typeof err.message === "string") return err.message;
	try { return JSON.stringify(err); } catch (_) { return String(err); }
}

function show_result(root, state, ctx) {
	set_step(root, 3);
	const r = state.result || {};
	const panel = root.querySelector(".msp-panel[data-panel='3']");

	const status_icon = { "Succeeded": "✓", "Partial": "◉", "Failed": "✗" }[r.status] || "?";
	const status_class = { "Succeeded": "ok", "Partial": "warn", "Failed": "error" }[r.status] || "warn";

	const run_link = r.run_name
		? `<a href="/app/supplier-import-run/${encodeURIComponent(r.run_name)}">${frappe.utils.escape_html(r.run_name)}</a>`
		: "—";

	panel.innerHTML = `
		<section class="msp-result ${status_class}">
			<div class="hero">
				<span class="icon">${status_icon}</span>
				<div>
					<div class="status">${__("Import abgeschlossen")} — <strong>${r.status || "?"}</strong></div>
					<div class="sub">Run ${run_link}</div>
				</div>
			</div>
			<div class="counters">
				<div class="counter"><strong>${r.document_count || 0}</strong><span>${__("Dokumente")}</span></div>
				<div class="counter"><strong>${r.line_count || 0}</strong><span>${__("Zeilen")}</span></div>
				<div class="counter"><strong>${r.skipped_count || 0}</strong><span>${__("Übersprungen")}</span></div>
				<div class="counter ${r.error_count ? 'counter--bad' : ''}"><strong>${r.error_count || 0}</strong><span>${__("Fehler")}</span></div>
			</div>
			${r.message ? `<div class="msg">${frappe.utils.escape_html(r.message)}</div>` : ""}
			<div class="actions">
				<a class="btn btn-primary" href="/app/supplier-import-run/${encodeURIComponent(r.run_name || "")}">
					${__("Run-Details öffnen")}
				</a>
				<a class="btn btn-default" href="/app/import-dropzone">
					${__("Weiteren Import starten")}
				</a>
			</div>
			${render_documents_block(r)}
		</section>
	`;

	// Nachladen: erzeugte Dokumente auflisten
	if (r.run_name) load_documents(panel, r.run_name);
}

function render_documents_block() {
	return `
		<div class="documents">
			<h4>${__("Erzeugte Dokumente")}</h4>
			<div class="documents-list"><span class="muted">${__("Lade …")}</span></div>
		</div>
	`;
}

async function load_documents(panel, run_name) {
	try {
		const response = await frappe.call({
			method: "msp.importers.assistant.run_documents",
			args: { run_name },
		});
		const entries = (response.message || []).sort((a, b) =>
			String(a.customer || "").localeCompare(String(b.customer || ""))
		);
		const list = panel.querySelector(".documents-list");
		if (!entries.length) {
			list.innerHTML = `<span class="muted">${__("Keine neuen Dokumente — alles übersprungen oder fehlgeschlagen.")}</span>`;
			return;
		}
		list.innerHTML = `
			<table class="table table-sm">
				<thead><tr>
					<th>${__("Kunde")}</th>
					<th>${__("Dokument")}</th>
					<th class="num">${__("Zeilen")}</th>
					<th class="num">${__("Summe (netto)")}</th>
				</tr></thead>
				<tbody>
					${entries.map((e) => `
						<tr>
							<td>${frappe.utils.escape_html(e.customer || "")}</td>
							<td><a href="/app/${slug(e.target_doc_type)}/${encodeURIComponent(e.target_doc_name)}">
								${frappe.utils.escape_html(e.target_doc_type)} ${frappe.utils.escape_html(e.target_doc_name)}
							</a></td>
							<td class="num">${e.line_count || 0}</td>
							<td class="num">${format_eur(e.total_amount)}</td>
						</tr>
					`).join("")}
				</tbody>
			</table>
		`;
	} catch (err) {
		console.error(err);
	}
}

function set_step(root, step) {
	root.querySelectorAll(".msp-stepper .step").forEach((el) => {
		const s = parseInt(el.dataset.step, 10);
		el.classList.toggle("active", s === step);
		el.classList.toggle("done", s < step);
	});
	root.querySelectorAll(".msp-panel").forEach((el) => {
		el.hidden = parseInt(el.dataset.panel, 10) !== step;
	});
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function filename_of(url) {
	return (url || "").split("/").pop();
}

function icon_for(url) {
	const n = (url || "").toLowerCase();
	if (n.endsWith(".zip")) return "🗜️";
	if (n.endsWith(".csv")) return "📄";
	return "📎";
}

function slug(doctype) {
	return (doctype || "").toLowerCase().replace(/\s+/g, "-");
}

function format_eur(v) {
	if (v == null || isNaN(v)) return "–";
	return Number(v).toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " €";
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

function inject_style(root) {
	if (root.querySelector("style[data-msp-assistant]")) return;
	const style = document.createElement("style");
	style.setAttribute("data-msp-assistant", "1");
	style.textContent = `
		.msp-assistant { padding: 10px; max-width: 980px; margin: 0 auto; }
		.msp-assistant-empty { padding: 40px; text-align: center; color: var(--text-muted); }

		.msp-stepper {
			display: flex; gap: 16px; margin-bottom: 28px;
			border-bottom: 1px solid var(--border-color);
			padding-bottom: 12px;
		}
		.msp-stepper .step {
			display: flex; align-items: center; gap: 8px;
			color: var(--text-muted); font-size: 14px;
		}
		.msp-stepper .step .num {
			width: 24px; height: 24px; border-radius: 50%;
			background: var(--bg-light-gray); color: var(--text-muted);
			display: flex; align-items: center; justify-content: center;
			font-size: 12px; font-weight: 600;
		}
		.msp-stepper .step.active { color: var(--heading-color); font-weight: 600; }
		.msp-stepper .step.active .num { background: var(--primary); color: #fff; }
		.msp-stepper .step.done .num { background: var(--green-500); color: #fff; }

		.msp-config header { margin-bottom: 20px; }
		.msp-config .file-line {
			display: flex; gap: 8px; align-items: baseline; margin: 8px 0 12px;
			font-size: 15px;
		}
		.msp-config .file-line .name { font-weight: 600; }
		.msp-config .file-line .sep { color: var(--text-muted); }
		.msp-config .file-line .handler { color: var(--text-muted); }
		.msp-config .stats .stat { margin-right: 16px; font-size: 13px; }
		.msp-config .stats strong { color: var(--heading-color); }
		.msp-config .stats .pill-warn { color: var(--orange-600); }

		.config-grid { display: grid; gap: 18px; max-width: 640px; }
		.config-grid .form-row label { font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: .04em; display: block; margin-bottom: 4px; }
		.config-grid .hint { font-size: 12px; color: var(--text-muted); margin-top: 4px; }
		.config-grid .hint.warn { color: var(--orange-600); }

		.msp-config footer { margin-top: 22px; }

		.msp-running { text-align: center; padding: 60px 20px; }
		.msp-running .spin { font-size: 48px; animation: msp-spin 2s linear infinite; display: inline-block; }
		.msp-running .label { font-size: 16px; margin-top: 12px; }
		.msp-running .hint { color: var(--text-muted); margin-top: 6px; }
		@keyframes msp-spin { from { transform: rotate(0); } to { transform: rotate(360deg); } }

		.msp-result .hero {
			display: flex; gap: 16px; align-items: center;
			padding: 16px 0 20px; border-bottom: 1px solid var(--border-color);
			margin-bottom: 20px;
		}
		.msp-result .hero .icon {
			font-size: 40px; width: 60px; height: 60px; border-radius: 50%;
			display: flex; align-items: center; justify-content: center;
			background: var(--bg-light-gray);
		}
		.msp-result.ok .hero .icon { background: var(--green-100); color: var(--green-600); }
		.msp-result.warn .hero .icon { background: var(--orange-100); color: var(--orange-600); }
		.msp-result.error .hero .icon { background: var(--red-100); color: var(--red-600); }
		.msp-result .status { font-size: 16px; }
		.msp-result .sub { color: var(--text-muted); font-size: 13px; margin-top: 2px; }

		.msp-result .counters { display: flex; gap: 16px; margin-bottom: 18px; }
		.msp-result .counter {
			background: var(--bg-light-gray); border-radius: 8px; padding: 14px 18px;
			flex: 1; text-align: center;
		}
		.msp-result .counter strong { display: block; font-size: 22px; font-weight: 600; }
		.msp-result .counter span { font-size: 12px; color: var(--text-muted); }
		.msp-result .counter--bad { background: var(--red-50); }
		.msp-result .counter--bad strong { color: var(--red-600); }

		.msp-result .actions { display: flex; gap: 8px; margin: 18px 0 24px; }
		.msp-result .msg { background: var(--red-50); color: var(--red-600); padding: 8px 12px; border-radius: 4px; margin-bottom: 12px; }

		.msp-result .documents h4 { margin: 20px 0 8px; }
		.msp-result .documents table { width: 100%; font-size: 13px; }
		.msp-result .documents td.num, .msp-result .documents th.num { text-align: right; }
		.msp-result .documents .muted { color: var(--text-muted); font-size: 13px; }
	`;
	root.appendChild(style);
}
