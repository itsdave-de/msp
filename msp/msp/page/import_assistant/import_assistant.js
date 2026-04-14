/**
 * Frappe-Page „Import-Assistent" — Wizard mit 3 Schritten:
 *   1. Konfiguration (+ Kundenkontext)
 *   2. Import läuft
 *   3. Ergebnis mit Counters, Top-Kunden, Dokumenten-Tabelle
 *
 * Nutzt Frappé-CSS-Variablen (--text-color, --card-bg, --primary, --red-500 …)
 * für Light-/Dark-Mode-Kompatibilität und konsistente Optik mit dem Desk.
 */

frappe.pages["import-assistant"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Import-Assistent"),
		single_column: true,
	});
	const root = page.main[0] || page.main;

	const ctx = frappe.route_options || {};
	frappe.route_options = {};

	if (!ctx.file_url || !ctx.handler_key) {
		root.innerHTML = `
			<div class="msp-wizard">
				<div class="msp-empty">
					<div class="msp-empty__icon">${ICON.arrow_left}</div>
					<h2 class="msp-empty__title">${__("Kein Kontext")}</h2>
					<p class="msp-empty__text">
						${__("Bitte starte den Import-Flow über die Dropzone.")}
					</p>
					<a class="btn btn-primary btn-sm" href="/app/import-dropzone">
						${__("Zur Dropzone")} →
					</a>
				</div>
			</div>`;
		inject_style(root);
		return;
	}

	if (!ctx.preview) {
		root.innerHTML = `<div class="msp-wizard"><div class="msp-empty"><span class="spinner spinner--lg"></span><p class="msp-empty__text">${__("Analysiere Datei …")}</p></div></div>`;
		inject_style(root);
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

function render_page(root, ctx, page) {
	const state = {
		step: 1,
		config: {
			profile: ctx.suggested_profile || "",
			output_mode: "",
			acknowledge_format_drift: !!ctx.format_drift,
		},
		result: null,
		profiles: [],
	};

	root.innerHTML = `
		<div class="msp-wizard">
			<header class="msp-wiz-head">
				<div class="msp-wiz-file">
					<span class="msp-wiz-file__icon">${icon_for(ctx.file_url)}</span>
					<div class="msp-wiz-file__meta">
						<div class="msp-wiz-file__name">${frappe.utils.escape_html(filename_of(ctx.file_url))}</div>
						<div class="msp-wiz-file__handler">${frappe.utils.escape_html(ctx.display_name || ctx.handler_key)}</div>
					</div>
				</div>
				<ol class="msp-steps">
					<li class="msp-step" data-step="1"><span>01</span>${__("Konfiguration")}</li>
					<li class="msp-step" data-step="2"><span>02</span>${__("Import")}</li>
					<li class="msp-step" data-step="3"><span>03</span>${__("Ergebnis")}</li>
				</ol>
			</header>

			<div class="msp-panel" data-panel="1">${render_config_panel(ctx)}</div>
			<div class="msp-panel" data-panel="2" hidden>${render_running_panel()}</div>
			<div class="msp-panel" data-panel="3" hidden></div>
		</div>
	`;

	inject_style(root);
	set_step(root, state.step);

	// Profile laden
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

	// Kundenkontext-Block (optional, wenn Preview-Zählungen da sind)
	enhance_with_customer_context(root, ctx);

	root.querySelector(".btn-start-import").addEventListener("click", () =>
		kick_off_import(root, state, ctx)
	);
}

// ---------------------------------------------------------------------------
// Panel 1: Konfiguration
// ---------------------------------------------------------------------------

function render_config_panel(ctx) {
	const p = ctx.preview || {};
	const hero = render_hero_stats(p);
	return `
		<section class="msp-config">
			${hero}

			<div class="msp-context" data-role="customer-context" hidden>
				<h3 class="msp-h3">${__("Kundenkontext")}</h3>
				<div class="msp-context__body"></div>
			</div>

			<h3 class="msp-h3">${__("Konfiguration")}</h3>
			<div class="msp-config__grid">
				<div class="msp-field">
					<label>${__("Profil")}</label>
					<select class="form-control field-profile">
						<option value="">${__("Lade Profile …")}</option>
					</select>
					<div class="msp-hint">${__("Defaults für Steuertemplate, AGBs und Titelpräfix.")}</div>
				</div>
				<div class="msp-field">
					<label>${__("Ziel-Dokument")}</label>
					<select class="form-control field-output-mode">
						<option value="">${__("Profil-Default verwenden")}</option>
						<option value="Sales Invoice">${__("Ausgangsrechnung erzwingen")}</option>
						<option value="Delivery Note">${__("Lieferschein erzwingen")}</option>
					</select>
					<div class="msp-hint">${__("Leer = Customer.billing_mode entscheidet pro Kunde.")}</div>
				</div>
				<div class="msp-field msp-field--wide">
					<label class="msp-check">
						<input type="checkbox" class="field-ack-drift" ${ctx.format_drift ? "checked" : ""} />
						<span>${__("Abweichendes Format akzeptieren")}</span>
					</label>
					<div class="msp-hint ${ctx.format_drift ? "msp-hint--warn" : ""}">
						${ctx.format_drift
							? __("Die Analyse hat ein abweichendes CSV-Layout erkannt. Nur aktivieren, wenn du die Quelle kennst.")
							: __("Aktivieren, falls der Parser die Datei ablehnt, obwohl sie inhaltlich passt.")}
					</div>
				</div>
			</div>

			<footer class="msp-config__foot">
				<a class="msp-back" href="/app/import-dropzone">← ${__("Zur Dropzone")}</a>
				<button class="btn btn-primary btn-start-import">
					${__("Import starten")} <span class="arr">→</span>
				</button>
			</footer>
		</section>
	`;
}

function render_hero_stats(p) {
	const cells = [];
	if (p.line_count != null) cells.push(stat_cell(__("Zeilen"), p.line_count, false, "primary", ICON.rows));
	if (p.customer_count != null) cells.push(stat_cell(__("Kunden"), p.customer_count, false, "success", ICON.users));
	if (p.product_count != null) cells.push(stat_cell(__("Produkte"), p.product_count, false, "info", ICON.box));
	if (p.period_label) cells.push(stat_cell(__("Zeitraum"), p.period_label, true, "neutral", ICON.calendar));
	if (p.credit_note_lines) cells.push(stat_cell(__("Gutschriften"), p.credit_note_lines, false, "accent", ICON.refund));
	if (!cells.length) return "";
	return `<div class="msp-hero-grid">${cells.join("")}</div>`;
}

function stat_cell(label, value, is_text, tone, icon) {
	const v = is_text ? frappe.utils.escape_html(String(value)) : format_int(value);
	return `
		<div class="msp-hero-stat msp-hero-stat--${tone || "neutral"}">
			<div class="msp-hero-stat__head">
				<span class="msp-hero-stat__icon">${icon || ""}</span>
				<span class="msp-hero-stat__label">${frappe.utils.escape_html(label)}</span>
			</div>
			<div class="msp-hero-stat__value">${v}</div>
		</div>
	`;
}

async function enhance_with_customer_context(root, ctx) {
	// Vorerst deaktiviert — die Preview liefert uns keine einzelnen Kunden-Refs.
	// Erweiterungspunkt für später: analyze_file könnte die Refs mit zurückgeben,
	// dann zeigen wir hier bekannte vs. neue Kunden an.
	void root; void ctx;
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

// ---------------------------------------------------------------------------
// Panel 2: Import läuft
// ---------------------------------------------------------------------------

function render_running_panel() {
	return `
		<section class="msp-running">
			<div class="msp-running__spin"></div>
			<div class="msp-running__label">${__("Import läuft")}</div>
			<div class="msp-running__hint">${__("Parst Zeilen, erzeugt Dokumente, aktualisiert Supply Subscriptions …")}</div>
		</section>
	`;
}

async function kick_off_import(root, state, ctx) {
	state.config.profile = root.querySelector(".field-profile").value;
	state.config.output_mode = root.querySelector(".field-output-mode").value;
	state.config.acknowledge_format_drift =
		root.querySelector(".field-ack-drift")?.checked ? 1 : 0;

	if (!state.config.profile) {
		frappe.msgprint({
			title: __("Profil fehlt"),
			message: __("Bitte ein Import-Profil auswählen."),
			indicator: "orange",
		});
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
		await show_result(root, state, ctx);
	} catch (err) {
		state.result = { status: "Failed", message: extract_error_message(err) };
		await show_result(root, state, ctx);
	}
}

function extract_error_message(err) {
	if (!err) return "Unbekannter Fehler";
	if (err._server_messages) {
		try {
			const msgs = JSON.parse(err._server_messages);
			const first = Array.isArray(msgs) ? msgs[0] : msgs;
			const parsed = typeof first === "string" ? JSON.parse(first) : first;
			if (parsed && parsed.message) return parsed.message;
		} catch (_) {}
	}
	if (typeof err === "string") return err;
	if (err.exception) return String(err.exception);
	if (err.message && typeof err.message === "string") return err.message;
	try { return JSON.stringify(err); } catch (_) { return String(err); }
}

// ---------------------------------------------------------------------------
// Panel 3: Ergebnis
// ---------------------------------------------------------------------------

async function show_result(root, state, ctx) {
	set_step(root, 3);
	const r = state.result || {};
	const panel = root.querySelector(".msp-panel[data-panel='3']");

	const status_label = {
		"Succeeded": __("Erfolgreich"),
		"Partial": __("Teilweise"),
		"Failed": __("Fehlgeschlagen"),
	}[r.status] || (r.status || "?");
	const status_cls = {
		"Succeeded": "ok", "Partial": "warn", "Failed": "error",
	}[r.status] || "warn";

	const run_link = r.run_name
		? `<a href="/app/supplier-import-run/${encodeURIComponent(r.run_name)}">${frappe.utils.escape_html(r.run_name)}</a>`
		: "—";

	panel.innerHTML = `
		<section class="msp-result msp-result--${status_cls}">
			<header class="msp-result__head">
				<div class="msp-result__status">
					<span class="msp-result__icon">${status_icon_svg(status_cls)}</span>
					<div>
						<div class="msp-result__title">${__("Import abgeschlossen")} — ${status_label}</div>
						<div class="msp-result__sub">Run ${run_link}</div>
					</div>
				</div>
				<div class="msp-result__cta">
					${r.run_name ? `<a class="btn btn-default btn-sm" href="/app/supplier-import-run/${encodeURIComponent(r.run_name)}">${__("Run-Details")} →</a>` : ""}
					<a class="btn btn-primary btn-sm" href="/app/import-dropzone">${__("Weiterer Import")} →</a>
				</div>
			</header>

			<div class="msp-counters">
				<div class="msp-counter msp-counter--primary">
					<div class="msp-counter__head">${ICON.doc} <span>${__("Dokumente")}</span></div>
					<div class="msp-counter__value">${format_int(r.document_count || 0)}</div>
				</div>
				<div class="msp-counter msp-counter--neutral">
					<div class="msp-counter__head">${ICON.rows} <span>${__("Zeilen gesamt")}</span></div>
					<div class="msp-counter__value">${format_int(r.line_count || 0)}</div>
				</div>
				<div class="msp-counter msp-counter--muted">
					<div class="msp-counter__head">${ICON.skip} <span>${__("Übersprungen")}</span></div>
					<div class="msp-counter__value">${format_int(r.skipped_count || 0)}</div>
				</div>
				<div class="msp-counter ${r.error_count ? 'msp-counter--bad' : 'msp-counter--ok'}">
					<div class="msp-counter__head">${r.error_count ? ICON.warning : ICON.check} <span>${__("Fehler")}</span></div>
					<div class="msp-counter__value">${format_int(r.error_count || 0)}</div>
				</div>
			</div>

			${r.message ? `<div class="msp-result__msg">${frappe.utils.escape_html(r.message)}</div>` : ""}

			<div class="msp-summary" data-role="summary" hidden>
				<h3 class="msp-h3">${__("Top-Kunden nach Summe")}</h3>
				<div class="msp-summary__body"></div>
			</div>

			<div class="msp-documents">
				<h3 class="msp-h3">${__("Erzeugte Dokumente")}</h3>
				<div class="msp-documents__body"><span class="muted">${__("Lade …")}</span></div>
			</div>
		</section>
	`;

	if (r.run_name) {
		load_summary(panel, r.run_name);
		load_documents(panel, r.run_name);
	}
}

function status_icon_svg(cls) {
	if (cls === "ok")
		return `<svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5 9-11"/></svg>`;
	if (cls === "error")
		return `<svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>`;
	return `<svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></svg>`;
}

async function load_summary(panel, run_name) {
	try {
		const r = await frappe.call({
			method: "msp.importers.assistant.run_summary",
			args: { run_name, top_n: 5 },
		});
		const m = r.message || {};
		const top = m.top_customers || [];
		if (!top.length) return;
		const sum_el = panel.querySelector('[data-role="summary"]');
		const max = Math.max(...top.map((c) => Number(c.total_amount) || 0), 1);
		const html = top.map((c, idx) => {
			const pct = ((Number(c.total_amount) || 0) / max * 100).toFixed(1);
			const display = c.customer_name || c.customer;
			const ref = c.customer_name ? c.customer : "";
			return `
				<div class="msp-top-row">
					<div class="msp-top-row__rank">${idx + 1}</div>
					<a class="msp-top-row__customer" href="/app/customer/${encodeURIComponent(c.customer)}">
						<span class="msp-top-row__name">${frappe.utils.escape_html(display)}</span>
						${ref ? `<span class="msp-top-row__ref">${frappe.utils.escape_html(ref)}</span>` : ""}
					</a>
					<div class="msp-top-row__bar">
						<div class="msp-top-row__bar-fill" style="width: ${pct}%"></div>
					</div>
					<div class="msp-top-row__sub">
						${c.line_count} ${__("Zeilen")} · ${c.documents} ${__("Dok.")}
					</div>
					<div class="msp-top-row__amount">${format_eur(c.total_amount)}</div>
				</div>
			`;
		}).join("");
		const totals = m.totals || {};
		const foot = `
			<div class="msp-top-foot">
				<span>${format_int(totals.customers)} ${__("Kunden")}</span>
				<span>${format_int(totals.documents)} ${__("Dokumente")}</span>
				<span><strong>${format_eur(totals.total_created)}</strong> ${__("gesamt netto")}</span>
			</div>
		`;
		sum_el.hidden = false;
		sum_el.querySelector(".msp-summary__body").innerHTML = html + foot;
	} catch (_) { /* non-blocking */ }
}

async function load_documents(panel, run_name) {
	try {
		const response = await frappe.call({
			method: "msp.importers.assistant.run_documents",
			args: { run_name },
		});
		const entries = (response.message || []).sort((a, b) =>
			String(a.customer_name || a.customer || "").localeCompare(String(b.customer_name || b.customer || ""))
		);
		const body = panel.querySelector(".msp-documents__body");
		if (!entries.length) {
			body.innerHTML = `<div class="muted">${__("Keine neuen Dokumente — alles übersprungen oder fehlgeschlagen.")}</div>`;
			return;
		}
		body.innerHTML = `
			<div class="msp-table-wrap">
			<table class="msp-table">
				<thead><tr>
					<th>${__("Kunde")}</th>
					<th>${__("Dokument")}</th>
					<th class="num">${__("Zeilen")}</th>
					<th class="num">${__("Summe (netto)")}</th>
				</tr></thead>
				<tbody>
					${entries.map((e) => {
						const name = e.customer_name || e.customer || "";
						const ref = e.customer_name && e.customer ? e.customer : "";
						return `
							<tr>
								<td>
									<a class="msp-cust-link" href="/app/customer/${encodeURIComponent(e.customer || "")}">
										<span class="msp-cust-name">${frappe.utils.escape_html(name)}</span>
										${ref ? `<span class="msp-cust-ref">${frappe.utils.escape_html(ref)}</span>` : ""}
									</a>
								</td>
								<td>
									<a href="/app/${slug(e.target_doc_type)}/${encodeURIComponent(e.target_doc_name)}">
										<span class="msp-doc-type">${frappe.utils.escape_html(e.target_doc_type)}</span>
										<span class="msp-doc-name">${frappe.utils.escape_html(e.target_doc_name)}</span>
									</a>
								</td>
								<td class="num">${format_int(e.line_count || 0)}</td>
								<td class="num">${format_eur(e.total_amount)}</td>
							</tr>
						`;
					}).join("")}
				</tbody>
			</table>
			</div>
		`;
	} catch (err) { console.error(err); }
}

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

const ICON = {
	arrow_left: `<svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5"/><path d="M12 19l-7-7 7-7"/></svg>`,
	rows: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M3 12h18"/><path d="M3 18h18"/></svg>`,
	users: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9.5" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9"/><path d="M16 3.1a4 4 0 0 1 0 7.8"/></svg>`,
	box: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><path d="M3.3 7l8.7 5 8.7-5"/><path d="M12 22V12"/></svg>`,
	calendar: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>`,
	refund: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9h13a5 5 0 0 1 0 10h-2"/><path d="M7 5L3 9l4 4"/></svg>`,
	doc: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h8M8 17h6"/></svg>`,
	skip: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4l10 8-10 8V4z"/><path d="M19 5v14"/></svg>`,
	warning: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>`,
	check: `<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg>`,
};

// ---------------------------------------------------------------------------
// Utils
// ---------------------------------------------------------------------------

function set_step(root, step) {
	root.querySelectorAll(".msp-step").forEach((el) => {
		const s = parseInt(el.dataset.step, 10);
		el.classList.toggle("is-active", s === step);
		el.classList.toggle("is-done", s < step);
	});
	root.querySelectorAll(".msp-panel").forEach((el) => {
		el.hidden = parseInt(el.dataset.panel, 10) !== step;
	});
}

function filename_of(url) {
	return (url || "").split("/").pop();
}

function icon_for(url) {
	const n = (url || "").toLowerCase();
	if (n.endsWith(".zip"))
		return "<svg viewBox='0 0 24 24' width='22' height='22' fill='none' stroke='currentColor' stroke-width='1.6'><rect x='4' y='3' width='16' height='18' rx='2'/><path d='M10 3v4h4V3'/><path d='M10 9v2h4v2h-4v2h4v2h-4'/></svg>";
	return "<svg viewBox='0 0 24 24' width='22' height='22' fill='none' stroke='currentColor' stroke-width='1.6'><path d='M6 3h9l4 4v14a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z'/><path d='M15 3v4h4'/><path d='M8 14h8M8 18h6'/></svg>";
}

function slug(doctype) {
	return (doctype || "").toLowerCase().replace(/\s+/g, "-");
}

function format_int(n) {
	return Number(n || 0).toLocaleString("de-DE");
}

function format_eur(v) {
	if (v == null || isNaN(v)) return "–";
	return Number(v).toLocaleString("de-DE", {
		minimumFractionDigits: 2, maximumFractionDigits: 2,
	}) + " €";
}

// ---------------------------------------------------------------------------
// Styles — Frappé-Variablen (Light/Dark-kompatibel)
// ---------------------------------------------------------------------------

function inject_style(root) {
	const style = document.createElement("style");
	style.textContent = `
		.msp-wizard {
			--msp-accent: #e73249;
			--msp-radius: 10px;
			--msp-shadow-card: 0 1px 2px rgba(15, 23, 42, 0.04);

			max-width: 1120px;
			margin: 0 auto;
			padding: var(--padding-sm) var(--padding-lg) var(--padding-2xl);
			color: var(--text-color);
			font-family: inherit;
		}
		@media (max-width: 640px) {
			.msp-wizard { padding: var(--padding-xs) var(--padding-md) var(--padding-xl); }
		}

		.msp-empty {
			min-height: 360px;
			display: flex; flex-direction: column; align-items: center; justify-content: center;
			gap: 14px; text-align: center;
		}
		.msp-empty__icon { color: var(--text-muted); }
		.msp-empty__title { font-size: 20px; font-weight: 600; margin: 0; color: var(--heading-color); }
		.msp-empty__text { color: var(--text-muted); font-size: 14px; margin: 0; }

		/* ---------- Header + Stepper ---------- */
		.msp-wiz-head {
			display: grid;
			grid-template-columns: minmax(0, 1fr) auto;
			gap: var(--padding-xl);
			align-items: center;
			padding: var(--padding-lg) 0 var(--padding-md);
			border-bottom: 1px solid var(--border-color);
			margin-bottom: var(--padding-lg);
		}
		@media (max-width: 720px) {
			.msp-wiz-head { grid-template-columns: 1fr; gap: var(--padding-md); }
		}
		.msp-wiz-file {
			display: flex; gap: 12px; align-items: center;
			min-width: 0;
		}
		.msp-wiz-file__icon {
			width: 44px; height: 44px; border-radius: 10px;
			background: var(--subtle-fg);
			display: flex; align-items: center; justify-content: center;
			color: var(--text-muted);
			flex: none;
		}
		.msp-wiz-file__meta { min-width: 0; }
		.msp-wiz-file__name {
			font-size: 15px; font-weight: 600; color: var(--heading-color);
			letter-spacing: -0.01em;
			white-space: nowrap; text-overflow: ellipsis; overflow: hidden;
		}
		.msp-wiz-file__handler { font-size: 12.5px; color: var(--text-muted); }

		.msp-steps {
			list-style: none;
			display: flex; gap: var(--padding-lg);
			margin: 0; padding: 0;
		}
		.msp-step {
			display: flex; gap: 10px; align-items: center;
			font-size: 13px; color: var(--text-muted);
			font-weight: 500;
		}
		.msp-step span {
			display: inline-flex; align-items: center; justify-content: center;
			min-width: 26px; height: 26px;
			padding: 0 7px;
			border: 1px solid var(--border-color);
			border-radius: 6px;
			font-size: 11px;
			font-family: var(--font-stack-monospace, "SF Mono", Menlo, Consolas, monospace);
			color: var(--text-muted);
			font-weight: 600;
			background: var(--card-bg);
		}
		.msp-step.is-active { color: var(--heading-color); font-weight: 600; }
		.msp-step.is-active span {
			border-color: var(--primary);
			color: var(--primary);
			background: var(--alert-bg-info);
		}
		.msp-step.is-done span {
			background: var(--green-500);
			border-color: var(--green-500);
			color: #fff;
		}

		/* ---------- Config Panel ---------- */
		.msp-config { animation: msp-fade-in .3s ease both; }
		.msp-h3 {
			font-size: 12px;
			text-transform: uppercase;
			letter-spacing: .1em;
			color: var(--text-muted);
			font-weight: 600;
			margin: 0 0 var(--padding-sm) 0;
		}

		.msp-hero-grid {
			display: grid;
			grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
			gap: var(--padding-sm);
			margin-bottom: var(--padding-xl);
		}
		.msp-hero-stat {
			position: relative;
			padding: var(--padding-md);
			background: var(--card-bg);
			border: 1px solid var(--border-color);
			border-radius: var(--msp-radius);
			overflow: hidden;
			box-shadow: var(--msp-shadow-card);
		}
		.msp-hero-stat::before {
			content: ""; position: absolute; left: 0; top: 0; bottom: 0;
			width: 3px; background: var(--border-color);
		}
		.msp-hero-stat--primary::before { background: var(--primary); }
		.msp-hero-stat--success::before { background: var(--green-500); }
		.msp-hero-stat--info::before { background: var(--blue-500); }
		.msp-hero-stat--accent::before  { background: var(--msp-accent); }
		.msp-hero-stat--neutral::before { background: var(--border-color); }

		.msp-hero-stat__head {
			display: flex; align-items: center; gap: 6px;
			margin-bottom: 6px;
		}
		.msp-hero-stat__icon {
			display: inline-flex; align-items: center; justify-content: center;
			width: 22px; height: 22px; border-radius: 5px;
			background: var(--subtle-fg);
			color: var(--text-muted);
		}
		.msp-hero-stat--primary .msp-hero-stat__icon { background: var(--alert-bg-info); color: var(--alert-text-info); }
		.msp-hero-stat--success .msp-hero-stat__icon { background: var(--alert-bg-success); color: var(--alert-text-success); }
		.msp-hero-stat--info .msp-hero-stat__icon { background: var(--alert-bg-info); color: var(--alert-text-info); }
		.msp-hero-stat--accent .msp-hero-stat__icon { background: var(--alert-bg-danger); color: var(--msp-accent); }

		.msp-hero-stat__label {
			font-size: 11px;
			text-transform: uppercase;
			letter-spacing: .08em;
			color: var(--text-muted);
			font-weight: 600;
		}
		.msp-hero-stat__value {
			font-size: 24px; font-weight: 700; line-height: 1.1;
			font-variant-numeric: tabular-nums;
			letter-spacing: -0.02em;
			color: var(--heading-color);
		}
		.msp-hero-stat--accent .msp-hero-stat__value { color: var(--msp-accent); }

		.msp-context { margin: var(--padding-lg) 0; }

		.msp-config__grid {
			display: grid;
			grid-template-columns: 1fr 1fr;
			gap: var(--padding-lg);
			max-width: 720px;
		}
		@media (max-width: 640px) { .msp-config__grid { grid-template-columns: 1fr; } }
		.msp-field label {
			display: block;
			font-size: 11px;
			text-transform: uppercase;
			letter-spacing: .08em;
			color: var(--text-muted);
			font-weight: 600;
			margin-bottom: 6px;
		}
		.msp-field--wide { grid-column: 1 / -1; }
		.msp-check { display: flex; align-items: center; gap: 8px; cursor: pointer; }
		.msp-check span { font-size: 13.5px; color: var(--text-color); font-weight: 500; text-transform: none; letter-spacing: 0; }
		.msp-hint {
			font-size: 12px; color: var(--text-muted); margin-top: 6px;
			line-height: 1.45;
		}
		.msp-hint--warn { color: var(--alert-text-warning); }

		.msp-config__foot {
			display: flex; justify-content: space-between; align-items: center;
			margin-top: var(--padding-xl); padding-top: var(--padding-md);
			border-top: 1px solid var(--border-color);
		}
		.msp-back {
			font-size: 13px; color: var(--text-muted); text-decoration: none;
		}
		.msp-back:hover { color: var(--primary); }
		.arr { margin-left: 4px; }

		/* ---------- Running Panel ---------- */
		.msp-running {
			min-height: 320px;
			display: flex; flex-direction: column; align-items: center; justify-content: center;
			gap: 14px; text-align: center;
			animation: msp-fade-in .3s ease both;
		}
		.msp-running__spin {
			width: 40px; height: 40px; border-radius: 50%;
			border: 3px solid var(--border-color); border-top-color: var(--primary);
			animation: msp-spin .9s linear infinite;
		}
		.msp-running__label { font-size: 18px; font-weight: 600; color: var(--heading-color); }
		.msp-running__hint { font-size: 13px; color: var(--text-muted); }

		/* ---------- Result Panel ---------- */
		.msp-result { animation: msp-fade-in .3s ease both; }
		.msp-result__head {
			display: flex; justify-content: space-between; align-items: center;
			gap: var(--padding-md); flex-wrap: wrap;
			padding-bottom: var(--padding-md); border-bottom: 1px solid var(--border-color);
			margin-bottom: var(--padding-lg);
		}
		.msp-result__status { display: flex; gap: 14px; align-items: center; }
		.msp-result__icon {
			width: 52px; height: 52px; border-radius: 50%;
			display: flex; align-items: center; justify-content: center;
			background: var(--subtle-fg); color: var(--text-muted);
			flex: none;
		}
		.msp-result--ok .msp-result__icon { background: var(--alert-bg-success); color: var(--alert-text-success); }
		.msp-result--warn .msp-result__icon { background: var(--alert-bg-warning); color: var(--alert-text-warning); }
		.msp-result--error .msp-result__icon { background: var(--alert-bg-danger); color: var(--alert-text-danger); }
		.msp-result__title { font-size: 18px; font-weight: 600; color: var(--heading-color); }
		.msp-result__sub { font-size: 13px; color: var(--text-muted); margin-top: 2px; }
		.msp-result__sub a { font-family: var(--font-stack-monospace, "SF Mono", Menlo, Consolas, monospace); }
		.msp-result__cta { display: flex; gap: 8px; }
		.msp-result__msg {
			background: var(--alert-bg-danger); color: var(--alert-text-danger);
			padding: 10px 14px; border-radius: 6px; margin-bottom: var(--padding-md);
			font-size: 13px;
		}

		/* ---------- Counters ---------- */
		.msp-counters {
			display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--padding-sm);
			margin-bottom: var(--padding-xl);
		}
		@media (max-width: 640px) { .msp-counters { grid-template-columns: repeat(2, 1fr); } }
		.msp-counter {
			background: var(--card-bg);
			border: 1px solid var(--border-color);
			border-radius: var(--msp-radius);
			padding: var(--padding-md);
			position: relative;
			overflow: hidden;
			box-shadow: var(--msp-shadow-card);
		}
		.msp-counter::before {
			content: ""; position: absolute; left: 0; top: 0; bottom: 0;
			width: 3px; background: var(--border-color);
		}
		.msp-counter--primary::before { background: var(--primary); }
		.msp-counter--ok::before  { background: var(--green-500); }
		.msp-counter--bad::before { background: var(--red-500); }
		.msp-counter--muted::before { background: var(--border-color); }

		.msp-counter__head {
			display: flex; align-items: center; gap: 6px;
			font-size: 11px;
			text-transform: uppercase; letter-spacing: .08em;
			color: var(--text-muted); font-weight: 600;
			margin-bottom: 10px;
		}
		.msp-counter__head svg { color: var(--text-muted); }
		.msp-counter--primary .msp-counter__head svg { color: var(--primary); }
		.msp-counter--ok .msp-counter__head svg { color: var(--green-500); }
		.msp-counter--bad .msp-counter__head svg { color: var(--red-500); }
		.msp-counter__value {
			font-size: 32px; font-weight: 700; line-height: 1;
			font-variant-numeric: tabular-nums;
			letter-spacing: -0.02em;
			color: var(--heading-color);
		}
		.msp-counter--bad .msp-counter__value { color: var(--red-600, var(--red-500)); }

		/* ---------- Top-Customer-Liste ---------- */
		.msp-summary { margin: var(--padding-lg) 0 var(--padding-xl); }
		.msp-top-row {
			display: grid;
			grid-template-columns: 28px minmax(180px, 1.4fr) minmax(120px, 2fr) auto auto;
			gap: var(--padding-sm);
			align-items: center;
			padding: 10px 0;
			border-bottom: 1px solid var(--border-color);
			font-size: 13.5px;
		}
		.msp-top-row:last-child { border-bottom: 0; }
		.msp-top-row__rank {
			font-family: var(--font-stack-monospace, "SF Mono", Menlo, Consolas, monospace);
			color: var(--text-muted);
			font-size: 12px;
			font-weight: 600;
		}
		.msp-top-row__customer {
			display: flex; flex-direction: column; gap: 1px;
			text-decoration: none; color: var(--text-color);
			min-width: 0;
		}
		.msp-top-row__customer:hover .msp-top-row__name { color: var(--primary); }
		.msp-top-row__name {
			font-weight: 600; color: var(--text-color);
			white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
		}
		.msp-top-row__ref {
			font-size: 11px; color: var(--text-muted);
			font-family: var(--font-stack-monospace, "SF Mono", Menlo, Consolas, monospace);
		}
		.msp-top-row__bar {
			height: 6px; background: var(--subtle-fg); border-radius: 999px;
			overflow: hidden;
		}
		.msp-top-row__bar-fill {
			height: 100%; background: var(--primary);
			border-radius: 999px;
			transition: width .4s ease;
		}
		.msp-top-row__sub { color: var(--text-muted); font-size: 12px; white-space: nowrap; }
		.msp-top-row__amount {
			font-weight: 600; font-variant-numeric: tabular-nums;
			min-width: 100px; text-align: right;
			color: var(--heading-color);
		}
		.msp-top-foot {
			display: flex; gap: var(--padding-md); justify-content: flex-end;
			padding-top: 12px; font-size: 12.5px; color: var(--text-muted);
		}
		.msp-top-foot strong { color: var(--heading-color); font-weight: 600; font-variant-numeric: tabular-nums; }

		/* ---------- Documents table ---------- */
		.msp-documents { margin-top: var(--padding-md); }
		.msp-table-wrap {
			border: 1px solid var(--border-color);
			border-radius: var(--msp-radius);
			overflow: hidden;
			background: var(--card-bg);
			box-shadow: var(--msp-shadow-card);
		}
		.msp-table { width: 100%; border-collapse: collapse; font-size: 13px; }
		.msp-table th {
			text-align: left;
			font-size: 11px; text-transform: uppercase; letter-spacing: .08em;
			color: var(--text-muted); font-weight: 600;
			padding: 10px var(--padding-md);
			background: var(--subtle-accent);
			border-bottom: 1px solid var(--border-color);
		}
		.msp-table td {
			padding: 10px var(--padding-md);
			border-bottom: 1px solid var(--border-color);
			color: var(--text-color);
			vertical-align: middle;
		}
		.msp-table tbody tr:last-child td { border-bottom: 0; }
		.msp-table tr:hover td { background: var(--highlight-color); }
		.msp-table td.num, .msp-table th.num { text-align: right; font-variant-numeric: tabular-nums; }
		.msp-table a { color: var(--text-color); text-decoration: none; }
		.msp-table a:hover { color: var(--primary); }

		.msp-cust-link { display: flex; flex-direction: column; gap: 1px; min-width: 0; }
		.msp-cust-name { font-weight: 500; color: var(--text-color); }
		.msp-cust-ref {
			font-size: 11px; color: var(--text-muted);
			font-family: var(--font-stack-monospace, "SF Mono", Menlo, Consolas, monospace);
		}

		.msp-doc-type {
			display: inline-block;
			padding: 1px 7px;
			background: var(--subtle-fg);
			color: var(--text-muted);
			border-radius: 4px;
			font-size: 11px;
			font-weight: 500;
			margin-right: 6px;
		}
		.msp-doc-name {
			font-family: var(--font-stack-monospace, "SF Mono", Menlo, Consolas, monospace);
			font-size: 12.5px;
			color: var(--text-muted);
		}

		.muted { color: var(--text-muted); }
		.num { text-align: right; }

		.spinner {
			display: inline-block;
			width: 10px; height: 10px; border-radius: 50%;
			border: 1.5px solid var(--border-color);
			border-top-color: var(--primary);
			animation: msp-spin .8s linear infinite;
		}
		.spinner--lg { width: 32px; height: 32px; border-width: 3px; }

		@keyframes msp-fade-in {
			from { opacity: 0; transform: translateY(4px); }
			to   { opacity: 1; transform: translateY(0); }
		}
		@keyframes msp-spin {
			from { transform: rotate(0); }
			to   { transform: rotate(360deg); }
		}
	`;
	root.appendChild(style);
}
