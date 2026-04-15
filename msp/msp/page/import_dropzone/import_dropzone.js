/**
 * Frappe-Page „Lieferanten-Import" — Drag-&-Drop-Dropzone mit Dashboard.
 *
 * Nutzt durchgehend Frappé-CSS-Variablen (--text-color, --card-bg, --primary,
 * --red-500, --green-500 …), damit Dark Mode und Theme-Switch out-of-the-box
 * funktionieren. Horizontale Seitenpaddings per var(--padding-lg).
 */

frappe.pages["import-dropzone"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Lieferanten-Import"),
		single_column: true,
	});
	const root = page.main[0] || page.main;

	root.innerHTML = `
		<div class="msp-importer">
			<header class="msp-hero">
				<div class="msp-hero__lede">
					<p class="msp-eyebrow">${__("Lieferanten-Import")}</p>
					<h1 class="msp-title">${__("Dateien analysieren & Belege erzeugen")}</h1>
					<p class="msp-sub">${__("CSV oder ZIP hier einwerfen — das System erkennt das Format, zeigt eine Vorschau und führt dich durch den Import.")}</p>
				</div>
				<div class="msp-stats" data-role="stats">
					<div class="msp-stat msp-stat--skeleton"></div>
					<div class="msp-stat msp-stat--skeleton"></div>
					<div class="msp-stat msp-stat--skeleton"></div>
					<div class="msp-stat msp-stat--skeleton"></div>
				</div>
			</header>

			<section class="msp-dropzone" tabindex="0">
				<div class="msp-dropzone__inner">
					<div class="msp-dropzone__orb" aria-hidden="true">
						${ICON.upload}
					</div>
					<div class="msp-dropzone__copy">
						<div class="msp-dropzone__label">
							${__("Dateien ablegen")}
						</div>
						<div class="msp-dropzone__hint">
							${__("CSV · ZIP (mit einer CSV) — mehrere Dateien gleichzeitig möglich")}
						</div>
					</div>
					<button class="btn btn-primary btn-sm msp-dropzone__browse" type="button">
						${__("Datei auswählen")}
					</button>
					<input type="file" class="msp-dropzone__input" multiple hidden
						accept=".csv,.zip,application/zip,application/x-zip-compressed,text/csv" />
				</div>
			</section>

			<div class="msp-cards" data-role="cards"></div>

			<section class="msp-recent" data-role="recent">
				<div class="msp-section-head">
					<h2 class="msp-section-title">${__("Letzte Läufe")}</h2>
					<a class="msp-section-link" href="/app/supplier-import-run">
						${__("Alle anzeigen")} →
					</a>
				</div>
				<div class="msp-recent__list">
					<div class="msp-recent__empty">${__("Noch keine Läufe vorhanden.")}</div>
				</div>
			</section>
		</div>
	`;

	inject_style(root);

	const els = {
		dz: root.querySelector(".msp-dropzone"),
		cards: root.querySelector('[data-role="cards"]'),
		stats: root.querySelector('[data-role="stats"]'),
		recent: root.querySelector('[data-role="recent"] .msp-recent__list'),
		fileInput: root.querySelector(".msp-dropzone__input"),
	};

	// --- Dashboard-Daten nachladen ------------------------------------
	let HANDLERS = [];
	frappe.call({
		method: "msp.importers.assistant.list_handlers",
		callback: (r) => (HANDLERS = r.message || []),
	});
	frappe.call({
		method: "msp.importers.assistant.dashboard_stats",
		args: { months: 1, recent_count: 6 },
		callback: (r) => render_dashboard(r.message || {}),
	});

	// --- Drag & Drop --------------------------------------------------
	["dragenter", "dragover"].forEach((ev) =>
		els.dz.addEventListener(ev, (e) => {
			e.preventDefault();
			e.stopPropagation();
			els.dz.classList.add("is-dragover");
		})
	);
	["dragleave", "drop"].forEach((ev) =>
		els.dz.addEventListener(ev, (e) => {
			e.preventDefault();
			e.stopPropagation();
			els.dz.classList.remove("is-dragover");
		})
	);
	els.dz.addEventListener("drop", (e) => handle_files(e.dataTransfer.files));
	els.dz.addEventListener("click", (e) => {
		if (e.target.tagName !== "BUTTON" && !e.target.classList.contains("msp-dropzone__browse")) {
			els.fileInput.click();
		}
	});
	root.querySelector(".msp-dropzone__browse").addEventListener("click", (e) => {
		e.stopPropagation();
		els.fileInput.click();
	});
	els.fileInput.addEventListener("change", (e) => handle_files(e.target.files));

	function handle_files(file_list) {
		if (!file_list || !file_list.length) return;
		for (const file of file_list) process_one_file(file);
	}

	// --- Dashboard --------------------------------------------------------

	function render_dashboard(data) {
		const t = data.totals || {};
		const s = data.subscriptions || {};
		const stats = [
			{
				label: __("Läufe (30 Tage)"),
				value: t.runs || 0,
				sub: build_status_strip(t),
				tone: "primary",
				icon: ICON.stack,
			},
			{
				label: __("Erzeugte Belege"),
				value: t.documents || 0,
				sub: fmt_line(t.lines, __("Zeilen verarbeitet")),
				tone: "success",
				icon: ICON.doc,
			},
			{
				label: __("Fehler"),
				value: t.errors || 0,
				sub: t.errors ? __("bitte prüfen") : __("keine auffälligen"),
				tone: t.errors ? "danger" : "neutral",
				icon: t.errors ? ICON.warning : ICON.check,
			},
			{
				label: __("Aktive Subscriptions"),
				value: s.active || 0,
				sub: `${format_int(s.total_qty || 0)} ${__("Slots insgesamt")}`,
				tone: "accent",
				icon: ICON.users,
			},
		];
		els.stats.innerHTML = stats.map(render_stat).join("");

		const recent = data.recent_runs || [];
		els.recent.innerHTML = recent.length
			? recent.map(render_recent_row).join("")
			: `<div class="msp-recent__empty">${__("Noch keine Läufe vorhanden.")}</div>`;
	}

	function render_stat(s) {
		return `
			<div class="msp-stat msp-stat--${s.tone}">
				<div class="msp-stat__head">
					<span class="msp-stat__icon">${s.icon || ""}</span>
					<span class="msp-stat__label">${s.label}</span>
				</div>
				<div class="msp-stat__value">${format_int(s.value)}</div>
				<div class="msp-stat__sub">${s.sub || ""}</div>
			</div>
		`;
	}

	function build_status_strip(t) {
		const parts = [];
		if (t.succeeded) parts.push(`<span class="pill pill--ok">${t.succeeded} ${__("erfolgreich")}</span>`);
		if (t.partial) parts.push(`<span class="pill pill--warn">${t.partial} ${__("partiell")}</span>`);
		if (t.failed) parts.push(`<span class="pill pill--danger">${t.failed} ${__("fehlgeschlagen")}</span>`);
		return parts.join(" ") || `<span class="pill pill--muted">${__("—")}</span>`;
	}

	function fmt_line(n, suffix) {
		if (!n) return `<span class="muted">${__("—")}</span>`;
		return `${format_int(n)} ${suffix}`;
	}

	function render_recent_row(r) {
		const status_cls = {
			"Succeeded": "ok", "Partial": "warn", "Failed": "danger",
			"Running": "accent", "Pending": "muted",
		}[r.status] || "muted";
		const dt = r.creation ? format_relative(r.creation) : "";
		return `
			<a class="msp-recent__row" href="/app/supplier-import-run/${encodeURIComponent(r.name)}">
				<span class="msp-recent__status"><span class="dot dot--${status_cls}"></span>${frappe.utils.escape_html(r.status || "")}</span>
				<span class="msp-recent__name">${frappe.utils.escape_html(r.name)}</span>
				<span class="msp-recent__profile">${frappe.utils.escape_html(r.profile || "")}</span>
				<span class="msp-recent__nums">
					<strong>${format_int(r.document_count || 0)}</strong> ${__("Docs")} ·
					<strong>${format_int(r.line_count || 0)}</strong> ${__("Zeilen")}${r.error_count ? ` · <span class="danger">${r.error_count} ${__("Fehler")}</span>` : ""}
				</span>
				<span class="msp-recent__time">${dt}</span>
			</a>
		`;
	}

	// --- Upload-Handling ----------------------------------------------

	async function process_one_file(file) {
		const card = make_card(file);
		els.cards.prepend(card.el);
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
		const el = document.createElement("article");
		el.className = "msp-card msp-card--uploading";
		el.innerHTML = `
			<div class="msp-card__badge">${icon_for(file.name)}</div>
			<div class="msp-card__body">
				<header class="msp-card__head">
					<h3 class="msp-card__name"></h3>
					<span class="msp-card__size"></span>
				</header>
				<div class="msp-card__state"><span class="spinner"></span> <em>${__("Warte …")}</em></div>
				<div class="msp-card__stats" hidden></div>
				<div class="msp-card__warn" hidden></div>
				<div class="msp-card__error" hidden></div>
				<div class="msp-card__actions" hidden></div>
			</div>
		`;
		el.querySelector(".msp-card__name").textContent = file.name;
		el.querySelector(".msp-card__size").textContent = format_size(file.size);

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
				if (label) state_el.innerHTML = `<span class="spinner"></span> <em>${label}</em>`;
				else state_el.innerHTML = "";
			},
			set_progress(pct) {
				el.querySelector(".msp-card__state").innerHTML =
					`<span class="spinner"></span> <em>${__("Lade hoch …")} ${Math.round(pct)}%</em>`;
			},
			set_error(msg) {
				el.classList.add("msp-card--error");
				el.querySelector(".msp-card__state").innerHTML = `<span class="cross">✕</span> ${__("Fehler")}`;
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
		const actions_el = el.querySelector(".msp-card__actions");

		if (result.error) {
			card.set_error(result.error);
			return;
		}

		if (!result.handler_key) {
			el.classList.remove("msp-card--analyzing");
			el.classList.add("msp-card--unmatched");
			state_el.innerHTML = `<span class="cross cross--warn">!</span> <strong>${__("Format nicht erkannt")}</strong>`;
			warn_el.hidden = false;
			warn_el.textContent = __("Keiner der verfügbaren Handler hat die Datei zuverlässig erkannt. Bitte manuell zuordnen:");
			actions_el.hidden = false;
			actions_el.innerHTML = `
				<select class="form-control form-control-sm msp-input">
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
			select.addEventListener("change", () => (btn.disabled = !select.value));
			btn.addEventListener("click", () =>
				open_assistant(file_url, select.value, {}, { display_name: null, preview: null })
			);
			return;
		}

		el.classList.remove("msp-card--analyzing");
		el.classList.add("msp-card--matched");
		state_el.innerHTML = `
			<span class="check">✓</span>
			<strong>${frappe.utils.escape_html(result.display_name)}</strong>
			<span class="muted">· ${Math.round(result.confidence * 100)}% ${__("Confidence")}</span>
		`;

		const preview = result.preview || {};
		const stats = [];
		if (preview.line_count != null) stats.push(["Zeilen", preview.line_count]);
		if (preview.customer_count != null) stats.push(["Kunden", preview.customer_count]);
		if (preview.product_count != null) stats.push(["Produkte", preview.product_count]);
		if (preview.period_label) stats.push(["Zeitraum", preview.period_label, true]);
		if (preview.credit_note_lines) stats.push(["Gutschriftzeilen", preview.credit_note_lines, false, "warn"]);

		stats_el.hidden = false;
		stats_el.innerHTML = stats.map(([label, val, isText, pill]) => `
			<div class="msp-chip ${pill ? `msp-chip--${pill}` : ""}">
				<span class="msp-chip__label">${__(label)}</span>
				<span class="msp-chip__value">${isText ? frappe.utils.escape_html(String(val)) : format_int(val)}</span>
			</div>
		`).join("");

		const warnings = [...(preview.warnings || [])];
		if (preview.format_drift) warnings.unshift(__("Format weicht vom erwarteten Layout ab"));
		if (warnings.length) {
			warn_el.hidden = false;
			warn_el.innerHTML = warnings.map((w) => `<div>⚠ ${frappe.utils.escape_html(w)}</div>`).join("");
		}

		actions_el.hidden = false;
		actions_el.innerHTML = `
			<button class="btn btn-primary btn-sm btn-open-assistant">
				${__("Assistent öffnen")} <span class="arr">→</span>
			</button>
		`;
		actions_el.querySelector(".btn-open-assistant").addEventListener("click", () =>
			open_assistant(file_url, result.handler_key, {
				wizard_route: result.wizard_route,
				format_drift: preview.format_drift,
				suggested_profile: preview.suggested_profile,
				display_name: result.display_name,
			}, result)
		);
	}

	function open_assistant(file_url, handler_key, opts = {}, analysis = {}) {
		frappe.route_options = {
			file_url,
			handler_key,
			display_name: analysis.display_name || opts.display_name || "",
			suggested_profile: opts.suggested_profile || "",
			format_drift: !!opts.format_drift,
			preview: analysis.preview || null,
		};
		frappe.set_route(opts.wizard_route || "import-assistant");
	}

	// --- HTTP / Utils ---------------------------------------------------

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
					} catch (e) { reject(e); }
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

	function format_int(n) {
		return Number(n || 0).toLocaleString("de-DE");
	}

	function format_relative(datetime_str) {
		const then = new Date(datetime_str.replace(" ", "T"));
		const diff = (Date.now() - then.getTime()) / 1000;
		if (diff < 60) return __("gerade eben");
		if (diff < 3600) return `${Math.round(diff / 60)} ${__("Min.")}`;
		if (diff < 86400) return `${Math.round(diff / 3600)} ${__("h")}`;
		if (diff < 86400 * 7) return `${Math.round(diff / 86400)} ${__("Tage")}`;
		return then.toLocaleDateString("de-DE");
	}

	function icon_for(filename) {
		const name = (filename || "").toLowerCase();
		if (name.endsWith(".zip")) return ICON.zip;
		if (name.endsWith(".csv")) return ICON.csv;
		return ICON.file;
	}
};


// ---------------------------------------------------------------------------
// Icon-Set — schlanke 1.6er-Stroke-SVGs, erben currentColor
// ---------------------------------------------------------------------------

const ICON = {
	upload: `<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16V4"/><path d="M6 10l6-6 6 6"/><path d="M4 20h16"/></svg>`,
	stack: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l9 5-9 5-9-5 9-5z"/><path d="M3 13l9 5 9-5"/><path d="M3 17l9 5 9-5"/></svg>`,
	doc: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h8M8 17h6"/></svg>`,
	warning: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>`,
	check: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></svg>`,
	users: `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9.5" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.9"/><path d="M16 3.1a4 4 0 0 1 0 7.8"/></svg>`,
	zip: `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="3" width="16" height="18" rx="2"/><path d="M10 3v4h4V3"/><path d="M10 9v2h4v2h-4v2h4v2h-4"/></svg>`,
	csv: `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h9l4 4v14a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M15 3v4h4"/><path d="M8 14h2M12 14h2M16 14h1"/><path d="M8 18h2M12 18h2M16 18h1"/></svg>`,
	file: `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>`,
};


// ---------------------------------------------------------------------------
// Styles — nutzen Frappé-Design-Tokens (--text-color, --card-bg, --primary,
// --red-500/--green-500/--yellow-500/--blue-500, --padding-*)
// ---------------------------------------------------------------------------

function inject_style(root) {
	const style = document.createElement("style");
	style.textContent = `
		.msp-importer {
			--msp-accent: #e73249;       /* itsdave-Rot — sparsam als Signal */
			--msp-aurora-1: #2490ef;     /* ERP-Blau, deutlich gesättigter als --primary */
			--msp-aurora-2: #7856ff;     /* Violett-Tinte */
			--msp-radius: 10px;
			--msp-shadow-card: 0 1px 2px rgba(15, 23, 42, 0.04);

			max-width: 1120px;
			margin: 0 auto;
			padding: var(--padding-sm) var(--padding-lg) var(--padding-2xl);
			color: var(--text-color);
			font-family: inherit;
		}
		@media (max-width: 640px) {
			.msp-importer { padding: var(--padding-xs) var(--padding-md) var(--padding-xl); }
		}

		/* ---------- Hero + Stats ---------- */
		.msp-hero {
			display: grid;
			grid-template-columns: minmax(0, 1.1fr) minmax(0, 1.4fr);
			gap: var(--padding-2xl);
			align-items: end;
			padding: var(--padding-xl) 0 var(--padding-lg);
			border-bottom: 1px solid var(--border-color);
			margin-bottom: var(--padding-xl);
		}
		@media (max-width: 900px) {
			.msp-hero { grid-template-columns: 1fr; gap: var(--padding-lg); align-items: start; }
		}

		.msp-eyebrow {
			font-size: 11px;
			text-transform: uppercase;
			letter-spacing: .14em;
			color: var(--text-muted);
			margin: 0 0 10px 0;
			font-weight: 600;
		}
		.msp-title {
			font-size: 28px;
			font-weight: 700;
			line-height: 1.2;
			letter-spacing: -0.015em;
			margin: 0 0 10px 0;
			color: var(--heading-color);
		}
		.msp-sub {
			font-size: 14px;
			line-height: 1.55;
			color: var(--text-muted);
			max-width: 48ch;
			margin: 0;
		}

		.msp-stats {
			display: grid;
			grid-template-columns: repeat(4, 1fr);
			gap: var(--padding-sm);
		}
		@media (max-width: 720px) { .msp-stats { grid-template-columns: repeat(2, 1fr); } }

		.msp-stat {
			position: relative;
			background: var(--card-bg);
			border: 1px solid var(--border-color);
			border-radius: var(--msp-radius);
			padding: var(--padding-md);
			display: flex;
			flex-direction: column;
			gap: 4px;
			overflow: hidden;
			box-shadow: var(--msp-shadow-card);
			animation: msp-fade-in .4s ease both;
		}
		.msp-stat::before {
			content: ""; position: absolute;
			left: 0; top: 0; bottom: 0; width: 3px;
			background: var(--border-color);
		}
		.msp-stat--primary::before { background: var(--primary); }
		.msp-stat--success::before { background: var(--green-500); }
		.msp-stat--danger::before  { background: var(--red-500); }
		.msp-stat--accent::before  { background: var(--msp-accent); }
		.msp-stat--neutral::before { background: var(--border-color); }

		.msp-stat__head {
			display: flex; align-items: center; gap: 8px;
			color: var(--text-muted);
		}
		.msp-stat__icon {
			display: inline-flex; align-items: center; justify-content: center;
			width: 24px; height: 24px; border-radius: 6px;
			background: var(--subtle-fg);
			color: var(--text-muted);
			flex: none;
		}
		.msp-stat--primary .msp-stat__icon { background: var(--alert-bg-info); color: var(--alert-text-info); }
		.msp-stat--success .msp-stat__icon { background: var(--alert-bg-success); color: var(--alert-text-success); }
		.msp-stat--danger  .msp-stat__icon { background: var(--alert-bg-danger); color: var(--alert-text-danger); }
		.msp-stat--accent  .msp-stat__icon { background: var(--alert-bg-info); color: var(--alert-text-info); }

		.msp-stat__label {
			font-size: 11px;
			text-transform: uppercase;
			letter-spacing: .08em;
			color: var(--text-muted);
			font-weight: 600;
		}
		.msp-stat__value {
			font-size: 28px; font-weight: 700; line-height: 1;
			color: var(--heading-color);
			font-variant-numeric: tabular-nums;
			letter-spacing: -0.02em;
			margin-top: 4px;
		}
		.msp-stat--danger .msp-stat__value { color: var(--red-600, var(--red-500)); }
		.msp-stat__sub { font-size: 12px; color: var(--text-muted); margin-top: 2px; min-height: 18px; }

		.msp-stat--skeleton {
			background: linear-gradient(90deg, var(--subtle-fg) 0%, var(--fg-hover-color) 50%, var(--subtle-fg) 100%);
			background-size: 200% 100%;
			animation: msp-shimmer 1.2s linear infinite;
			min-height: 104px;
		}
		.msp-stat--skeleton::before { display: none; }

		/* ---------- Pills ---------- */
		.pill {
			display: inline-block;
			padding: 2px 8px;
			border-radius: 999px;
			font-size: 11px;
			font-weight: 600;
			line-height: 1.5;
			margin-right: 4px;
		}
		.pill--ok     { background: var(--alert-bg-success); color: var(--alert-text-success); }
		.pill--warn   { background: var(--alert-bg-warning); color: var(--alert-text-warning); }
		.pill--danger { background: var(--alert-bg-danger); color: var(--alert-text-danger); }
		.pill--muted  { background: var(--subtle-fg); color: var(--text-muted); }

		/* ---------- Dropzone ---------- */
		.msp-dropzone {
			position: relative;
			background: var(--card-bg);
			border: 1.5px dashed var(--dark-border-color, var(--border-color));
			border-radius: var(--msp-radius);
			padding: calc(var(--padding-2xl) + 8px) var(--padding-lg);
			text-align: center;
			cursor: pointer;
			transition: background-color .18s, border-color .18s, transform .18s;
			overflow: hidden;
			isolation: isolate;
			animation: msp-fade-in .5s ease .1s both;
		}
		/* Aurora-Glow: drei radiale Gradients erzeugen ein blau-violettes
		   Leuchten mit einem warmen Hauch — durch ::before-Drift animiert */
		.msp-dropzone::before {
			content: "";
			position: absolute; inset: -50% -15% auto -15%; height: 220%;
			background:
				radial-gradient(55% 50% at 50% 20%, rgba(36, 144, 239, 0.42), transparent 70%),
				radial-gradient(38% 35% at 18% 80%, rgba(120, 86, 255, 0.30), transparent 72%),
				radial-gradient(34% 32% at 84% 72%, rgba(231, 50, 73, 0.20), transparent 75%),
				radial-gradient(28% 28% at 70% 14%, rgba(56, 189, 248, 0.28), transparent 75%);
			pointer-events: none;
			z-index: 0;
			animation: msp-aurora 18s ease-in-out infinite alternate;
			filter: blur(2px);
		}
		/* Sub-Layer: feines Grain + Boden-Schatten für Tiefe */
		.msp-dropzone::after {
			content: "";
			position: absolute; inset: 0;
			background: radial-gradient(circle at 50% 115%, rgba(15, 23, 42, 0.05), transparent 60%);
			pointer-events: none;
			z-index: 0;
		}
		.msp-dropzone.is-dragover {
			border-color: var(--msp-aurora-1);
			border-style: solid;
			transform: translateY(-2px);
			box-shadow: 0 14px 40px rgba(36, 144, 239, 0.22);
		}
		.msp-dropzone.is-dragover::before {
			animation-duration: 6s;
			filter: saturate(1.4) brightness(1.1) blur(1px);
		}
		.msp-dropzone__inner {
			display: flex; flex-direction: column; align-items: center; gap: 12px;
			position: relative; z-index: 1;
		}
		.msp-dropzone__orb {
			width: 60px; height: 60px; border-radius: 50%;
			display: inline-flex; align-items: center; justify-content: center;
			background:
				radial-gradient(circle at 30% 22%, rgba(255,255,255,0.55), transparent 55%),
				linear-gradient(145deg, var(--msp-aurora-1) 0%, #1565b0 60%, #0d3f7a 100%);
			color: #fff;
			box-shadow:
				0 0 0 8px rgba(36, 144, 239, 0.10),
				0 12px 30px rgba(36, 144, 239, 0.42),
				inset 0 -2px 6px rgba(0, 0, 0, 0.18);
			animation: msp-orb-pulse 3.6s ease-in-out infinite;
		}
		.msp-dropzone__copy { display: flex; flex-direction: column; gap: 4px; }
		.msp-dropzone__label {
			font-size: 18px; font-weight: 600; color: var(--heading-color);
			letter-spacing: -0.01em;
		}
		.msp-dropzone__hint { font-size: 13px; color: var(--text-muted); }
		.msp-dropzone__browse { margin-top: 8px; font-weight: 500; }

		/* ---------- Upload-Cards ---------- */
		.msp-cards {
			display: flex; flex-direction: column; gap: var(--padding-sm);
			margin-top: var(--padding-md);
		}
		.msp-card {
			position: relative;
			display: grid;
			grid-template-columns: 44px 1fr;
			gap: 14px;
			padding: var(--padding-md);
			background: var(--card-bg);
			border: 1px solid var(--border-color);
			border-radius: var(--msp-radius);
			box-shadow: var(--msp-shadow-card);
			animation: msp-fade-in .3s ease both;
		}
		.msp-card__badge {
			width: 44px; height: 44px;
			display: flex; align-items: center; justify-content: center;
			background: var(--subtle-fg);
			color: var(--text-muted);
			border-radius: 8px;
			flex: none;
		}
		.msp-card__head {
			display: flex; gap: 8px; align-items: baseline;
			margin-bottom: 6px;
		}
		.msp-card__name { font-size: 15px; font-weight: 600; margin: 0; color: var(--heading-color); letter-spacing: -0.01em; }
		.msp-card__size { font-size: 12px; color: var(--text-muted); }
		.msp-card__state { font-size: 13px; color: var(--text-muted); display: flex; align-items: center; gap: 6px; }
		.msp-card__state .spinner {
			width: 10px; height: 10px; border-radius: 50%;
			border: 1.5px solid var(--border-color);
			border-top-color: var(--primary);
			animation: msp-spin .8s linear infinite;
			display: inline-block;
		}
		.msp-card__state em { font-style: normal; color: var(--text-muted); }
		.msp-card__state strong { font-weight: 600; color: var(--text-color); }
		.msp-card__state .check {
			color: #fff;
			background: var(--green-500);
			width: 16px; height: 16px;
			border-radius: 50%;
			display: inline-flex; align-items: center; justify-content: center;
			font-size: 10px;
		}
		.msp-card__state .cross {
			color: var(--red-600, var(--red-500));
			width: 16px; height: 16px;
			border-radius: 50%;
			display: inline-flex; align-items: center; justify-content: center;
			background: var(--alert-bg-danger);
			font-size: 11px;
			font-weight: 700;
		}
		.msp-card__state .cross--warn {
			color: var(--alert-text-warning);
			background: var(--alert-bg-warning);
		}

		.msp-card--matched   { border-left: 3px solid var(--green-500); padding-left: 14px; }
		.msp-card--unmatched { border-left: 3px solid var(--yellow-500); padding-left: 14px; }
		.msp-card--error     { border-left: 3px solid var(--red-500); padding-left: 14px; }

		.msp-card__stats {
			display: flex; flex-wrap: wrap; gap: 6px;
			margin-top: 10px;
		}
		.msp-chip {
			display: inline-flex; gap: 6px; align-items: baseline;
			padding: 4px 10px;
			background: var(--subtle-fg);
			border-radius: 7px;
			font-size: 12.5px;
		}
		.msp-chip__label { color: var(--text-muted); text-transform: lowercase; }
		.msp-chip__value { color: var(--text-color); font-weight: 600; font-variant-numeric: tabular-nums; }
		.msp-chip--warn { background: var(--alert-bg-warning); }
		.msp-chip--warn .msp-chip__label,
		.msp-chip--warn .msp-chip__value { color: var(--alert-text-warning); }

		.msp-card__warn {
			font-size: 12.5px;
			color: var(--alert-text-warning);
			background: var(--alert-bg-warning);
			padding: 8px 10px;
			border-radius: 6px;
			margin-top: 10px;
		}
		.msp-card__error {
			font-size: 12.5px;
			color: var(--alert-text-danger);
			background: var(--alert-bg-danger);
			padding: 8px 10px;
			border-radius: 6px;
			margin-top: 10px;
			white-space: pre-wrap;
		}
		.msp-card__actions {
			display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
			margin-top: 12px;
		}
		.msp-card__actions .msp-input { width: auto; min-width: 260px; }
		.btn-open-assistant .arr { margin-left: 4px; }

		/* ---------- Recent runs ---------- */
		.msp-recent { margin-top: var(--padding-xl); }
		.msp-section-head {
			display: flex; align-items: baseline; justify-content: space-between;
			margin-bottom: var(--padding-sm);
		}
		.msp-section-title {
			font-size: 12px;
			text-transform: uppercase;
			letter-spacing: .1em;
			color: var(--text-muted);
			font-weight: 600;
			margin: 0;
		}
		.msp-section-link {
			font-size: 13px;
			color: var(--text-muted);
			text-decoration: none;
		}
		.msp-section-link:hover { color: var(--primary); }

		.msp-recent__list {
			display: flex; flex-direction: column;
			border: 1px solid var(--border-color);
			border-radius: var(--msp-radius);
			overflow: hidden;
			background: var(--card-bg);
			box-shadow: var(--msp-shadow-card);
		}
		.msp-recent__row {
			display: grid;
			grid-template-columns: 130px 1fr 1.2fr 1.5fr auto;
			gap: 18px;
			padding: 12px var(--padding-md);
			border-bottom: 1px solid var(--border-color);
			text-decoration: none;
			color: var(--text-color);
			font-size: 13px;
			transition: background-color .12s;
		}
		.msp-recent__row:last-child { border-bottom: 0; }
		.msp-recent__row:hover { background: var(--highlight-color); }
		.msp-recent__status { display: inline-flex; align-items: center; gap: 6px; font-weight: 500; }
		.msp-recent__name { color: var(--text-muted); font-family: var(--font-stack-monospace, "SF Mono", Menlo, Consolas, monospace); font-size: 12.5px; }
		.msp-recent__profile { color: var(--text-muted); }
		.msp-recent__nums { color: var(--text-muted); font-variant-numeric: tabular-nums; }
		.msp-recent__nums strong { color: var(--text-color); font-weight: 600; }
		.msp-recent__nums .danger { color: var(--red-500); }
		.msp-recent__time { color: var(--text-muted); font-size: 12px; justify-self: end; }
		.msp-recent__empty {
			padding: var(--padding-xl); text-align: center;
			color: var(--text-muted); font-size: 13px;
		}
		@media (max-width: 900px) {
			.msp-recent__row { grid-template-columns: auto 1fr; grid-auto-flow: row; gap: 6px 12px; }
			.msp-recent__profile, .msp-recent__time { grid-column: 2; }
		}

		.dot {
			display: inline-block;
			width: 7px; height: 7px;
			border-radius: 50%;
		}
		.dot--ok     { background: var(--green-500); }
		.dot--warn   { background: var(--yellow-500); }
		.dot--danger { background: var(--red-500); }
		.dot--accent { background: var(--primary); }
		.dot--muted  { background: var(--text-muted); }

		.muted  { color: var(--text-muted); }
		.danger { color: var(--red-500); }

		@keyframes msp-fade-in {
			from { opacity: 0; transform: translateY(4px); }
			to   { opacity: 1; transform: translateY(0); }
		}
		@keyframes msp-shimmer {
			from { background-position: 0 0; }
			to   { background-position: -200% 0; }
		}
		@keyframes msp-spin {
			from { transform: rotate(0); }
			to   { transform: rotate(360deg); }
		}
		@keyframes msp-aurora {
			0%   { transform: translate3d(0, 0, 0) scale(1); }
			50%  { transform: translate3d(2%, -1%, 0) scale(1.05); }
			100% { transform: translate3d(-2%, 1%, 0) scale(1.02); }
		}
		@keyframes msp-orb-pulse {
			0%, 100% { box-shadow: 0 0 0 6px rgba(36, 144, 239, 0.10), 0 10px 28px rgba(36, 144, 239, 0.32); }
			50%      { box-shadow: 0 0 0 10px rgba(36, 144, 239, 0.06), 0 14px 36px rgba(36, 144, 239, 0.40); }
		}
	`;
	root.appendChild(style);
}
