/**
 * Frappe-Page „Lieferanten-Import" — Drag-&-Drop-Dropzone mit Dashboard.
 *
 * Layout-Konzept: Editorial Data. Große Zahlen als visueller Anker,
 * klare Typografie-Hierarchie, Grautöne für Struktur, ERPNext-Blau als
 * Primär, itsdave-Rot als sparsam eingesetzter Akzent.
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
					<div class="msp-dropzone__orb" aria-hidden="true"></div>
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
		if (e.target.classList.contains("msp-dropzone__browse") ||
			e.target.closest(".msp-dropzone__inner") === e.currentTarget.querySelector(".msp-dropzone__inner")) {
			if (e.target.tagName !== "BUTTON" && !e.target.classList.contains("msp-dropzone__browse")) {
				// Klick auf die Zone selbst → File-Dialog
				els.fileInput.click();
			}
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
			{ label: __("Läufe (30 Tage)"), value: t.runs || 0,
			  sub: build_status_strip(t), accent: "primary" },
			{ label: __("Erzeugte Belege"), value: t.documents || 0,
			  sub: fmt_line(t.lines, __("Zeilen verarbeitet")), accent: "neutral" },
			{ label: __("Fehler"), value: t.errors || 0,
			  sub: t.errors ? __("bitte prüfen") : __("keine auffälligen"),
			  accent: t.errors ? "danger" : "neutral" },
			{ label: __("Aktive Subscriptions"), value: s.active || 0,
			  sub: `${s.total_qty || 0} ${__("Slots insgesamt")}`,
			  accent: "accent" },
		];
		els.stats.innerHTML = stats.map(render_stat).join("");

		const recent = data.recent_runs || [];
		els.recent.innerHTML = recent.length
			? recent.map(render_recent_row).join("")
			: `<div class="msp-recent__empty">${__("Noch keine Läufe vorhanden.")}</div>`;
	}

	function render_stat(s) {
		return `
			<div class="msp-stat msp-stat--${s.accent}">
				<div class="msp-stat__value">${format_int(s.value)}</div>
				<div class="msp-stat__label">${s.label}</div>
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
		if (name.endsWith(".zip")) return "<svg viewBox='0 0 24 24' width='20' height='20' fill='none' stroke='currentColor' stroke-width='1.6'><rect x='4' y='3' width='16' height='18' rx='2'/><path d='M10 3v4h4V3'/><path d='M10 9v2h4v2h-4v2h4v2h-4'/></svg>";
		if (name.endsWith(".csv")) return "<svg viewBox='0 0 24 24' width='20' height='20' fill='none' stroke='currentColor' stroke-width='1.6'><path d='M6 3h9l4 4v14a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z'/><path d='M15 3v4h4'/><path d='M8 14h2M12 14h2M16 14h1'/><path d='M8 18h2M12 18h2M16 18h1'/></svg>";
		return "<svg viewBox='0 0 24 24' width='20' height='20' fill='none' stroke='currentColor' stroke-width='1.6'><path d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z'/><path d='M14 2v6h6'/></svg>";
	}
};


// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

function inject_style(root) {
	const style = document.createElement("style");
	style.textContent = `
		.msp-importer {
			--ink: #0f172a;
			--ink-soft: #475569;
			--mute: #94a3b8;
			--line: #e2e8f0;
			--surface: #ffffff;
			--surface-alt: #f8fafc;
			--primary: var(--primary, #2490ef);
			--primary-ink: #0b4a8a;
			--accent: #e73249;        /* itsdave rot */
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

		.msp-hero {
			display: grid;
			grid-template-columns: minmax(0, 1.1fr) minmax(0, 1.4fr);
			gap: 40px;
			align-items: end;
			padding: 36px 0 28px;
			border-bottom: 1px solid var(--line);
			margin-bottom: 28px;
		}
		@media (max-width: 880px) { .msp-hero { grid-template-columns: 1fr; gap: 24px; } }

		.msp-eyebrow {
			font-size: 11px;
			text-transform: uppercase;
			letter-spacing: .14em;
			color: var(--mute);
			margin: 0 0 10px 0;
			font-weight: 600;
		}
		.msp-title {
			font-size: 34px;
			font-weight: 600;
			line-height: 1.15;
			letter-spacing: -0.015em;
			margin: 0 0 12px 0;
			color: var(--ink);
		}
		.msp-sub {
			font-size: 14.5px;
			line-height: 1.55;
			color: var(--ink-soft);
			max-width: 46ch;
			margin: 0;
		}

		.msp-stats {
			display: grid;
			grid-template-columns: repeat(4, 1fr);
			gap: 12px;
		}
		@media (max-width: 640px) { .msp-stats { grid-template-columns: repeat(2, 1fr); } }

		.msp-stat {
			background: var(--surface);
			border: 1px solid var(--line);
			border-radius: 10px;
			padding: 14px 14px 12px;
			display: flex;
			flex-direction: column;
			gap: 6px;
			position: relative;
			overflow: hidden;
			animation: msp-fade-in .4s ease both;
		}
		.msp-stat::before {
			content: "";
			position: absolute;
			left: 0; top: 0; bottom: 0;
			width: 3px;
		}
		.msp-stat--primary::before { background: var(--primary); }
		.msp-stat--accent::before { background: var(--accent); }
		.msp-stat--neutral::before { background: var(--line); }
		.msp-stat--danger::before { background: var(--danger); }
		.msp-stat--skeleton {
			background: linear-gradient(90deg, var(--muted-bg) 0%, #e8eef5 50%, var(--muted-bg) 100%);
			background-size: 200% 100%;
			animation: msp-shimmer 1.2s linear infinite;
			min-height: 92px;
		}
		.msp-stat__value {
			font-size: 30px;
			font-weight: 600;
			line-height: 1;
			font-variant-numeric: tabular-nums;
			letter-spacing: -0.02em;
			color: var(--ink);
		}
		.msp-stat__label {
			font-size: 11px;
			text-transform: uppercase;
			letter-spacing: .1em;
			color: var(--mute);
			font-weight: 600;
		}
		.msp-stat__sub { font-size: 12px; color: var(--ink-soft); margin-top: 2px; }

		.pill {
			display: inline-block;
			padding: 2px 7px;
			border-radius: 999px;
			font-size: 11px;
			font-weight: 600;
			line-height: 1.5;
			margin-right: 4px;
		}
		.pill--ok { background: #dcfce7; color: #14532d; }
		.pill--warn { background: #fef3c7; color: #92400e; }
		.pill--danger { background: #fee2e2; color: #991b1b; }
		.pill--muted { background: var(--muted-bg); color: var(--mute); }

		.msp-dropzone {
			position: relative;
			background: var(--surface);
			border: 1.5px dashed #cbd5e1;
			border-radius: 14px;
			padding: 36px 28px;
			text-align: center;
			cursor: pointer;
			transition: background-color .18s, border-color .18s, transform .18s;
			overflow: hidden;
			animation: msp-fade-in .5s ease .1s both;
		}
		.msp-dropzone::before {
			content: "";
			position: absolute; inset: 0;
			background: radial-gradient(circle at 50% -10%, rgba(36, 144, 239, 0.06), transparent 55%);
			pointer-events: none;
		}
		.msp-dropzone.is-dragover {
			border-color: var(--primary);
			background: rgba(36, 144, 239, 0.04);
			transform: translateY(-1px);
		}
		.msp-dropzone__inner {
			display: flex; flex-direction: column; align-items: center; gap: 10px;
			position: relative; z-index: 1;
		}
		.msp-dropzone__orb {
			width: 46px; height: 46px; border-radius: 50%;
			background: linear-gradient(145deg, var(--primary) 0%, var(--primary-ink) 100%);
			position: relative;
			box-shadow: 0 4px 14px rgba(36, 144, 239, 0.25);
		}
		.msp-dropzone__orb::after {
			content: "";
			position: absolute;
			left: 50%; top: 50%;
			transform: translate(-50%, -50%);
			width: 14px; height: 14px;
			border-top: 2.5px solid #fff; border-left: 2.5px solid #fff;
			border-radius: 2px;
			transform-origin: center;
			transform: translate(-50%, -44%) rotate(45deg);
		}
		.msp-dropzone__copy { display: flex; flex-direction: column; gap: 4px; }
		.msp-dropzone__label {
			font-size: 18px; font-weight: 600; color: var(--ink);
			letter-spacing: -0.01em;
		}
		.msp-dropzone__hint { font-size: 13px; color: var(--ink-soft); }
		.msp-dropzone__browse {
			margin-top: 6px;
			font-weight: 500;
		}

		.msp-cards {
			display: flex; flex-direction: column; gap: 10px;
			margin-top: 18px;
		}

		.msp-card {
			position: relative;
			display: grid;
			grid-template-columns: 40px 1fr;
			gap: 14px;
			padding: 16px 18px;
			background: var(--surface);
			border: 1px solid var(--line);
			border-radius: 10px;
			animation: msp-fade-in .3s ease both;
		}
		.msp-card__badge {
			width: 40px; height: 40px;
			display: flex; align-items: center; justify-content: center;
			background: var(--muted-bg);
			border-radius: 8px;
			color: var(--ink-soft);
			flex: none;
		}
		.msp-card__head {
			display: flex; gap: 8px; align-items: baseline;
			margin-bottom: 6px;
		}
		.msp-card__name { font-size: 15px; font-weight: 600; margin: 0; color: var(--ink); letter-spacing: -0.01em; }
		.msp-card__size { font-size: 12px; color: var(--mute); }
		.msp-card__state { font-size: 13px; color: var(--ink-soft); display: flex; align-items: center; gap: 6px; }
		.msp-card__state .spinner {
			width: 10px; height: 10px; border-radius: 50%;
			border: 1.5px solid var(--line);
			border-top-color: var(--primary);
			animation: msp-spin .8s linear infinite;
			display: inline-block;
		}
		.msp-card__state em { font-style: normal; color: var(--mute); }
		.msp-card__state strong { font-weight: 600; color: var(--ink); }
		.msp-card__state .check {
			color: #fff;
			background: var(--ok);
			width: 16px; height: 16px;
			border-radius: 50%;
			display: inline-flex; align-items: center; justify-content: center;
			font-size: 10px;
		}
		.msp-card__state .cross {
			color: var(--danger);
			width: 16px; height: 16px;
			border-radius: 50%;
			display: inline-flex; align-items: center; justify-content: center;
			background: #fee2e2;
			font-size: 11px;
			font-weight: 700;
		}
		.msp-card__state .cross--warn { color: var(--warn); background: #fef3c7; }

		.msp-card--matched { border-left: 3px solid var(--ok); padding-left: 16px; }
		.msp-card--unmatched { border-left: 3px solid var(--warn); padding-left: 16px; }
		.msp-card--error { border-left: 3px solid var(--danger); padding-left: 16px; }

		.msp-card__stats {
			display: flex; flex-wrap: wrap; gap: 6px;
			margin-top: 10px;
		}
		.msp-chip {
			display: inline-flex; gap: 6px; align-items: baseline;
			padding: 4px 10px;
			background: var(--muted-bg);
			border-radius: 7px;
			font-size: 12.5px;
		}
		.msp-chip__label { color: var(--mute); text-transform: lowercase; }
		.msp-chip__value { color: var(--ink); font-weight: 600; font-variant-numeric: tabular-nums; }
		.msp-chip--warn { background: #fef3c7; }
		.msp-chip--warn .msp-chip__label,
		.msp-chip--warn .msp-chip__value { color: #92400e; }

		.msp-card__warn {
			font-size: 12.5px;
			color: var(--warn);
			background: #fffbeb;
			padding: 8px 10px;
			border-radius: 6px;
			margin-top: 10px;
		}
		.msp-card__error {
			font-size: 12.5px;
			color: var(--danger);
			background: #fef2f2;
			padding: 8px 10px;
			border-radius: 6px;
			margin-top: 10px;
			white-space: pre-wrap;
		}
		.msp-card__actions {
			display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
			margin-top: 12px;
		}
		.msp-card__actions .msp-input {
			width: auto; min-width: 260px;
		}
		.btn-open-assistant .arr { margin-left: 4px; }

		.msp-recent { margin-top: 32px; }
		.msp-section-head {
			display: flex; align-items: baseline; justify-content: space-between;
			margin-bottom: 12px;
		}
		.msp-section-title {
			font-size: 14px;
			text-transform: uppercase;
			letter-spacing: .1em;
			color: var(--mute);
			font-weight: 600;
			margin: 0;
		}
		.msp-section-link {
			font-size: 13px;
			color: var(--ink-soft);
			text-decoration: none;
		}
		.msp-section-link:hover { color: var(--primary); }

		.msp-recent__list {
			display: flex; flex-direction: column;
			border: 1px solid var(--line);
			border-radius: 10px;
			overflow: hidden;
			background: var(--surface);
		}
		.msp-recent__row {
			display: grid;
			grid-template-columns: 130px 1fr 1.3fr 1.6fr auto;
			gap: 18px;
			padding: 12px 16px;
			border-bottom: 1px solid var(--line);
			text-decoration: none;
			color: var(--ink);
			font-size: 13px;
			transition: background-color .12s;
		}
		.msp-recent__row:last-child { border-bottom: 0; }
		.msp-recent__row:hover { background: var(--surface-alt); }
		.msp-recent__status { display: inline-flex; align-items: center; gap: 6px; font-weight: 500; }
		.msp-recent__name { color: var(--ink-soft); font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 12.5px; }
		.msp-recent__profile { color: var(--ink-soft); }
		.msp-recent__nums { color: var(--ink-soft); font-variant-numeric: tabular-nums; }
		.msp-recent__nums strong { color: var(--ink); font-weight: 600; }
		.msp-recent__nums .danger { color: var(--danger); }
		.msp-recent__time { color: var(--mute); font-size: 12px; justify-self: end; }
		.msp-recent__empty {
			padding: 26px; text-align: center;
			color: var(--mute); font-size: 13px;
		}

		.dot {
			display: inline-block;
			width: 7px; height: 7px;
			border-radius: 50%;
		}
		.dot--ok { background: var(--ok); }
		.dot--warn { background: var(--warn); }
		.dot--danger { background: var(--danger); }
		.dot--accent { background: var(--primary); }
		.dot--muted { background: var(--mute); }

		.muted { color: var(--mute); }

		@keyframes msp-fade-in {
			from { opacity: 0; transform: translateY(4px); }
			to { opacity: 1; transform: translateY(0); }
		}
		@keyframes msp-shimmer {
			from { background-position: 0 0; }
			to { background-position: -200% 0; }
		}
		@keyframes msp-spin {
			from { transform: rotate(0); }
			to { transform: rotate(360deg); }
		}
	`;
	root.appendChild(style);
}
