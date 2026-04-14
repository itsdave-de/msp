/**
 * Frappe-Page „Import-Assistent" — Wizard mit 3 Schritten:
 *   1. Konfiguration (+ Kundenkontext)
 *   2. Import läuft
 *   3. Ergebnis mit Counters, Top-Kunden, Dokumenten-Tabelle
 *
 * Design: Editorial Data. Große Zahlen als Anker, dezente Akzentfarben.
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
					<div class="msp-empty__icon">↩</div>
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
	if (p.line_count != null) cells.push(stat_cell(__("Zeilen"), p.line_count));
	if (p.customer_count != null) cells.push(stat_cell(__("Kunden"), p.customer_count));
	if (p.product_count != null) cells.push(stat_cell(__("Produkte"), p.product_count));
	if (p.period_label) cells.push(stat_cell(__("Zeitraum"), p.period_label, true));
	if (p.credit_note_lines) cells.push(stat_cell(__("Gutschriften"), p.credit_note_lines, false, "accent"));
	if (!cells.length) return "";
	return `<div class="msp-hero-grid">${cells.join("")}</div>`;
}

function stat_cell(label, value, is_text, accent) {
	const v = is_text ? frappe.utils.escape_html(String(value)) : format_int(value);
	return `
		<div class="msp-hero-stat ${accent ? `msp-hero-stat--${accent}` : ""}">
			<div class="msp-hero-stat__value">${v}</div>
			<div class="msp-hero-stat__label">${frappe.utils.escape_html(label)}</div>
		</div>
	`;
}

async function enhance_with_customer_context(root, ctx) {
	// Der Preview kennt nur customer_count, nicht die einzelnen Refs. Wir
	// holen uns die Liste indirekt aus der Datei (erneute Analyse reicht nicht
	// — wir haben die Rows dort nicht). Um den Wizard trotzdem aussagekräftig
	// zu machen: neuer Endpoint analyze_file hat das nicht. Also machen wir
	// hier einen schnellen SQL-Call per whitelisted Helper: wir nutzen die
	// Preview-Customers nicht, weil sie nicht übermittelt werden. Stattdessen
	// lassen wir den Block dynamisch blenden, wenn das Frontend die Refs
	// nicht hat. (Erweiterung für später: analyze_file liefert auch die Liste.)
	// Bleibt vorerst hidden.
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
					<div class="msp-counter__value">${format_int(r.document_count || 0)}</div>
					<div class="msp-counter__label">${__("Dokumente")}</div>
				</div>
				<div class="msp-counter">
					<div class="msp-counter__value">${format_int(r.line_count || 0)}</div>
					<div class="msp-counter__label">${__("Zeilen gesamt")}</div>
				</div>
				<div class="msp-counter">
					<div class="msp-counter__value">${format_int(r.skipped_count || 0)}</div>
					<div class="msp-counter__label">${__("Übersprungen")}</div>
				</div>
				<div class="msp-counter ${r.error_count ? 'msp-counter--bad' : ''}">
					<div class="msp-counter__value">${format_int(r.error_count || 0)}</div>
					<div class="msp-counter__label">${__("Fehler")}</div>
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
			return `
				<div class="msp-top-row">
					<div class="msp-top-row__rank">${idx + 1}</div>
					<a class="msp-top-row__customer" href="/app/customer/${encodeURIComponent(c.customer)}">
						${frappe.utils.escape_html(c.customer)}
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
			String(a.customer || "").localeCompare(String(b.customer || ""))
		);
		const body = panel.querySelector(".msp-documents__body");
		if (!entries.length) {
			body.innerHTML = `<div class="muted">${__("Keine neuen Dokumente — alles übersprungen oder fehlgeschlagen.")}</div>`;
			return;
		}
		body.innerHTML = `
			<table class="msp-table">
				<thead><tr>
					<th>${__("Kunde")}</th>
					<th>${__("Dokument")}</th>
					<th class="num">${__("Zeilen")}</th>
					<th class="num">${__("Summe (netto)")}</th>
				</tr></thead>
				<tbody>
					${entries.map((e) => `
						<tr>
							<td><a href="/app/customer/${encodeURIComponent(e.customer || "")}">${frappe.utils.escape_html(e.customer || "")}</a></td>
							<td><a href="/app/${slug(e.target_doc_type)}/${encodeURIComponent(e.target_doc_name)}">
								<span class="msp-doc-type">${frappe.utils.escape_html(e.target_doc_type)}</span>
								<span class="msp-doc-name">${frappe.utils.escape_html(e.target_doc_name)}</span>
							</a></td>
							<td class="num">${format_int(e.line_count || 0)}</td>
							<td class="num">${format_eur(e.total_amount)}</td>
						</tr>
					`).join("")}
				</tbody>
			</table>
		`;
	} catch (err) { console.error(err); }
}

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
		return "<svg viewBox='0 0 24 24' width='20' height='20' fill='none' stroke='currentColor' stroke-width='1.6'><rect x='4' y='3' width='16' height='18' rx='2'/><path d='M10 3v4h4V3'/><path d='M10 9v2h4v2h-4v2h4v2h-4'/></svg>";
	return "<svg viewBox='0 0 24 24' width='20' height='20' fill='none' stroke='currentColor' stroke-width='1.6'><path d='M6 3h9l4 4v14a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z'/><path d='M15 3v4h4'/><path d='M8 14h8M8 18h6'/></svg>";
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
// Styles
// ---------------------------------------------------------------------------

function inject_style(root) {
	const style = document.createElement("style");
	style.textContent = `
		.msp-wizard {
			--ink: #0f172a;
			--ink-soft: #475569;
			--mute: #94a3b8;
			--line: #e2e8f0;
			--surface: #ffffff;
			--surface-alt: #f8fafc;
			--primary: var(--primary, #2490ef);
			--primary-ink: #0b4a8a;
			--accent: #e73249;
			--ok: #047857;
			--warn: #b45309;
			--danger: #b91c1c;
			--muted-bg: #f1f5f9;

			max-width: 1080px;
			margin: 0 auto;
			padding: 4px 4px 40px;
			font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
				"Helvetica Neue", Arial, sans-serif;
			color: var(--ink);
		}

		.msp-empty {
			min-height: 360px;
			display: flex; flex-direction: column; align-items: center; justify-content: center;
			gap: 14px;
			text-align: center;
		}
		.msp-empty__icon { font-size: 32px; color: var(--mute); }
		.msp-empty__title { font-size: 20px; font-weight: 600; margin: 0; color: var(--ink); }
		.msp-empty__text { color: var(--ink-soft); font-size: 14px; margin: 0; }

		/* ---- Header + Stepper -------------------------------------- */
		.msp-wiz-head {
			display: grid;
			grid-template-columns: minmax(0, 1fr) auto;
			gap: 32px;
			align-items: center;
			padding: 24px 0 20px;
			border-bottom: 1px solid var(--line);
			margin-bottom: 24px;
		}
		@media (max-width: 720px) {
			.msp-wiz-head { grid-template-columns: 1fr; gap: 16px; }
		}
		.msp-wiz-file {
			display: flex; gap: 12px; align-items: center;
			min-width: 0;
		}
		.msp-wiz-file__icon {
			width: 44px; height: 44px; border-radius: 10px;
			background: var(--muted-bg);
			display: flex; align-items: center; justify-content: center;
			color: var(--ink-soft);
			flex: none;
		}
		.msp-wiz-file__meta { min-width: 0; }
		.msp-wiz-file__name {
			font-size: 15px; font-weight: 600; color: var(--ink);
			letter-spacing: -0.01em;
			white-space: nowrap; text-overflow: ellipsis; overflow: hidden;
		}
		.msp-wiz-file__handler {
			font-size: 12.5px; color: var(--ink-soft);
		}

		.msp-steps {
			list-style: none;
			display: flex; gap: 24px;
			margin: 0; padding: 0;
		}
		.msp-step {
			display: flex; gap: 10px; align-items: center;
			font-size: 13px; color: var(--mute);
			font-weight: 500;
			letter-spacing: 0.01em;
		}
		.msp-step span {
			display: inline-flex; align-items: center; justify-content: center;
			min-width: 26px; height: 26px;
			padding: 0 7px;
			border: 1px solid var(--line);
			border-radius: 6px;
			font-size: 11px;
			font-family: "SF Mono", Menlo, Consolas, monospace;
			color: var(--mute);
			font-weight: 600;
			background: var(--surface);
		}
		.msp-step.is-active { color: var(--ink); font-weight: 600; }
		.msp-step.is-active span { border-color: var(--primary); color: var(--primary); background: rgba(36, 144, 239, 0.06); }
		.msp-step.is-done span { background: var(--ok); border-color: var(--ok); color: #fff; }

		/* ---- Config Panel ----------------------------------------- */
		.msp-config { animation: msp-fade-in .3s ease both; }
		.msp-h3 {
			font-size: 12px;
			text-transform: uppercase;
			letter-spacing: .12em;
			color: var(--mute);
			font-weight: 600;
			margin: 0 0 10px 0;
		}

		.msp-hero-grid {
			display: grid;
			grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
			gap: 12px;
			margin-bottom: 28px;
		}
		.msp-hero-stat {
			position: relative;
			padding: 14px 14px 12px;
			background: var(--surface);
			border: 1px solid var(--line);
			border-radius: 10px;
			overflow: hidden;
		}
		.msp-hero-stat::before {
			content: "";
			position: absolute; left: 0; top: 0; bottom: 0;
			width: 3px; background: var(--line);
		}
		.msp-hero-stat--accent::before { background: var(--accent); }
		.msp-hero-stat__value {
			font-size: 26px; font-weight: 600; line-height: 1.1;
			font-variant-numeric: tabular-nums;
			letter-spacing: -0.02em;
		}
		.msp-hero-stat--accent .msp-hero-stat__value { color: var(--accent); }
		.msp-hero-stat__label {
			font-size: 11px;
			text-transform: uppercase;
			letter-spacing: .1em;
			color: var(--mute);
			font-weight: 600;
			margin-top: 4px;
		}

		.msp-context { margin: 28px 0; }

		.msp-config__grid {
			display: grid;
			grid-template-columns: 1fr 1fr;
			gap: 20px;
			max-width: 720px;
		}
		@media (max-width: 640px) { .msp-config__grid { grid-template-columns: 1fr; } }
		.msp-field label {
			display: block;
			font-size: 11px;
			text-transform: uppercase;
			letter-spacing: .1em;
			color: var(--mute);
			font-weight: 600;
			margin-bottom: 6px;
		}
		.msp-field--wide { grid-column: 1 / -1; }
		.msp-check { display: flex; align-items: center; gap: 8px; cursor: pointer; }
		.msp-check span { font-size: 13.5px; color: var(--ink); font-weight: 500; text-transform: none; letter-spacing: 0; }
		.msp-hint {
			font-size: 12px; color: var(--mute); margin-top: 6px;
			line-height: 1.45;
		}
		.msp-hint--warn { color: var(--warn); }

		.msp-config__foot {
			display: flex; justify-content: space-between; align-items: center;
			margin-top: 32px; padding-top: 20px;
			border-top: 1px solid var(--line);
		}
		.msp-back {
			font-size: 13px; color: var(--ink-soft); text-decoration: none;
		}
		.msp-back:hover { color: var(--primary); }
		.arr { margin-left: 4px; }

		/* ---- Running Panel ---------------------------------------- */
		.msp-running {
			min-height: 320px;
			display: flex; flex-direction: column; align-items: center; justify-content: center;
			gap: 14px; text-align: center;
			animation: msp-fade-in .3s ease both;
		}
		.msp-running__spin {
			width: 40px; height: 40px; border-radius: 50%;
			border: 3px solid var(--line); border-top-color: var(--primary);
			animation: msp-spin .9s linear infinite;
		}
		.msp-running__label { font-size: 18px; font-weight: 600; color: var(--ink); }
		.msp-running__hint { font-size: 13px; color: var(--ink-soft); }

		/* ---- Result Panel ----------------------------------------- */
		.msp-result { animation: msp-fade-in .3s ease both; }
		.msp-result__head {
			display: flex; justify-content: space-between; align-items: center;
			gap: 20px; flex-wrap: wrap;
			padding-bottom: 20px; border-bottom: 1px solid var(--line);
			margin-bottom: 24px;
		}
		.msp-result__status { display: flex; gap: 14px; align-items: center; }
		.msp-result__icon {
			width: 54px; height: 54px; border-radius: 50%;
			display: flex; align-items: center; justify-content: center;
			background: var(--muted-bg); color: var(--ink-soft);
			flex: none;
		}
		.msp-result--ok .msp-result__icon { background: #dcfce7; color: var(--ok); }
		.msp-result--warn .msp-result__icon { background: #fef3c7; color: var(--warn); }
		.msp-result--error .msp-result__icon { background: #fee2e2; color: var(--danger); }
		.msp-result__title { font-size: 18px; font-weight: 600; color: var(--ink); }
		.msp-result__sub { font-size: 13px; color: var(--ink-soft); margin-top: 2px; }
		.msp-result__sub a { font-family: "SF Mono", Menlo, Consolas, monospace; }
		.msp-result__cta { display: flex; gap: 8px; }
		.msp-result__msg {
			background: #fef2f2; color: var(--danger);
			padding: 10px 14px; border-radius: 6px; margin-bottom: 16px;
			font-size: 13px;
		}

		.msp-counters {
			display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;
			margin-bottom: 28px;
		}
		@media (max-width: 640px) { .msp-counters { grid-template-columns: repeat(2, 1fr); } }
		.msp-counter {
			background: var(--surface);
			border: 1px solid var(--line);
			border-radius: 10px;
			padding: 18px 16px 16px;
			position: relative;
			overflow: hidden;
		}
		.msp-counter::before {
			content: ""; position: absolute; left: 0; top: 0; bottom: 0;
			width: 3px; background: var(--line);
		}
		.msp-counter--primary::before { background: var(--primary); }
		.msp-counter--bad::before { background: var(--danger); }
		.msp-counter__value {
			font-size: 34px; font-weight: 600; line-height: 1;
			font-variant-numeric: tabular-nums;
			letter-spacing: -0.02em;
		}
		.msp-counter--bad .msp-counter__value { color: var(--danger); }
		.msp-counter__label {
			font-size: 11px; text-transform: uppercase; letter-spacing: .1em;
			color: var(--mute); font-weight: 600; margin-top: 6px;
		}

		/* ---- Summary / Top customers ------------------------------ */
		.msp-summary { margin: 28px 0 32px; }
		.msp-top-row {
			display: grid;
			grid-template-columns: 28px minmax(150px, 1fr) minmax(120px, 2fr) auto auto;
			gap: 12px;
			align-items: center;
			padding: 10px 0;
			border-bottom: 1px solid var(--line);
			font-size: 13.5px;
		}
		.msp-top-row:last-child { border-bottom: 0; }
		.msp-top-row__rank {
			font-family: "SF Mono", Menlo, Consolas, monospace;
			color: var(--mute);
			font-size: 12px;
			font-weight: 600;
		}
		.msp-top-row__customer { color: var(--ink); text-decoration: none; font-weight: 500; }
		.msp-top-row__customer:hover { color: var(--primary); }
		.msp-top-row__bar {
			height: 6px; background: var(--muted-bg); border-radius: 999px;
			overflow: hidden;
		}
		.msp-top-row__bar-fill {
			height: 100%; background: var(--primary);
			border-radius: 999px;
			transition: width .4s ease;
		}
		.msp-top-row__sub { color: var(--mute); font-size: 12px; white-space: nowrap; }
		.msp-top-row__amount {
			font-weight: 600; font-variant-numeric: tabular-nums;
			min-width: 100px; text-align: right;
		}
		.msp-top-foot {
			display: flex; gap: 18px; justify-content: flex-end;
			padding-top: 12px; font-size: 12.5px; color: var(--ink-soft);
		}
		.msp-top-foot strong { color: var(--ink); font-weight: 600; font-variant-numeric: tabular-nums; }

		/* ---- Documents table -------------------------------------- */
		.msp-documents { margin-top: 16px; }
		.msp-table { width: 100%; border-collapse: collapse; font-size: 13px; }
		.msp-table th {
			text-align: left;
			font-size: 11px; text-transform: uppercase; letter-spacing: .1em;
			color: var(--mute); font-weight: 600;
			padding: 10px 8px;
			border-bottom: 1px solid var(--line);
		}
		.msp-table td {
			padding: 10px 8px;
			border-bottom: 1px solid var(--line);
			color: var(--ink);
		}
		.msp-table tr:hover td { background: var(--surface-alt); }
		.msp-table td.num, .msp-table th.num { text-align: right; font-variant-numeric: tabular-nums; }
		.msp-table a { color: var(--ink); text-decoration: none; }
		.msp-table a:hover { color: var(--primary); }
		.msp-doc-type {
			display: inline-block;
			padding: 1px 7px;
			background: var(--muted-bg);
			color: var(--ink-soft);
			border-radius: 4px;
			font-size: 11px;
			font-weight: 500;
			margin-right: 6px;
		}
		.msp-doc-name {
			font-family: "SF Mono", Menlo, Consolas, monospace;
			font-size: 12.5px;
			color: var(--ink-soft);
		}

		.muted { color: var(--mute); }
		.num { text-align: right; }

		.spinner {
			display: inline-block;
			width: 10px; height: 10px; border-radius: 50%;
			border: 1.5px solid var(--line);
			border-top-color: var(--primary);
			animation: msp-spin .8s linear infinite;
		}
		.spinner--lg { width: 32px; height: 32px; border-width: 3px; }

		@keyframes msp-fade-in {
			from { opacity: 0; transform: translateY(4px); }
			to { opacity: 1; transform: translateY(0); }
		}
		@keyframes msp-spin {
			from { transform: rotate(0); }
			to { transform: rotate(360deg); }
		}
	`;
	root.appendChild(style);
}
