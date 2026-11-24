/**
 * Sierra Snow dashboard: data loading, section renderers, stacked forecast
 * chart and Leaflet road map. The hero scene, verdict, 7-day strip,
 * shortcuts and other interactive extras live in experience.js and hook in
 * through the "snow:render" and "snow:tier" events.
 */

let snowData = null;

/* ---------------- Preferences & units (saved per browser) ---------------- */
const Prefs = (() => {
  const KEY = "sierraSnowPrefs.v1";
  const defaults = { temp: "F", snow: "in", favResort: "palisades_tahoe", alerts: true, alertThreshold: 12, model: "nbm" };
  let v = { ...defaults };
  try { v = { ...defaults, ...JSON.parse(localStorage.getItem(KEY) || "{}") }; } catch (e) {}
  return {
    get: k => v[k],
    set(k, val) {
      v[k] = val;
      try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) {}
      document.dispatchEvent(new CustomEvent("snow:prefs", { detail: { key: k, value: val } }));
    }
  };
})();

const U = {
  metricSnow: () => Prefs.get("snow") === "cm",
  celsius: () => Prefs.get("temp") === "C",
  snowNum: inches => (inches == null ? null : (Prefs.get("snow") === "cm" ? inches * 2.54 : inches)),
  /** "12 in" / "30 cm". Values >= 10 are rounded to whole numbers. */
  snow(inches, digits) {
    if (inches == null || isNaN(inches)) return "--";
    const v = U.snowNum(inches);
    const d = digits ?? (Math.abs(v) >= 10 ? 0 : 1);
    return `${v.toFixed(d)} ${U.metricSnow() ? "cm" : "in"}`;
  },
  snowBare(inches, digits) {
    if (inches == null || isNaN(inches)) return "--";
    const v = U.snowNum(inches);
    return v.toFixed(digits ?? (Math.abs(v) >= 10 ? 0 : 1));
  },
  snowSuffix: () => (Prefs.get("snow") === "cm" ? " cm" : " in"),
  snowAxisUnit: () => (Prefs.get("snow") === "cm" ? "cm" : "in"),
  liquid: inches => (inches == null ? "--" : U.metricSnow() ? `${(inches * 25.4).toFixed(1)} mm` : `${inches.toFixed(2)} in`),
  tempNum: f => (f == null ? null : U.celsius() ? (f - 32) * 5 / 9 : f),
  temp: (f, digits = 0) => (f == null ? "n/a" : `${U.tempNum(f).toFixed(digits)}°${U.celsius() ? "C" : "F"}`),
  tempShort: f => (f == null ? "--" : `${Math.round(U.tempNum(f))}°`),
};

let currentResortId = Prefs.get("favResort") || "palisades_tahoe";
let roadMap = null;
let roadLayers = {};
let liftObserverSetup = false;

document.addEventListener("DOMContentLoaded", () => {
  initDashboard();
});

async function loadSnowData() {
  for (const url of ["/api/snow", "./data/live_snow_data.json"]) {
    try {
      const res = await fetch(url, { cache: "no-store" });
      if (res.ok) return await res.json();
    } catch (e) { /* try next */ }
  }
  return window.__INITIAL_SNOW_DATA__ || null;
}

/* Server refresh status: shows progress while the server fetches new data,
   and reloads the page data when a newer dataset is written. */
const Live = {
  hasServer: false,
  timer: null,
  wasRunning: false,
  async poll() {
    let st = null;
    try {
      const r = await fetch("/api/status", { cache: "no-store" });
      if (r.ok) { st = await r.json(); this.hasServer = true; }
    } catch (e) { /* static file mode */ }
    if (!st) { this.showBar(null); return; }
    this.showBar(st);
    const current = snowData && snowData.metadata ? snowData.metadata.generated_at_utc : null;
    if (st.data_generated_at_utc && st.data_generated_at_utc !== current && !st.running) {
      const fresh = await loadSnowData();
      if (fresh) {
        const first = !snowData;
        snowData = fresh;
        for (const k in ModelCache) delete ModelCache[k];
        renderDashboard();
        if (first) initRoadMap(); else updateRoadMapData();
      }
    }
    this.wasRunning = st.running;
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this.poll(), st.running ? 1500 : 30000);
  },
  showBar(st) {
    const bar = document.getElementById("refresh-bar"), btn = document.getElementById("btn-refresh");
    if (!bar) return;
    const running = !!(st && st.running);
    bar.hidden = !running;
    if (btn) btn.classList.toggle("spinning", running);
    if (!running) return;
    const steps = st.steps || [];
    const done = steps.filter(x => x.state !== "running").length;
    const cur = steps.filter(x => x.state === "running").map(x => x.name).slice(-1)[0];
    document.getElementById("refresh-text").textContent = `Fetching latest data${st.kind === "roads" ? " (roads)" : ""}: ${cur || "starting"}`;
    document.getElementById("refresh-steps").innerHTML = steps.filter(x => x.state !== "running").slice(-6)
      .map(x => `<span class="rs ${x.state}">${x.state === "done" ? "✓" : "!"} ${x.name}</span>`).join("") + `<span class="rs count">${done} steps done</span>`;
  },
  async refresh() {
    try {
      const r = await fetch("/api/refresh", { method: "POST" });
      if (r.ok) { this.wasRunning = true; clearTimeout(this.timer); this.poll(); return; }
    } catch (e) { /* no server */ }
    const fresh = await loadSnowData();
    if (fresh) { snowData = fresh; renderDashboard(); updateRoadMapData(); }
  },
};

async function initDashboard() {
  document.querySelectorAll(".tab-btn").forEach(t => t.classList.toggle("active", t.dataset.resort === currentResortId));
  document.addEventListener("snow:prefs", e => { if (["temp", "snow"].includes(e.detail.key)) renderDashboard(); });
  setupTabs();
  setupTierToggle();
  const btn = document.getElementById("btn-refresh");
  if (btn) btn.addEventListener("click", () => Live.refresh());

  snowData = await loadSnowData();
  if (snowData) {
    renderDashboard();
    initRoadMap();
  }
  Live.poll();
}

function activeResort() {
  if (!snowData || !snowData.resorts) return null;
  return snowData.resorts[currentResortId] || Object.values(snowData.resorts)[0];
}

function setResort(id) {
  if (!snowData || !snowData.resorts[id] || id === currentResortId) return;
  currentResortId = id;
  document.querySelectorAll(".tab-btn").forEach(t => t.classList.toggle("active", t.dataset.resort === id));
  renderDashboard();
}

function setupTabs() {
  document.querySelectorAll(".tab-btn").forEach(tab => {
    tab.addEventListener("click", () => setResort(tab.dataset.resort));
  });
}

/* ---------------- Observations for the T=0 frame ----------------
   Resort weather stations (base, mid, summit) from the resort feed. Used only at
   hour 0 and only when the reading is recent; every later hour uses the forecast. */
const Obs = {
  forTier(resort, tier, maxAgeMin = 90) {
    const st = ((((resort || {}).sources || {}).resort_official || {}).weather_stations || {})[tier];
    if (!st || st.temp_f == null || !st.observed_at) return null;
    const t = new Date(String(st.observed_at).replace(/([+-]\d{2})(\d{2})$/, "$1:$2"));
    const age = (Date.now() - t) / 60000;
    if (!(age >= -15 && age <= maxAgeMin)) return null;
    return { ...st, observed: t, age_min: Math.max(0, Math.round(age)) };
  },
  wetBulbF(tf, tdf, elevFt) {
    if (tf == null || tdf == null) return null;
    const p = 1013.25 * Math.pow(1 - 2.25577e-5 * elevFt * 0.3048, 5.25588);
    const t = (tf - 32) * 5 / 9, td = (tdf - 32) * 5 / 9;
    const es = x => 6.112 * Math.exp(17.67 * x / (x + 243.5));
    const e = es(td);
    let lo = td, hi = t;
    for (let i = 0; i < 40; i++) { const m = (lo + hi) / 2; (es(m) - 6.6e-4 * p * (t - m) > e) ? (hi = m) : (lo = m); }
    return ((lo + hi) / 2) * 9 / 5 + 32;
  },
};
window.Obs = Obs;

/* ---------------- Forecast model selection ----------------
   The main dataset carries the default model (NBM). Other models live in
   data/models/<resort>/<model>.json and are loaded when selected. */
const ModelCache = {};

async function ensureModel(resort) {
  if (!resort._omDefault) { resort._omDefault = resort.sources.open_meteo; resort._consDefault = resort.consensus_forecast; }
  const def = resort._omDefault;
  const defId = (def.model || {}).id || "nbm";
  const avail = (def.available_models || []).filter(m => m.status === "success").map(m => m.id);
  let want = Prefs.get("model") || defId;
  if (avail.length && !avail.includes(want)) want = defId;
  resort._modelError = null;
  if (want === defId) {
    resort.sources.open_meteo = def; resort.consensus_forecast = resort._consDefault; resort._modelId = defId;
    return;
  }
  const key = `${resort.id}|${want}|${snowData.metadata.generated_at_utc}`;
  if (!ModelCache[key]) {
    try {
      const r = await fetch(`data/models/${resort.id}/${want}.json`, { cache: "no-store" });
      if (r.ok) ModelCache[key] = await r.json();
    } catch (e) { /* static file mode */ }
  }
  const m = ModelCache[key];
  if (!m) {
    resort._modelError = "Other models need the server (python3 server.py); showing the default model.";
    resort.sources.open_meteo = def; resort.consensus_forecast = resort._consDefault; resort._modelId = defId;
    return;
  }
  m.available_models = def.available_models;
  m.scales = def.scales;
  resort.sources.open_meteo = m;
  resort.consensus_forecast = m.consensus_forecast || resort._consDefault;
  resort._modelId = want;
}

function renderModelBar(resort) {
  const box = document.getElementById("model-chips");
  if (!box) return;
  const def = resort._omDefault || resort.sources.open_meteo || {};
  const list = def.available_models || [];
  const cur = resort._modelId;
  const runOf = m => {
    const r = (m.runs || []).find(x => x.run_init_utc);
    return r ? `${r.run_init_utc.slice(5, 10).replace("-", "/")} ${r.run_init_utc.slice(11, 13)}Z` : "run n/a";
  };
  box.innerHTML = list.map(m => `<button class="model-chip${m.id === cur ? " active" : ""}" role="tab" data-model="${m.id}" ${m.status !== "success" ? "disabled" : ""}
      title="${m.provider} · ${m.grid} · sounding: ${m.sounding_label}${m.sounding_has_vertical_velocity ? "" : " (no vertical velocity)"} · ${m.hours_available ?? "?"} h">
      <b>${m.label}</b><small>${m.members ? `${m.members.length} models` : runOf(m)}${m.hours_available && m.hours_available < 160 ? ` · ${Math.round(m.hours_available / 24 * 10) / 10} d` : ""}</small></button>`).join("");
  box.querySelectorAll(".model-chip").forEach(b => b.addEventListener("click", () => { Prefs.set("model", b.dataset.model); renderDashboard(); }));
  const om = resort.sources.open_meteo || {};
  const note = document.getElementById("model-note");
  const gp = om.nbm_grid_points;
  const shared = gp && gp.mid && gp.summit && gp.mid.grid_lat === gp.summit.grid_lat && gp.mid.grid_lon === gp.summit.grid_lon;
  const adjNote = om.nbm_elevation_adjustment ? " · values moved from the 2.5 km cells to each tier's elevation" : (shared ? " · mid and summit share one 2.5 km grid point" : "");
  if (note) note.textContent = resort._modelError || `${(om.primary_model || {}).label || ""} · ${(om.model || {}).hours_available ?? "?"} h · fetched ${Fmt.ago(om.fetched_at_utc)}${adjNote}`;
}

let renderSeq = 0;
async function renderDashboard() {
  const resort = activeResort();
  if (!resort) return;
  const seq = ++renderSeq;
  await ensureModel(resort);
  if (seq !== renderSeq) return;   // a newer render started while loading
  renderModelBar(resort);
  renderHeader(snowData.metadata, resort);
  renderKPIs(resort);
  renderSynopticDiscussion(resort);
  renderSounding(resort);
  renderHourlyDualAxisChart(resort);
  renderHazards(resort);
  renderLiftsAndOperations(resort);
  renderRoadList();
  document.dispatchEvent(new CustomEvent("snow:render", { detail: { resort, data: snowData } }));
}

function sourceStatuses(resort) {
  const s = resort.sources || {};
  const roads = snowData.road_conditions || {};
  const sond = snowData.observed_soundings || {};
  const item = (name, src, when) => ({ name, status: (src || {}).status || "error", when: when ?? ((src || {}).fetched_at_utc || (src || {}).timestamp_utc), note: (src || {}).stale_reason || (src || {}).error_message || (src || {}).reason });
  return [
    item("Models (HRRR→GFS, comparisons, ensembles)", s.open_meteo),
    item("NWS (REV discussion/alerts, grid snowfall)", s.noaa_nws),
    item(`CDEC sensor ${(s.cdec_snotel || {}).station_id || ""}`, s.cdec_snotel),
    item("Radiosondes REV / OAK", { status: Object.values(sond).every(x => x.status === "success") ? "success" : "stale" }, (sond.KREV || {}).fetched_at_utc),
    { name: "Caltrans chain controls", status: roads.is_live_feed && roads.status !== "stale" ? "success" : (roads.status || "error"), when: roads.fetched_at_utc, note: roads.stale_reason },
    item("Resort snow report", s.resort_official),
  ];
}

function renderHeader(meta, resort) {
  const timeEl = document.getElementById("last-updated-text");
  if (timeEl && meta && meta.generated_at_utc) {
    timeEl.textContent = `Data ${new Date(meta.generated_at_utc).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })} · ${Fmt.ago(meta.generated_at_utc)}`;
  }
  const srcs = sourceStatuses(resort);
  const cls = st => (st === "success" ? "live" : st === "stale" ? "cached" : "err");
  const dots = document.getElementById("source-dots");
  if (dots) dots.innerHTML = srcs.map(s => `<i class="${cls(s.status)}" title="${s.name}: ${s.status}"></i>`).join("");
  const pop = document.getElementById("source-pop");
  if (pop) {
    pop.innerHTML = `<div class="mini-label" style="padding:2px 6px 6px">Fetched by the server${Live.hasServer ? "" : " (static file: not refreshed)"}</div>` + srcs.map(s => `
      <div class="src" title="${(s.note || "").replace(/"/g, "&quot;")}"><i style="background:${s.status === "success" ? "var(--good)" : s.status === "stale" ? "var(--warn)" : "var(--bad)"}"></i>
      <span>${s.name}</span><span>${s.status === "success" ? Fmt.ago(s.when) : s.status === "unavailable" ? "unavailable" : `${s.status} · ${Fmt.ago(s.when)}`}</span></div>`).join("");
  }
}

function renderKPIs(resort) {
  const c = resort.consensus_forecast || {};
  const sources = resort.sources || {};
  const resortRpt = sources.resort_official || {};
  const om = sources.open_meteo || {};

  const setRange = (key, obj) => {
    const val = document.getElementById(`kpi-${key}-val`);
    const sub = document.getElementById(`kpi-${key}-sub`);
    const bar = document.getElementById(`kpi-${key}-bar`);
    if (!obj || !val) return;
    val.dataset.target = U.snowNum(obj.expected);
    val.textContent = U.snowBare(obj.expected, 0);
    const unitEl = val.nextElementSibling; if (unitEl) unitEl.textContent = U.snowSuffix();
    if (sub) sub.textContent = obj.min != null ? `${U.snowBare(obj.min, 0)}–${U.snow(obj.max, 0)} (p10–p90)` : "range unavailable";
    if (bar && obj.min != null) {
      const scale = Math.max(obj.max * 1.15, 1);
      bar.style.left = `${(obj.min / scale) * 100}%`;
      bar.style.width = `${((obj.max - obj.min) / scale) * 100}%`;
    }
  };
  setRange("24h", c.next_24h_inches);
  setRange("48h", c.next_48h_inches);

  const val7d = document.getElementById("kpi-7d-val");
  const summit7d = (om.summit && om.summit.snow_7d_total_inches) ?? c.next_7d_total_inches ?? 0;
  if (val7d) {
    val7d.dataset.target = U.snowNum(summit7d); val7d.textContent = U.snowBare(summit7d, 0);
    const unitEl = val7d.nextElementSibling; if (unitEl) unitEl.textContent = U.snowSuffix();
  }
  const sub7 = document.getElementById("kpi-ops-sub");
  const e7 = om.summit && om.summit.ensemble && om.summit.ensemble.snow_7d;
  if (sub7) sub7.textContent = e7 ? `${U.snowBare(e7.p10, 0)}–${U.snow(e7.p90, 0)} (p10–p90)` : "range unavailable";
  const bar7 = document.getElementById("kpi-7d-bar");
  if (bar7 && e7) { const sc = Math.max(e7.p90 * 1.15, 1); bar7.style.left = `${(e7.p10 / sc) * 100}%`; bar7.style.width = `${((e7.p90 - e7.p10) / sc) * 100}%`; }
  const srcNote = document.getElementById("range-source");
  const nMem = (c.range_source && (c.range_source.match(/\((\d+) members/) || [])[1]) || null;
  if (srcNote) srcNote.textContent = nMem ? `Shapes: ${nMem} ensemble members (GEFS, ECMWF ENS, ICON-EPS), each converted to snow with the ${(om.model || {}).label || "selected model"}'s hourly snow fraction and snow/liquid ratio. Tick: ${(om.model || {}).label || "model"} value. Axis is fixed across models and elevations.` : "Ensemble unavailable.";
  // Tier comparison: selected model and NWS, both at the tier elevation
  const tc = document.getElementById("tier-compare");
  const ng = c.nws_gridded || {};
  const nt = ng.tiers || {};
  const elv = resort.elevations || {};
  const sn = v => (v == null ? "–" : `${U.snowBare(v)} ${U.snowAxisUnit()}`);
  const thruIso = (nt.summit || {}).through_utc || (ng.summit_cell || {}).through_utc;
  const thruTxt = thruIso ? new Date(thruIso).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "America/Los_Angeles" }) : "end";
  const label = (om.model || {}).label || "Model";
  if (tc) {
    const row = t => {
      const m = om[t] || {}, w = nt[t] || {};
      const v = k => (w[k] || {}).value;
      return `<tr><td><b>${{ base: "Base", mid: "Mid", summit: "Summit" }[t]}</b><small>${(elv[`${t}_ft`] || 0).toLocaleString()} ft</small></td>
        <td>${sn(m.snow_24h_inches)}</td><td>${sn(m.snow_48h_inches)}</td><td>${sn(m.snow_7d_total_inches)}</td>
        <td>${sn(v("24h"))}</td><td>${sn(v("48h"))}</td><td>${sn(v("total"))}</td></tr>`;
    };
    tc.innerHTML = `<thead><tr><th></th><th colspan="3" class="grp">${label}</th><th colspan="3" class="grp">NWS gridded</th></tr>
      <tr><th></th><th>24 h</th><th>48 h</th><th>7 d</th><th>24 h</th><th>48 h</th><th>to ${thruTxt}</th></tr></thead>
      <tbody>${row("summit")}${row("mid")}${row("base")}</tbody>`;
  }
  const nwsEl = document.getElementById("nws-line");
  if (nwsEl) {
    const adj = om.nbm_elevation_adjustment;
    const parts = [];
    if (adj) {
      const rng = ["base", "mid", "summit"].filter(t => adj[t]).map(t => adj[t].neighbor_elevation_ft);
      const lo = Math.min(...rng.map(r => r[0])), hi = Math.max(...rng.map(r => r[1]));
      const ex = ["summit", "mid", "base"].filter(t => adj[t] && adj[t].extrapolation_ft > 50).map(t => {
        const a = adj[t], up = a.target_elevation_ft > a.neighbor_elevation_ft[1];
        return `the ${t} (${a.target_elevation_ft.toLocaleString()} ft) is ${a.extrapolation_ft.toLocaleString()} ft ${up ? "above the highest" : "below the lowest"} of those cells (${(up ? a.neighbor_elevation_ft[1] : a.neighbor_elevation_ft[0]).toLocaleString()} ft), so its values extend the line ${a.extrapolation_ft.toLocaleString()} ft past the data`;
      });
      parts.push(`NBM values at each tier come from a line fit every hour through the ~25 surrounding 2.5 km cells (terrain ${lo.toLocaleString()}–${hi.toLocaleString()} ft), evaluated at the tier's own height${ex.length ? `. Note: ${ex.join("; ")}` : ""}.`);
    }
    if (nt.summit && nt.summit.total) parts.push(`NWS values: the same regression on the NWS forecast's own neighboring cells (${nt.summit.total.cells} cells; NWS cell at the summit point ${(nt.summit.total.cell_elevation_ft || 0).toLocaleString()} ft, ${sn(nt.summit.total.cell_value)} unadjusted). NWS is shown beside the model and is not blended into it.`);
    else {
      const cellTxt = cl => cl && cl.office ? `${cl.office} cell ${cl.elevation_ft ? cl.elevation_ft.toLocaleString() + " ft" : ""}: 24 h ${sn(cl["24h"])}, 48 h ${sn(cl["48h"])}, ${sn(cl.total)} to ${thruTxt}` : null;
      const cl = [cellTxt(ng.summit_cell), cellTxt(ng.base_cell)].filter(Boolean);
      if (cl.length) parts.push(`NWS gridded forecast at its grid cells (not elevation-adjusted, not blended): ${cl.join(" · ")}`);
    }
    nwsEl.textContent = parts.join(" ");
  }
  renderDistribution(resort);
  const pdef = document.getElementById("powder-def");
  if (pdef && c.powder_score_definition) pdef.title = c.powder_score_definition;

  const valPowder = document.getElementById("kpi-powder-val");
  if (valPowder) valPowder.textContent = c.powder_score ? c.powder_score.toFixed(1) : "--";
  const ring = document.getElementById("powder-ring");
  if (ring) ring.style.strokeDashoffset = `${314.16 * (1 - Math.min(10, c.powder_score || 0) / 10)}`;


  const resortOk = ["success", "stale"].includes(resortRpt.status);
  const areas = resortRpt.snow_areas || {};
  const valOps = document.getElementById("kpi-ops-val");
  if (valOps) {
    const bd = (areas.base || {}).base_depth_in, md = (areas.mid || {}).base_depth_in;
    valOps.textContent = resortOk && bd != null ? `${U.snowBare(bd, 0)}${md != null ? "–" + U.snowBare(md, 0) : ""}` : "--";
    if (valOps.nextElementSibling) valOps.nextElementSibling.textContent = U.snowSuffix();
    const lbl = document.getElementById("resort-depth-label");
    if (lbl) lbl.textContent = resortOk ? `resort depth, base ${(areas.base || {}).elevation_ft?.toLocaleString() || ""}–mid ${(areas.mid || {}).elevation_ft?.toLocaleString() || ""} ft` : "resort report unavailable";
  }
  const cdec = sources.cdec_snotel || {};
  const sensor = cdec.measurements ? cdec.measurements.snow_depth_current_inches : null;
  const sensorEl = document.getElementById("snowpack-sensor");
  if (sensorEl) {
    sensorEl.textContent = typeof sensor === "number" ? U.snowBare(sensor, 0) : "--";
    if (sensorEl.nextElementSibling) sensorEl.nextElementSibling.textContent = U.snowSuffix();
  }
  const sensorLbl = document.getElementById("snowpack-sensor-label");
  if (sensorLbl) sensorLbl.textContent = `CDEC ${cdec.station_id || ""} sensor, ${(cdec.elevation_ft || 0).toLocaleString()} ft`;
  const kv = document.getElementById("resort-kv");
  if (kv) {
    const row = (k, v) => (v == null || v === "" ? "" : `<dt>${k}</dt><dd>${v}</dd>`);
    const area = t => areas[t] || {};
    const newSnow = t => { const a = area(t); return a.new_24h_in == null && a.new_7d_in == null ? null : `${U.snow(a.new_24h_in ?? 0)} / ${U.snow(a.new_72h_in ?? 0)} / ${U.snow(a.new_7d_in ?? 0)}`; };
    kv.innerHTML = resortOk ? [
      row(`New snow 24 h / 72 h / 7 d, mid ${area("mid").elevation_ft ? area("mid").elevation_ft.toLocaleString() + " ft" : ""}`, newSnow("mid")),
      row(`Same, base ${area("base").elevation_ft ? area("base").elevation_ft.toLocaleString() + " ft" : ""}`, newSnow("base")),
      row("Storm total / season total", resortRpt.storm_total_in != null ? `${U.snow(resortRpt.storm_total_in)} / ${U.snow(resortRpt.season_total_in)}` : null),
      row("Lifts open or scheduled", resortRpt.lifts_total ? `${resortRpt.lifts_open} of ${resortRpt.lifts_total}` : null),
      row("Trails open", resortRpt.trails_total ? `${resortRpt.trails_open} of ${resortRpt.trails_total}` : null),
      row("Surface", resortRpt.surface_condition),
    ].join("") : "";
  }
  const eb = document.getElementById("resort-eyebrow");
  if (eb) eb.textContent = resortOk ? `Resort snow report · updated ${resortRpt.report_updated ? new Date(resortRpt.report_updated).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "n/a"}` : "Resort snow report";
  const note = document.getElementById("ops-note");
  if (note) note.textContent = resortOk ? `Source: ${resortRpt.source}${resortRpt.status === "stale" ? ` (stale: ${resortRpt.stale_reason})` : ""} · fetched ${Fmt.ago(resortRpt.fetched_at_utc)}. Resort totals are measured on cleared new-snow boards.`
    : `Resort report unavailable${resortRpt.error_message ? `: ${resortRpt.error_message}` : ""}.`;
  const txtWrap = document.getElementById("resort-text-wrap"), txt = document.getElementById("resort-text");
  if (txtWrap && txt) { txtWrap.hidden = !resortRpt.report_text; txt.textContent = resortRpt.report_text || ""; }
}

const NWS_OFFICES = { REV: "Reno", STO: "Sacramento" };

/* Ensemble distribution: one row per window (24 h, 48 h, 7 d); summit density above
   the axis, base density mirrored below; tick = selected model's value. */
function renderDistribution(resort) {
  const box = document.getElementById("dist-chart");
  if (!box) return;
  window.__distResort = resort;
  const c = resort.consensus_forecast || {};
  const om = resort.sources.open_meteo || {};
  const sc = (om.scales || {}).distribution_in;
  const periods = [["24h", "h24", "24 h"], ["48h", "h48", "48 h"], ["7d", "d7", "7 days"]];
  // base on the left of each center line, summit on the right
  const sides = [["base", "#fbbf24", "Base", -1], ["summit", "#7dd3fc", "Summit", 1]];
  const unit = U.snowAxisUnit();
  const fmt = v => `${U.snowBare(v ?? 0)} ${unit}`;
  const allMax = sc ? Math.max(1, sc) : Math.max(1, ...periods.flatMap(([k, m]) => sides.flatMap(([t]) => [((c[t] || {})[k] || {}).value || 0, ...((((c[t] || {}).members || {})[m]) || [])])));
  const dt = document.getElementById("dist-title");
  const nMembers = ((c.summit || {}).members || {}).d7 ? c.summit.members.d7.length : 0;
  if (dt) dt.textContent = `${nMembers ? nMembers + " ensemble members" : "Ensemble"} vs. ${(om.model || {}).label || "selected model"}, next 24 h, 48 h and 7 days`;

  const W = Math.max(280, Math.round(box.clientWidth || 360));
  const L = 40, R = 6, T = 22, PH = 170, tickH = 30, labH = 50, H = T + PH + tickH + labH;
  const gap = W < 480 ? 8 : 18;
  const pw = (W - L - R - gap * 2) / 3;
  const maxIn = (() => { const v = U.snowNum(allMax) * 1.05; const st = niceStep(v, 4); return Math.ceil(v / st) * st; })();
  const Y = v => T + PH * (1 - Math.min(1, v / maxIn));
  let s = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg" font-family="var(--font-sans)">`;
  const tickStep = niceStep(maxIn, 4);
  for (let v = 0; v <= maxIn + 1e-6; v += tickStep) {
    s += `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" stroke="rgba(255,255,255,${v === 0 ? 0.18 : 0.06})"/>
      <text x="${L - 6}" y="${Y(v) + 4}" text-anchor="end" fill="#94a3b8" font-size="11" style="font-variant-numeric:tabular-nums">${+v.toFixed(1)}</text>`;
  }
  s += `<text x="${L - 6}" y="${T - 10}" text-anchor="end" fill="#64748b" font-size="10">${unit}</text>`;
  periods.forEach(([k, mk, label], pi) => {
    const x0 = L + pi * (pw + gap), cx = x0 + pw / 2, hw = pw / 2 - 4;
    // % of members axis: 50 and 100 on both sides of the center line
    [0.5, 1].forEach(f => [-1, 1].forEach(dir => {
      const x = cx + dir * hw * f;
      s += `<line x1="${x}" x2="${x}" y1="${T}" y2="${T + PH}" stroke="rgba(255,255,255,${f === 1 ? 0.05 : 0.08})" stroke-dasharray="${f === 1 ? "" : "2 3"}"/>
        <line x1="${x}" x2="${x}" y1="${T + PH}" y2="${T + PH + 4}" stroke="#64748b"/>
        <text x="${x}" y="${T + PH + 14}" text-anchor="middle" fill="#64748b" font-size="${pw < 120 ? 7.5 : 9.5}" style="font-variant-numeric:tabular-nums">${f * 100}</text>`;
    }));
    s += `<line x1="${cx}" x2="${cx}" y1="${T}" y2="${T + PH}" stroke="rgba(255,255,255,0.22)"/>
      <text x="${cx}" y="${T + PH + 26}" text-anchor="middle" fill="#64748b" font-size="9.5">% of members</text>`;
    sides.forEach(([t, col, , dir]) => {
      const mem = (((c[t] || {}).members || {})[mk]) || [];
      if (mem.length >= 5) {
        // width at an amount = share of members forecasting at least that much (100% at zero, 50% at the median)
        const vals = mem.map(v => U.snowNum(v)).sort((a, b) => a - b), N = vals.length;
        const n = 160;
        const ys = Array.from({ length: n + 1 }, (_, i) => maxIn * i / n);
        let j = 0;
        const share = ys.map(y => { while (j < N && vals[j] < y) j++; return (N - j) / N; });
        const pts = ys.map((y, i) => `${(cx + dir * hw * share[i]).toFixed(1)},${Y(y).toFixed(1)}`);
        const lastIdx = share.reduce((acc, v, i) => (v > 0 ? i : acc), 0);
        const outline = pts.slice(0, lastIdx + 1).concat([`${cx.toFixed(1)},${Y(ys[Math.min(n, lastIdx + 1)]).toFixed(1)}`]);
        s += `<path d="M${cx},${Y(0)} L${outline.join(" L")} Z" fill="${col}" fill-opacity="${t === "summit" ? 0.3 : 0.24}" stroke="none"/>
          <path d="M${outline.join(" L")}" fill="none" stroke="${col}" stroke-width="1.2"/>`;
        const med = vals[Math.floor(N / 2)];
        s += `<circle cx="${cx + dir * hw * 0.5}" cy="${Y(med)}" r="3" fill="${col}" stroke="#0b1220" stroke-width="1"><title>${t} ensemble median ${fmt(med)} (50% of members at least this)</title></circle>`;
        const beyond = vals.filter(v => v > maxIn).length;
        if (beyond) s += `<text x="${cx + dir * 4}" y="${T + 10}" text-anchor="${dir < 0 ? "end" : "start"}" fill="${col}" font-size="10">▲ ${beyond}</text>`;
      }
      const v = ((c[t] || {})[k] || {}).value;
      if (v != null) {
        const vv = U.snowNum(v), N2 = mem.length;
        const pAt = N2 ? Math.round(100 * mem.filter(m => U.snowNum(m) >= vv).length / N2) : null;
        s += `<line x1="${cx}" x2="${cx + dir * hw}" y1="${Y(vv)}" y2="${Y(vv)}" stroke="#f8fafc" stroke-width="2"><title>${t} ${(om.model || {}).label || "model"} ${fmt(v)}${pAt != null ? `: ${pAt}% of members at least this` : ""}</title></line>`;
      }
    });
    const by = T + PH + tickH + 16;
    s += `<text x="${cx}" y="${by}" text-anchor="middle" fill="#e2e8f0" font-size="12" font-weight="650">${label}</text>
      <text x="${cx}" y="${by + 15}" text-anchor="middle" font-size="11" style="font-variant-numeric:tabular-nums" fill="#fbbf24">Base ${fmt(((c.base || {})[k] || {}).value)}</text>
      <text x="${cx}" y="${by + 29}" text-anchor="middle" font-size="11" style="font-variant-numeric:tabular-nums" fill="#7dd3fc">Summit ${fmt(((c.summit || {})[k] || {}).value)}</text>`;
  });
  box.innerHTML = s + "</svg>";
}
window.addEventListener("resize", (() => {
  let t = null, lastW = 0;
  return () => {
    clearTimeout(t);
    t = setTimeout(() => {
      const box = document.getElementById("dist-chart");
      if (box && window.__distResort && Math.abs(box.clientWidth - lastW) > 8) { lastW = box.clientWidth; renderDistribution(window.__distResort); }
    }, 150);
  };
})());

function renderSynopticDiscussion(resort) {
  const box = document.getElementById("afd-grid");
  if (!box) return;
  const nws = (resort.sources || {}).noaa_nws || {};
  const esc = t => t.replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  const list = (nws.discussions && nws.discussions.length) ? nws.discussions
    : [{ office: nws.office || "REV", role: "resort office (base point)", text: nws.synoptic_discussion || "" }];
  box.innerHTML = list.map((d, i) => {
    const paras = (d.text || "").split(/\n\s*\n/).map(p => p.trim()).filter(Boolean);
    const issued = paras.length && /^Issued /.test(paras[paras.length - 1]) ? paras.pop() : null;
    const body = paras.length ? paras.map(p => /^[*-]\s/.test(p) ? `<p class="afd-bullet">${esc(p.replace(/^[*-]\s*/, ""))}</p>` : `<p>${esc(p)}</p>`).join("")
      : `<p class="muted">Discussion unavailable.</p>`;
    const name = NWS_OFFICES[d.office] || d.office;
    return `<article class="card afd">
      <header>
        <div><h3>NWS ${esc(name)} (${esc(d.office)})</h3>
          <div class="mini-label">${issued ? esc(issued.replace("Issued ", "Issued ")) : "Issue time n/a"} · fetched ${Fmt.ago(nws.fetched_at_utc)}</div></div>
        <a class="text-btn" href="https://forecast.weather.gov/product.php?site=${d.office}&issuedby=${d.office}&product=AFD" target="_blank" rel="noopener">Full discussion ↗</a>
      </header>
      <div class="afd-text">${body}</div>
    </article>`;
  }).join("");
}

/* ==========================================================================
   48-HOUR STACKED FORECAST CHART
   Five panels share one time axis, each with its own labeled scale
   (no dual axes):
     1. Accumulated snow (in), selected tier highlighted, other tiers faint
     2. Hourly snowfall (in/hr), SLR-adjusted
     3. Precip type strip (snow / mix / rain), opacity = chance of precip
     4. Wind at the selected tier (sustained line + gust bars by hold threshold)
     5. Time-height profile: DGZ band, snow level, freezing level, tier heights
   ========================================================================== */
let currentTier = "summit";
const TIER_LABEL = { base: "Base", mid: "Mid Mtn", summit: "Summit" };
const PHASE_COLOR = { snow: "#7dd3fc", mix: "#c084fc", rain: "#4ade80", ice: "#fb7185", dry: "transparent" };
const SVGNS = "http://www.w3.org/2000/svg";

function setTier(tier) {
  if (!TIER_LABEL[tier]) return;
  currentTier = tier;
  document.querySelectorAll(".tier-toggle-btn").forEach(b => b.classList.toggle("active", b.dataset.tier === tier));
  const resort = activeResort();
  if (resort) renderHourlyDualAxisChart(resort);
  document.dispatchEvent(new CustomEvent("snow:tier", { detail: { tier, resort } }));
}

function setupTierToggle() {
  document.querySelectorAll(".tier-toggle-btn").forEach(btn => {
    btn.addEventListener("click", () => setTier(btn.dataset.tier));
  });
}

function niceStep(max, targetTicks) {
  const raw = max / targetTicks;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const n = raw / mag;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * mag;
}

function niceAxis(maxVal, minTop, ticks = 4) {
  const top0 = Math.max(minTop, maxVal * 1.08);
  const step = niceStep(top0, ticks);
  return { max: Math.ceil(top0 / step) * step, step };
}

function fmtFt(v) { return v == null ? "n/a" : `${Math.round(v).toLocaleString()} ft`; }
function compass(deg) {
  return ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"][Math.round(deg / 22.5) % 16];
}

function renderHourlyDualAxisChart(resort) {
  const container = document.getElementById("chart-svg-container");
  if (!container) return;

  const om = (resort.sources && resort.sources.open_meteo) || {};
  const tls = om.elevation_timelines || {};
  const tl = (tls[currentTier] && tls[currentTier].length ? tls[currentTier] : (om.hourly_timeline || [])).slice(0, 168);
  const profile = (om.vertical_profile && om.vertical_profile.length ? om.vertical_profile : tl.map(x => ({ time: x.time, snow_level_ft: x.snow_level_ft, freezing_level_ft: x.freezing_level_ft }))).slice(0, 168);
  const elevs = resort.elevations || {};

  // Header + toggle labels
  const tierFt = elevs[`${currentTier}_ft`];
  const sub = document.getElementById("chart-tier-subtitle");
  const isNBM = (om.model || {}).id === "nbm";
  if (sub) sub.textContent = `${TIER_LABEL[currentTier]} (${tierFt ? tierFt.toLocaleString() + " ft" : "--"}). ${isNBM ? (om.nbm_elevation_adjustment ? "Snowfall is the NBM's own snowfall field, moved from its 2.5 km cell to this elevation with NBM's hourly elevation relationship" : "Snowfall is the NBM's own snowfall field at the nearest 2.5 km grid point") : "Snowfall uses the unadjusted Cobb-style snow/liquid ratio"}; wind is at this elevation.`;
  const lgs = document.getElementById("legend-snow"); if (lgs) lgs.textContent = isNBM ? "Snowfall (NBM snowfall field)" : "Snowfall (Cobb-style SLR, unadjusted)";
  const lgr = document.getElementById("legend-raw"); if (lgr) lgr.style.display = isNBM ? "none" : "";
  const colSrc = (om.profile_model || {}).label || (om.blend ? om.blend.profile_from : ((om.model || {}).label || "model"));
  const lsl = document.getElementById("legend-sl"); if (lsl) lsl.textContent = isNBM ? "Snow level (NBM's own field)" : `Snow level (${colSrc} wet-bulb zero − 500 ft)`;
  const lfz = document.getElementById("legend-fz"); if (lfz) lfz.textContent = `Freezing level (${colSrc} column)`;
  const ceb = document.getElementById("chart-eyebrow");
  if (ceb) ceb.textContent = `Model: ${(om.primary_model || {}).label || ""} · ${tl.length} h · fetched ${Fmt.ago(om.fetched_at_utc)}`;
  document.querySelectorAll("[data-tier-elev]").forEach(el => {
    const ft = elevs[`${el.dataset.tierElev}_ft`];
    if (ft) el.textContent = `${ft.toLocaleString()} ft`;
  });
  const fdl = document.getElementById("fan-det-label"); if (fdl) fdl.textContent = `${(om.model || {}).label || "Selected model"} (deterministic)`;

  if (!tl.length) {
    container.innerHTML = `<p style="padding:30px;color:#94a3b8;text-align:center;">Hourly timeline data unavailable.</p>`;
    return;
  }

  // ---- Layout ----
  const W = 1040, padL = 64, padR = 124;
  const plotW = W - padL - padR;
  const n = tl.length;
  const step = plotW / n;
  const xOf = i => padL + i * step;
  const xMid = i => padL + (i + 0.5) * step;

  const panels = {};
  let y = 14;
  const addPanel = (key, h, title, gap = 30) => { panels[key] = { top: y + 16, h, title }; y += 16 + h + gap; };
  addPanel("cum", 120, `ACCUMULATED SNOW (${U.snowAxisUnit().toUpperCase()})`);
  addPanel("rate", 80, `HOURLY SNOWFALL (${U.snowAxisUnit().toUpperCase()}/HR)`);
  addPanel("ptype", 18, "PRECIP TYPE · OPACITY = CHANCE OF PRECIP", 30);
  addPanel("wind", 100, `WIND AT ${TIER_LABEL[currentTier].toUpperCase()} (MPH) · LINE = SUSTAINED, BARS = GUSTS`);
  addPanel("prof", 170, "WHERE SNOW FORMS & FALLS (FT ABOVE SEA LEVEL)", 8);
  const axisY = y + 4;
  const H = axisY + 34;

  let s = `<svg viewBox="0 0 ${W} ${H}" xmlns="${SVGNS}" font-family="var(--font-sans)">`;
  s += `<defs>
    <pattern id="hatchLift" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <line x1="0" y1="0" x2="0" y2="6" stroke="#e0f2fe" stroke-width="1.6" stroke-opacity="0.75"/>
    </pattern>
  </defs>`;

  const grid = (p, val, max, label, strong) => {
    const yy = p.top + p.h * (1 - val / max);
    s += `<line x1="${padL}" x2="${padL + plotW}" y1="${yy}" y2="${yy}" stroke="rgba(255,255,255,${strong ? 0.16 : 0.06})" stroke-width="1"/>`;
    s += `<text x="${padL - 8}" y="${yy + 3.5}" fill="#94a3b8" font-size="10" text-anchor="end" font-family="var(--font-mono)">${label}</text>`;
  };
  const title = p => { s += `<text x="${padL}" y="${p.top - 6}" fill="#cbd5e1" font-size="10" font-weight="700" letter-spacing="0.6">${p.title}</text>`; };

  // Day separators across all panels
  tl.forEach((st, i) => {
    const d = new Date(st.time);
    if (d.getHours() === 0 && i > 0) {
      s += `<line x1="${xOf(i)}" x2="${xOf(i)}" y1="${panels.cum.top - 4}" y2="${axisY}" stroke="rgba(255,255,255,0.14)" stroke-dasharray="2,3"/>`;
    }
  });

  // ---- Panel 1: accumulation ----
  {
    const p = panels.cum; title(p);
    const tiers = ["base", "mid", "summit"].filter(t => tls[t] && tls[t].length);
    const lastCum = t => U.snowNum((tls[t].slice(0, n).slice(-1)[0] || {}).cumulative_snow_inches || 0);
    const maxCum = Math.max(...tiers.map(lastCum), U.snowNum((tl[n - 1] || {}).cumulative_snow_inches || 0), ...(tl.map(x => U.snowNum(x.model_cumulative_inches || 0))));
    const scl = (om.scales || {}).cumulative_in;
    const ax = niceAxis(scl ? U.snowNum(scl) : maxCum, U.snowNum(6), 4);
    for (let v = 0; v <= ax.max + 1e-6; v += ax.step) grid(p, v, ax.max, `${+v.toFixed(1)}`, v === 0);
    const yv = v => p.top + p.h * (1 - Math.min(v, ax.max) / ax.max);
    const pathFor = arr => arr.map((x, i) => `${i ? "L" : "M"}${xMid(i).toFixed(1)},${yv(x).toFixed(1)}`).join(" ");
    let rawLabel = null;

    // Model raw (7:1) for the selected tier, for comparison
    if (!isNBM && tl.some(x => x.model_cumulative_inches != null)) {
      s += `<path d="${pathFor(tl.map(x => U.snowNum(x.model_cumulative_inches || 0)))}" fill="none" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="5,4"/>`;
      const mv = U.snowNum(tl[n - 1].model_cumulative_inches || 0);
      rawLabel = { v: mv };
    }
    // Other tiers faint, selected tier filled; end labels collected and spread so they never overlap
    const endLabels = [];
    tiers.forEach(t => {
      const arr = tls[t].slice(0, n).map(x => U.snowNum(x.cumulative_snow_inches || 0));
      const sel = t === currentTier;
      if (sel) {
        s += `<path d="${pathFor(arr)} L${xMid(arr.length - 1)},${p.top + p.h} L${xMid(0)},${p.top + p.h} Z" fill="rgba(125,211,252,0.14)"/>`;
        // blend: range of the members' own totals (lowest to highest member at each hour)
        const tt = tls[t].slice(0, n);
        if (tt.length && tt[0].member_cum_snow_max != null) {
          const hiA = tt.map(x => U.snowNum(x.member_cum_snow_max || 0)), loA = tt.map(x => U.snowNum(x.member_cum_snow_min || 0));
          s += `<path d="${pathFor(hiA)} ${loA.map((v, i) => `L${xMid(i).toFixed(1)},${yv(v).toFixed(1)}`).reverse().join(" ")} Z" fill="rgba(167,139,250,0.2)" stroke="rgba(167,139,250,0.55)" stroke-width="0.8"/>`;
          const a = loA[loA.length - 1], b = hiA[hiA.length - 1];
          endLabels.push({ y: yv(b) + 4, txt: `members ${a.toFixed(a >= 10 ? 0 : 1)}–${b.toFixed(b >= 10 ? 0 : 1)}${U.snowSuffix()}`, fill: "#c4b5fd", size: 10, weight: 600 });
        }
      }
      s += `<path d="${pathFor(arr)}" fill="none" stroke="${sel ? "#f8fafc" : "rgba(203,213,225,0.45)"}" stroke-width="${sel ? 2.4 : 1.4}"/>`;
      const v = arr[arr.length - 1];
      endLabels.push({ y: yv(v) + 4, txt: `${v.toFixed(v >= 10 ? 0 : 1)}${U.snowSuffix()} ${TIER_LABEL[t]}`, fill: sel ? "#f8fafc" : "#94a3b8", size: sel ? 11 : 10, weight: sel ? 800 : 600 });
    });
    if (rawLabel) endLabels.push({ y: yv(rawLabel.v) + 4, txt: `${rawLabel.v.toFixed(rawLabel.v >= 10 ? 0 : 1)}${U.snowSuffix()} 7:1 field (${TIER_LABEL[currentTier]})`, fill: "#94a3b8", size: 10, weight: 500, italic: true });
    endLabels.sort((a, b) => a.y - b.y);
    const gap = 12, lo = p.top + 8, hi = p.top + p.h + 8;
    endLabels.forEach((l, i) => { l.y = Math.max(l.y, lo, i ? endLabels[i - 1].y + gap : lo); });
    const over = endLabels.length ? endLabels[endLabels.length - 1].y - hi : 0;
    if (over > 0) endLabels.forEach(l => { l.y -= over; });
    endLabels.forEach(l => {
      s += `<text x="${padL + plotW + 6}" y="${l.y.toFixed(1)}" fill="${l.fill}" font-size="${l.size}" font-weight="${l.weight}"${l.italic ? ' font-style="italic"' : ""}>${l.txt}</text>`;
    });
  }

  // ---- Panel 2: hourly rate ----
  {
    const p = panels.rate; title(p);
    // Fixed 0-3 in/hr (0-7.5 cm/hr): rates above that are rare; a bar that exceeds it is capped and marked.
    const ax = U.metricSnow() ? { max: 7.5, step: 2.5 } : { max: 3, step: 1 };
    for (let v = 0; v <= ax.max + 1e-6; v += ax.step) grid(p, v, ax.max, `${+v.toFixed(2)}`, v === 0);
    const bw = Math.max(3, step - 3);
    tl.forEach((x, i) => {
      const r = U.snowNum(x.snowfall_rate_in_hr || 0);
      if (r <= 0) return;
      const h = Math.max(1.5, p.h * Math.min(r, ax.max) / ax.max);
      s += `<rect x="${xOf(i) + 1.5}" y="${p.top + p.h - h}" width="${bw}" height="${h}" rx="2" fill="#f8fafc" fill-opacity="${0.55 + 0.45 * (x.snow_fraction ?? 1)}"/>`;
      if (r > ax.max) s += `<path d="M${xOf(i) + 1.5},${p.top - 1} l${bw / 2},-5 l${bw / 2},5 Z" fill="#fbbf24"><title>${U.snow(x.snowfall_rate_in_hr)}/hr</title></path>`;
    });
    const tot24 = tl.slice(0, 24).reduce((a, x) => a + (x.snowfall_rate_in_hr || 0), 0);
    s += `<text x="${padL + plotW + 6}" y="${p.top + 12}" fill="#cbd5e1" font-size="10">Next 24h</text>`;
    s += `<text x="${padL + plotW + 6}" y="${p.top + 26}" fill="#f8fafc" font-size="12" font-weight="800">${U.snow(tot24)}</text>`;
  }

  // ---- Panel 3: precip type strip ----
  {
    const p = panels.ptype; title(p);
    tl.forEach((x, i) => {
      const ph = x.precip_phase || "dry";
      const pop = (x.precip_probability ?? 0) / 100;
      if (ph === "dry" && pop < 0.2) {
        s += `<rect x="${xOf(i) + 1}" y="${p.top}" width="${step - 2}" height="${p.h}" rx="2" fill="rgba(255,255,255,0.04)"/>`;
        return;
      }
      const col = PHASE_COLOR[ph === "dry" ? "snow" : ph];
      s += `<rect x="${xOf(i) + 1}" y="${p.top}" width="${step - 2}" height="${p.h}" rx="2" fill="${col}" fill-opacity="${(0.15 + 0.85 * pop).toFixed(2)}"/>`;
    });
    // Direct labels on the right: share of liquid falling as snow
    const wet = tl.filter(x => (x.precip_in || 0) >= 0.01);
    const liq = wet.reduce((a, x) => a + x.precip_in, 0);
    const snowPct = liq > 0 ? Math.round(100 * wet.reduce((a, x) => a + x.precip_in * (x.snow_fraction ?? 1), 0) / liq) : null;
    s += `<text x="${padL + plotW + 6}" y="${p.top + 13}" fill="#cbd5e1" font-size="10">${snowPct == null ? "Dry" : snowPct + "% as snow"}</text>`;
  }

  // ---- Panel 4: wind ----
  {
    const p = panels.wind; title(p);
    const maxG = Math.max((om.scales || {}).gust_mph || 0, ...tl.map(x => x.gust_mph || 0), 70);
    const ax = niceAxis(maxG, 70, 4);
    for (let v = 0; v <= ax.max + 1e-6; v += ax.step) grid(p, v, ax.max, `${v}`, v === 0);
    const yv = v => p.top + p.h * (1 - Math.min(v, ax.max) / ax.max);
    [[45, "#f59e0b", "45: holds possible"], [65, "#ef4444", "65: upper lifts hold"]].forEach(([v, c, lbl]) => {
      s += `<line x1="${padL}" x2="${padL + plotW}" y1="${yv(v)}" y2="${yv(v)}" stroke="${c}" stroke-width="1" stroke-dasharray="4,4" opacity="0.7"/>`;
      s += `<text x="${padL + plotW + 6}" y="${yv(v) + 3.5}" fill="#cbd5e1" font-size="9.5">${lbl}</text>`;
    });
    const bw = Math.max(3, step - 3);
    tl.forEach((x, i) => {
      const g = x.gust_mph || 0;
      const c = g >= 65 ? "#ef4444" : g >= 45 ? "#f59e0b" : "#10b981";
      s += `<rect x="${xOf(i) + 1.5}" y="${yv(g)}" width="${bw}" height="${p.top + p.h - yv(g)}" rx="2" fill="${c}" fill-opacity="0.55"/>`;
    });
    s += `<path d="${tl.map((x, i) => `${i ? "L" : "M"}${xMid(i).toFixed(1)},${yv(x.wind_mph || 0).toFixed(1)}`).join(" ")}" fill="none" stroke="#f8fafc" stroke-width="2"/>`;
    // direction arrows every 6h (arrow points where wind blows TO)
    tl.forEach((x, i) => {
      if (i % 6 !== 3 || x.wind_dir_deg == null) return;
      const cx = xMid(i), cy = p.top + 8;
      s += `<g transform="translate(${cx},${cy}) rotate(${(x.wind_dir_deg + 180) % 360})"><path d="M0,-6 L4,4 L0,1.5 L-4,4 Z" fill="#cbd5e1"/></g>`;
    });
  }

  // ---- Panel 5: time-height profile ----
  {
    const p = panels.prof; title(p);
    const yMin = 4000, yMax = 20000;
    const yv = v => p.top + p.h * (1 - (Math.max(yMin, Math.min(yMax, v)) - yMin) / (yMax - yMin));
    for (let v = yMin; v <= yMax; v += 2000) {
      const yy = yv(v);
      s += `<line x1="${padL}" x2="${padL + plotW}" y1="${yy}" y2="${yy}" stroke="rgba(255,255,255,0.05)"/>`;
      s += `<text x="${padL - 8}" y="${yy + 3.5}" fill="#94a3b8" font-size="10" text-anchor="end" font-family="var(--font-mono)">${(v / 1000)}k</text>`;
    }
    if (profile.length) {
      // DGZ band: opacity by RH; hatched where saturated AND rising (crosshair)
      profile.forEach((pr, i) => {
        if (pr.dgz_base_ft == null || pr.dgz_top_ft == null || i >= n) return;
        const y1 = yv(pr.dgz_top_ft), y2 = yv(pr.dgz_base_ft);
        const rh = (pr.dgz_rh_pct ?? 50) / 100;
        s += `<rect x="${xOf(i)}" y="${y1}" width="${step + 0.5}" height="${Math.max(1, y2 - y1)}" fill="#38bdf8" fill-opacity="${Math.max(0.08, (rh - 0.4) * 0.9).toFixed(2)}"/>`;
        if ((pr.dgz_rh_pct ?? 0) >= 85 && (pr.dgz_lift_cm_s ?? 0) >= 10) {
          s += `<rect x="${xOf(i)}" y="${y1}" width="${step + 0.5}" height="${Math.max(1, y2 - y1)}" fill="url(#hatchLift)"/>`;
        }
      });
      const line = (key, col, dash, w) => {
        const pts = profile.slice(0, n).map((pr, i) => pr[key] == null ? null : `${xMid(i).toFixed(1)},${yv(pr[key]).toFixed(1)}`);
        let d = "", pen = false;
        pts.forEach(pt => { if (!pt) { pen = false; return; } d += (pen ? "L" : "M") + pt + " "; pen = true; });
        s += `<path d="${d}" fill="none" stroke="${col}" stroke-width="${w}" ${dash ? `stroke-dasharray="${dash}"` : ""}/>`;
      };
      line("freezing_level_ft", "#fbbf24", "6,4", 1.6);
      line("snow_level_ft", "#f8fafc", null, 2.2);
      const last = profile[Math.min(n, profile.length) - 1];
      const lbls = [];
      const rlabel = (v, txt, col) => {
        if (v == null) return;
        let ly = yv(v) + 4; lbls.forEach(o => { if (Math.abs(o - ly) < 12) ly = o + 12; }); lbls.push(ly);
        s += `<text x="${padL + plotW + 6}" y="${ly}" fill="${col}" font-size="10" font-weight="700">${txt}</text>`;
      };
      rlabel(last.dgz_top_ft != null ? (last.dgz_top_ft + last.dgz_base_ft) / 2 : null, "DGZ", "#7dd3fc");
      rlabel(last.freezing_level_ft, "Freezing lvl", "#fbbf24");
      rlabel(last.snow_level_ft, "Snow level", "#f8fafc");
    }
    // Tier elevations
    ["base", "mid", "summit"].forEach(t => {
      const ft = elevs[`${t}_ft`]; if (!ft) return;
      const sel = t === currentTier;
      s += `<line x1="${padL}" x2="${padL + plotW}" y1="${yv(ft)}" y2="${yv(ft)}" stroke="${sel ? "#f472b6" : "rgba(244,114,182,0.4)"}" stroke-width="${sel ? 1.6 : 1}" stroke-dasharray="${sel ? "" : "2,3"}"/>`;
      s += `<text x="${padL + 4 + { base: 0, mid: 104, summit: 208 }[t]}" y="${yv(ft) - 3}" fill="${sel ? "#f9a8d4" : "#94a3b8"}" font-size="9.5" font-weight="${sel ? 800 : 600}">${TIER_LABEL[t]} ${ft.toLocaleString()}'</text>`;
    });
  }

  // ---- X axis ----
  tl.forEach((x, i) => {
    const d = new Date(x.time);
    if (i % (n > 72 ? 12 : 3) === 0) {
      s += `<text x="${xMid(i)}" y="${axisY + 12}" fill="#94a3b8" font-size="10" text-anchor="middle">${d.toLocaleTimeString([], { hour: "numeric" })}</text>`;
    }
    const firstMidnight = tl.findIndex(z => new Date(z.time).getHours() === 0);
    if (d.getHours() === 0 || (i === 0 && (firstMidnight < 0 || firstMidnight > 6))) {
      s += `<text x="${xOf(i) + 2}" y="${axisY + 27}" fill="#cbd5e1" font-size="10" font-weight="700">${d.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })}</text>`;
    }
  });

  // ---- Hover targets + crosshair ----
  s += `<line id="chart-crosshair" x1="0" x2="0" y1="${panels.cum.top}" y2="${axisY}" stroke="#f8fafc" stroke-opacity="0.5" stroke-width="1" visibility="hidden"/>`;
  tl.forEach((x, i) => {
    s += `<rect class="chart-hit" data-idx="${i}" x="${xOf(i)}" y="${panels.cum.top - 4}" width="${step}" height="${axisY - panels.cum.top + 4}" fill="transparent"/>`;
  });
  s += `</svg>`;

  container.innerHTML = s;
  setupChartHoverTooltips(tl, profile, xMid);
}

function setupChartHoverTooltips(tl, profile, xMid) {
  const tooltip = document.getElementById("chart-tooltip");
  const cross = document.getElementById("chart-crosshair");
  const wrap = document.querySelector(".chart-wrapper");
  if (!tooltip || !wrap) return;

  const row = (l, v, c) => `<div class="tt-row"><span class="tt-label">${l}</span><span class="tt-val"${c ? ` style="color:${c}"` : ""}>${v}</span></div>`;

  document.querySelectorAll(".chart-hit").forEach(hit => {
    hit.addEventListener("mouseenter", () => {
      const i = +hit.dataset.idx;
      const x = tl[i]; const pr = profile[i] || {};
      if (!x) return;
      const d = new Date(x.time);
      const ph = x.precip_phase || "dry";
      const gust = x.gust_mph || 0;
      const gc = gust >= 65 ? "#fca5a5" : gust >= 45 ? "#fcd34d" : "#6ee7b7";
      const lift = pr.dgz_lift_cm_s;
      const crosshair = (pr.dgz_rh_pct ?? 0) >= 85 && (lift ?? 0) >= 10;
      tooltip.innerHTML = `
        <div class="tt-time">${d.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })} · ${d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</div>
        ${row("Precip type", `<span style="color:${PHASE_COLOR[ph] === "transparent" ? "#94a3b8" : PHASE_COLOR[ph]}">${x.precip_phase_label || ph}</span>`)}
        ${row("Chance of precip", `${x.precip_probability ?? "n/a"}%`)}
        ${x.chance_snow_pct != null ? row("Chance snow / rain", `${x.chance_snow_pct}% / ${x.chance_rain_pct}%`) : ""}
        ${row("Snowfall", `${U.snow(x.snowfall_rate_in_hr || 0, U.metricSnow() ? 1 : 2)} /hr`)}
        ${row("Accumulated", U.snow(x.cumulative_snow_inches || 0, 1))}
        ${x.precip_in != null ? row("Liquid · SLR", `${U.liquid(x.precip_in)} · ${x.slr != null ? x.slr + ":1" : "n/a"}`) : ""}
        ${row("Temp / wet bulb", `${U.tempShort(x.temp_f)} / ${U.temp(x.wet_bulb_f)}`)}
        ${row("Wind", `${Math.round(x.wind_mph || 0)} mph${x.wind_dir_deg != null ? " " + compass(x.wind_dir_deg) : ""}`)}
        ${row("Gusts", `${Math.round(gust)} mph`, gc)}
        ${row("Snow level", fmtFt(pr.snow_level_ft ?? x.snow_level_ft))}
        ${row("Freezing level", fmtFt(pr.freezing_level_ft ?? x.freezing_level_ft))}
        ${pr.dgz_base_ft != null ? row("DGZ layer", `${fmtFt(pr.dgz_base_ft)} – ${fmtFt(pr.dgz_top_ft)}`) : ""}
        ${pr.dgz_rh_pct != null ? row("DGZ RH · lift", `${pr.dgz_rh_pct}% · ${lift > 0 ? "+" : ""}${lift} cm/s`, crosshair ? "#7dd3fc" : null) : ""}
        ${x.mixing_ratio_g_kg != null ? row("Mixing ratio", `${x.mixing_ratio_g_kg.toFixed(1)} g/kg`) : ""}
        ${crosshair ? `<div style="margin-top:6px;color:#7dd3fc;font-size:11px;font-weight:700;">Saturated, rising DGZ: efficient dendrite growth</div>` : ""}
      `;
      tooltip.style.display = "block";
      if (cross) { cross.setAttribute("x1", xMid(i)); cross.setAttribute("x2", xMid(i)); cross.setAttribute("visibility", "visible"); }
    });
    hit.addEventListener("mousemove", e => {
      const r = wrap.getBoundingClientRect();
      const tw = tooltip.offsetWidth || 240;
      let left = e.clientX - r.left + 16;
      if (left + tw > r.width) left = e.clientX - r.left - tw - 16;
      tooltip.style.left = `${Math.max(0, left)}px`;
      tooltip.style.top = `${Math.max(0, e.clientY - r.top - 60)}px`;
    });
    hit.addEventListener("mouseleave", () => {
      tooltip.style.display = "none";
      if (cross) cross.setAttribute("visibility", "hidden");
    });
  });
}

/* ==========================================================================
   SOUNDING / MICROPHYSICS CARDS
   ========================================================================== */
function renderSounding(resort) {
  const om = (resort.sources && resort.sources.open_meteo) || {};
  const snd = om.atmospheric_sounding || {};
  if (snd.available === false) {
    ["dgz-thickness-val", "dgz-layer-val", "dgz-pres-val", "dgz-rh-val", "dgz-lift-val", "dgz-hours-val", "dgz-crystal-val"].forEach(id => { const e = document.getElementById(id); if (e) e.textContent = "n/a"; });
    const b = document.getElementById("dgz-badge"); if (b) { b.textContent = "No profile"; b.className = "chip"; b.title = snd.reason || ""; }
    const eb = document.getElementById("atmo-eyebrow"); if (eb) eb.textContent = snd.reason || "No vertical profile for this model";
    const pr = document.getElementById("phase-risk-badge"); if (pr) { pr.textContent = "NBM snow level"; pr.className = "chip"; }
    ["dgz-rh-bar", "dgz-lift-bar"].forEach(id => { const e = document.getElementById(id); if (e) e.style.width = "0"; });
    // moisture and crest wind come from the surface fields and follow the slider (panels.js renderMoisture)
    return;
  }
  const dgz = snd.dgz || {}, ph = snd.precipitation_phase_analysis || {}, md = snd.moisture_and_dynamics || {};
  const set = (id, v, html) => { const el = document.getElementById(id); if (el && v != null) el[html ? "innerHTML" : "textContent"] = v; };
  const width = (id, pct, left) => { const el = document.getElementById(id); if (el) { el.style.width = `${Math.max(0, Math.min(100, pct))}%`; if (left != null) el.style.left = `${left}%`; } };
  const eb = document.getElementById("atmo-eyebrow");
  if (eb) {
    const q = (om.query_points || {}).summit || {}, pm = om.profile_model;
    eb.textContent = pm
      ? `Column: ${pm.label} at ${q.lat ?? "?"}, ${q.lon ?? "?"} (${(om.model || {}).label} has no vertical profile) · snow level and surface values: ${(om.model || {}).label}`
      : `Model sounding (${(om.primary_model || {}).label || "model"}) at ${q.lat ?? "?"}, ${q.lon ?? "?"}`;
  }

  // DGZ
  const badge = document.getElementById("dgz-badge");
  if (badge) {
    badge.textContent = { SATURATED_RISING: "Ice-saturated, rising", SATURATED: "Ice-saturated, weak lift", SUBSATURATED: "Subsaturated", ABSENT: "Not found" }[dgz.status] || "--";
    badge.className = "chip " + (dgz.status === "SATURATED_RISING" ? "chip-ice" : "");
    badge.title = dgz.criteria || "";
  }
  set("dgz-thickness-val", dgz.thickness_ft != null ? `${dgz.thickness_ft.toLocaleString()} ft<small>thick</small>` : "--", true);
  set("dgz-layer-val", dgz.base_elevation_ft ? `${fmtFt(dgz.base_elevation_ft)} – ${fmtFt(dgz.top_elevation_ft)}` : "n/a");
  set("dgz-pres-val", dgz.base_pressure_hpa ? `${dgz.base_pressure_hpa} – ${dgz.top_pressure_hpa} hPa` : "n/a");
  const rhi = dgz.relative_humidity_ice_pct;
  set("dgz-rh-val", rhi != null ? `${rhi}% (water ${dgz.relative_humidity_pct}%)` : "n/a");
  width("dgz-rh-bar", rhi != null ? rhi / 1.2 : 0);   // bar spans 0-120%; tick at 100%
  const lift = dgz.lift_cm_s ?? 0;
  set("dgz-lift-val", `${lift > 0 ? "+" : ""}${lift} cm/s`);
  const liftPct = Math.max(-50, Math.min(50, lift));
  width("dgz-lift-bar", Math.abs(liftPct), liftPct >= 0 ? 50 : 50 + liftPct);
  const lb = document.getElementById("dgz-lift-bar"); if (lb) lb.style.background = lift >= 10 ? "var(--ice)" : lift >= 0 ? "var(--indigo)" : "var(--bad)";
  set("dgz-hours-val", dgz.saturated_and_rising_hours_24h != null ? `${dgz.saturated_and_rising_hours_24h} of 24` : "n/a");
  set("dgz-crystal-val", dgz.avg_summit_slr ? `${dgz.avg_summit_slr}:1` : "n/a");

  // Phase card header (the column and table follow the scrubber; see panels.js)
  const risk = ph.base_rain_risk;
  const pr = document.getElementById("phase-risk-badge");
  if (pr) {
    pr.textContent = risk ? `Base rain risk: ${risk.toLowerCase()}` : "--";
    pr.className = "chip " + (risk === "LOW" ? "chip-good" : risk === "MODERATE" ? "chip-warn" : risk === "HIGH" ? "chip-bad" : "");
    pr.title = ph.base_rain_risk_criteria || "";
  }

  // Moisture and crest wind: hourly, see panels.js renderMoisture
}

/* ==========================================================================
   CALTRANS HIGHWAY ROAD MAP
   Native dark retina tiles (CARTO, no key) instead of CSS-inverted OSM,
   OSRM-routed road geometry, on-map labels and an R-level legend.
   ========================================================================== */
const R_LEVELS = [
  ["R-0", "#10b981", "No controls"],
  ["R-1", "#f59e0b", "Chains or snow tires (4WD/AWD exempt)"],
  ["R-2", "#f97316", "Chains unless 4WD/AWD + snow tires"],
  ["R-3", "#ef4444", "Chains on everyone"],
  ["CLOSED", "#e11d48", "Road closed"]
];
let roadLabelLayer = null;

function initRoadMap() {
  const mapEl = document.getElementById("road-map");
  if (!mapEl || roadMap) return;

  roadMap = L.map("road-map", { center: [39.15, -120.2], zoom: 10, zoomControl: true, scrollWheelZoom: false });

  // Esri basemaps: free, no API key. Dark canvas + dark hillshade so the
  // Sierra terrain reads under the colored routes.
  const esri = "https://server.arcgisonline.com/ArcGIS/rest/services";
  L.tileLayer(`${esri}/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}`, {
    attribution: 'Tiles &copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors · routes via OSRM',
    maxZoom: 16
  }).addTo(roadMap);
  L.tileLayer(`${esri}/Elevation/World_Hillshade_Dark/MapServer/tile/{z}/{y}/{x}`, {
    maxZoom: 16, opacity: 0.55
  }).addTo(roadMap);

  roadMap.createPane("labels");
  roadMap.getPane("labels").style.zIndex = 650;

  // Resorts
  const resortIcon = L.divIcon({ className: "map-resort-dot", iconSize: [14, 14] });
  [
    [[39.1970, -120.2356], "Palisades Tahoe", "Base 6,200' · Summit 9,050'"],
    [[39.1644, -120.2386], "Alpine Meadows", "Base 6,835' · Ward Peak 8,637'"]
  ].forEach(([ll, name, sub]) => {
    L.marker(ll, { icon: resortIcon }).addTo(roadMap)
      .bindTooltip(`<b>${name}</b><span>${sub}</span>`, { permanent: true, direction: "left", offset: [-8, 0], className: "map-label map-label-resort", pane: "labels" })
      .bindPopup(`<div class="map-popup-header">${name}</div><div class="map-popup-desc">${sub}</div>`);
  });

  // Towns (small reference labels)
  [
    [[39.3280, -120.1833], "Truckee"], [[39.1677, -120.1452], "Tahoe City"],
    [[39.2380, -120.0266], "Kings Beach"], [[39.2513, -119.9524], "Incline Village"],
    [[38.9399, -119.9772], "South Lake Tahoe"], [[39.5296, -119.8138], "Reno"],
    [[39.0985, -120.9530], "Colfax"], [[38.7296, -120.7985], "Placerville"],
    [[38.8500, -120.0200], "Meyers"]
  ].forEach(([ll, name]) => {
    L.marker(ll, { icon: L.divIcon({ className: "map-town-dot", iconSize: [5, 5] }), interactive: false }).addTo(roadMap)
      .bindTooltip(name, { permanent: true, direction: "right", offset: [4, 0], className: "map-label map-label-town", pane: "labels" });
  });

  // Gondola
  L.polyline([[39.1965, -120.2356], [39.1644, -120.2386]], { color: "#38bdf8", weight: 2, dashArray: "4,5", opacity: 0.8 })
    .addTo(roadMap).bindPopup(`<b>Base to Base Gondola</b><br>Subject to wind holds above ~45 mph`);

  // Legend
  const legend = L.control({ position: "bottomleft" });
  legend.onAdd = () => {
    const div = L.DomUtil.create("div", "map-legend");
    div.innerHTML = `<div class="map-legend-title">Caltrans chain control</div>` +
      R_LEVELS.map(([lvl, c, txt]) => `<div class="map-legend-row"><span class="map-legend-line${lvl === "CLOSED" ? " dashed" : ""}" style="--c:${c}"></span><b>${lvl}</b><span>${txt}</span></div>`).join("") +
      `<div class="map-legend-row"><span class="map-legend-line" style="--c:#64748b"></span><b>NV</b><span>Nevada road, no live feed</span></div>` +
      `<div class="map-legend-row"><span class="map-legend-pass"></span><b>▲</b><span>Mountain pass</span></div><div class="map-legend-foot">Full definitions below the map</div>`;
    L.DomEvent.disableClickPropagation(div);
    return div;
  };
  legend.addTo(roadMap);

  updateRoadMapData();
}

function updateRoadMapData() {
  if (!roadMap || !snowData || !snowData.road_conditions) return;
  const segments = snowData.road_conditions.segments || [];

  Object.values(roadLayers).forEach(layer => roadMap.removeLayer(layer));
  roadLayers = {};
  if (roadLabelLayer) roadMap.removeLayer(roadLabelLayer);
  roadLabelLayer = L.layerGroup().addTo(roadMap);

  segments.forEach(seg => {
    if (!seg.polyline || !seg.polyline.length) return;
    const isClosed = seg.status === "CLOSED";
    const color = seg.status_color || (isClosed ? "#e11d48" : "#10b981");
    const minor = /road/.test(seg.id);

    // dark casing under the colored line so it reads on any tile
    const casing = L.polyline(seg.polyline, { color: "#020617", weight: minor ? 6 : 8, opacity: 0.85, interactive: false });
    const line = L.polyline(seg.polyline, { color, weight: minor ? 3 : 4.5, opacity: 0.95, dashArray: isClosed ? "8,6" : null });
    const group = L.featureGroup([casing, line]).addTo(roadMap);

    line.bindPopup(`
      <div class="map-popup-header">${seg.name}</div>
      <div class="map-popup-status" style="background:${color}22;color:${color};border:1px solid ${color}66;">${seg.status}: ${seg.status_label}</div>
      <div class="map-popup-desc">
        <b>Checkpoint:</b> ${seg.checkpoint}<br>
        <b>Pass elevation:</b> ${seg.pass_elevation_ft > 0 ? seg.pass_elevation_ft.toLocaleString() + "'" : "Valley grade"}<br>
        <span style="display:inline-block;margin-top:4px;">${seg.description}</span>
      </div>`);
    roadLayers[seg.id] = group;

    // Route shield label near the middle of the line
    const shieldSvg = window.routeShield ? routeShield(seg.route, 24) : "";
    // Shield sits on the line, offset from the pass marker so labels don't stack
    const pl = seg.polyline;
    let anchorIdx = Math.floor(pl.length / 2);
    if (seg.shield_coords) {
      let best = Infinity;
      pl.forEach((pt, k) => { const d = (pt[0] - seg.shield_coords[0]) ** 2 + (pt[1] - seg.shield_coords[1]) ** 2; if (d < best) { best = d; anchorIdx = k; } });
    }
    const shift = Math.floor(pl.length * 0.18);
    anchorIdx = anchorIdx + shift < pl.length ? anchorIdx + shift : Math.max(0, anchorIdx - shift);
    const mid = pl[anchorIdx];
    if (!minor) {
      L.marker(mid, {
        icon: L.divIcon({ className: "", html: `<div class="map-shield" style="--c:${color}">${shieldSvg}<span class="lvl">${seg.status}</span></div>`, iconSize: null }),
        pane: "labels"
      }).on("click", () => line.openPopup(mid)).addTo(roadLabelLayer);
    }

    // Pass marker
    const pass = seg.coordinates && (seg.coordinates.pass || seg.coordinates.summit || seg.coordinates.echo_summit || seg.coordinates.emerald_bay_overlook);
    if (pass && seg.pass_elevation_ft > 6500 && seg.key_pass) {
      L.marker([pass.lat, pass.lon], { icon: L.divIcon({ className: "map-pass-icon", html: "▲", iconSize: [12, 12] }), interactive: false, pane: "labels" })
        .bindTooltip(`${seg.key_pass} ${seg.pass_elevation_ft.toLocaleString()}'`, { permanent: true, direction: "top", offset: [0, -6], className: "map-label map-label-pass", pane: "labels" })
        .addTo(roadLabelLayer);
    }
  });
}

function renderRoadList() {
  const container = document.getElementById("road-list-container");
  if (!container || !snowData || !snowData.road_conditions) return;
  const rc = snowData.road_conditions;
  const segments = rc.segments || [];
  const sum = document.getElementById("roads-summary");
  if (sum) {
    const active = segments.filter(s => !["R-0", "UNKNOWN", "NO FEED"].includes(s.status));
    const noFeed = segments.filter(s => s.status === "NO FEED").length;
    const fresh = rc.status !== "stale" && rc.is_live_feed;
    sum.innerHTML = `${fresh ? `Fetched ${new Date(rc.fetched_at_utc).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })} (${Fmt.ago(rc.fetched_at_utc)})` : `<span class="warn-text">Not current: last successful fetch ${Fmt.ago(rc.fetched_at_utc)}${rc.stale_reason ? ` (${rc.stale_reason})` : ""}</span>`}` +
      ` · ${active.length ? `${active.length} of ${segments.length - noFeed} corridors under controls` : `no chain controls on ${segments.length - noFeed} Caltrans corridors`}${noFeed ? ` · ${noFeed} Nevada road${noFeed > 1 ? "s" : ""} without a live feed` : ""} · server re-checks every 5 min`;
  }
  container.innerHTML = segments.map(seg => `
    <div class="road-card" onclick="focusRoadSegment('${seg.id}')">
      <span class="road-card-name">${window.routeShield ? routeShield(seg.route, 20) : ""}${seg.common_name || seg.name}</span>
      <span class="road-card-badge" style="background:${seg.status_color}22;color:${seg.status_color};border:1px solid ${seg.status_color}55;">${seg.status}</span>
      <span class="road-card-chk">${seg.status === "NO FEED" ? `No live feed · ${seg.feed_note || ""}` : seg.status === "R-0" ? seg.checkpoint : `${seg.status_label} · ${seg.checkpoint}`}</span>
    </div>`).join("");
}

window.focusRoadSegment = function(segId) {
  const layer = roadLayers[segId];
  if (layer && roadMap) {
    roadMap.fitBounds(layer.getBounds(), { padding: [50, 50], maxZoom: 12 });
    layer.openPopup();
  }
};

/* ==========================================================================
   MULTI-SOURCE BENCHMARK MATRIX & HAZARDS
   ========================================================================== */
function renderComparisonTable(resort) {
  const tableBody = document.getElementById("comparison-table-body");
  if (!tableBody) return;

  const s = resort.sources || {};
  const resortRpt = s.resort_official || {};
  const om = s.open_meteo || {};
  const nws = s.noaa_nws || {};
  const cdec = s.cdec_snotel || {};

  const na = `<span style="color:var(--ink-3)">n/a</span>`;
  const num = v => typeof v === "number" && !isNaN(v);
  const m = cdec.measurements || {};
  const ens = (om.summit || {}).ensemble || {};
  const rng = st => (st ? ` <span style="color:var(--ink-3)">(${U.snowBare(st.p10, 0)}–${U.snow(st.p90, 0)})</span>` : "");
  const resortVal = (v, label) => (num(v) ? `${U.snow(v)} ${label}` : na);
  const rows = [
    {
      metric: "Next 24h snowfall",
      resort: na,
      open_meteo: num((om.summit || {}).snow_24h_inches) ? `${U.snow(om.summit.snow_24h_inches)} summit${rng(ens.snow_24h)}` : na,
      nws: num(nws.forecast_24h_expected_inches) ? U.snow(nws.forecast_24h_expected_inches) : na,
      cdec: "forecast only"
    },
    {
      metric: "Next 48h snowfall",
      resort: na,
      open_meteo: num(om.summit_48h_inches) ? `${U.snow(om.summit_48h_inches)} summit${rng(ens.snow_48h)}` : na,
      nws: num(nws.forecast_48h_expected_inches) ? U.snow(nws.forecast_48h_expected_inches) : na,
      cdec: "forecast only"
    },
    {
      metric: "Last 24 / 48h (observed)",
      resort: `${resortVal(resortRpt.snow_24h_inches, "24h")} · ${resortVal(resortRpt.snow_48h_inches, "48h")}`,
      open_meteo: "forecast only",
      nws: "forecast only",
      cdec: num(m.snow_depth_24h_gain_inches) ? `+${U.snow(m.snow_depth_24h_gain_inches)} / +${U.snow(m.snow_depth_48h_gain_inches ?? 0)} depth · ${U.liquid(m.swe_48h_gain_inches ?? m.swe_24h_gain_inches)} water (48h)` : na
    },
    {
      metric: "Snowpack depth",
      resort: num(resortRpt.base_depth_base_inches) ? `${U.snow(resortRpt.base_depth_base_inches)} base · ${U.snow(resortRpt.base_depth_summit_inches)} summit` : na,
      open_meteo: "n/a",
      nws: "n/a",
      cdec: num(m.snow_depth_current_inches) ? `${U.snow(m.snow_depth_current_inches)} at ${(cdec.elevation_ft || 0).toLocaleString()}' · ${U.liquid(m.swe_current_inches)} SWE` : na
    },
    {
      metric: "Snow quality (snow ratio)",
      resort: resortRpt.surface_condition || na,
      open_meteo: (om.atmospheric_sounding || {}).dgz && om.atmospheric_sounding.dgz.avg_summit_slr ? `~${om.atmospheric_sounding.dgz.avg_summit_slr}:1 forecast (Kuchera)` : na,
      nws: "n/a",
      cdec: num(m.snow_to_liquid_ratio) ? `${m.snow_to_liquid_ratio}:1 measured · ${m.snow_density_classification}` : (m.snow_density_classification || na)
    },
    {
      metric: "Summit wind / temperature",
      resort: resortRpt.operations_note || na,
      open_meteo: num(om.peak_gust_summit_mph) ? `Peak gust ${Math.round(om.peak_gust_summit_mph)} mph (48h)` : na,
      nws: ((nws.active_hazards || [])[0] || {}).event || "No active hazards",
      cdec: num(m.air_temperature_f) ? `${U.temp(m.air_temperature_f)} now` : na
    }
  ];

  if (resortRpt.status !== "success") rows.forEach(r => { r.resort = `<span style="color:var(--ink-3)">Report unavailable</span>`; });
  tableBody.innerHTML = rows.map(r => `
    <tr>
      <td>${r.metric}</td>
      <td>${r.resort}</td>
      <td>${r.open_meteo}</td>
      <td>${r.nws}</td>
      <td>${r.cdec}</td>
    </tr>
  `).join("");
}

function renderHazards(resort) {
  const el = document.getElementById("active-hazards-container");
  if (!el) return;
  const hazards = (((resort.sources || {}).noaa_nws || {}).active_hazards) || [];
  const esc = t => String(t || "").replace(/[&<>]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  el.innerHTML = hazards.map(h => `
    <div class="hazard">
      <svg><use href="#i-alert"/></svg>
      <div>
        <b>${esc(h.event || h.headline)}</b>
        <p>${esc(h.headline && h.event ? h.headline : "")}</p>
        ${h.description ? `<details><summary>Details${h.instruction ? " & travel advice" : ""}</summary><p>${esc(h.description)}</p>${h.instruction ? `<p>${esc(h.instruction)}</p>` : ""}</details>` : ""}
      </div>
    </div>`).join("");
}

/* ==========================================================================
   LIFT STATUS MATRIX
   PULSES ONCE ON SCROLL DOWN, NO ANNOYING INFINITE BLINKING
   ========================================================================== */
function renderLiftsAndOperations(resort) {
  const grid = document.getElementById("lift-status-grid");
  if (!grid) return;
  const om = (resort.sources || {}).open_meteo || {};
  const rep = (resort.sources || {}).resort_official || {};
  const summitTl = ((om.elevation_timelines || {}).summit || []).slice(0, 24);
  const day = summitTl.filter(x => { const h = new Date(x.time).getHours(); return h >= 8 && h <= 16; });
  const peakRow = (day.length ? day : summitTl).reduce((m, x) => ((x.gust_mph || 0) > (m.gust_mph || 0) ? x : m), {});
  const peak = peakRow.gust_mph || 0;
  const exposedNames = ((resort.consensus_forecast || {}).wind_hold_risk || {}).affected_lifts || [];
  const isExposed = name => exposedNames.some(n => (name || "").toLowerCase().startsWith(n.toLowerCase()));
  const gustLevel = peak >= 65 ? "hold" : peak >= 45 ? "mod" : "open";
  const gustLabel = `forecast gust ${Math.round(peak)} mph`;
  const statusCls = st => { const s = (st || "").toLowerCase(); return s === "open" ? "open" : s === "scheduled" ? "sched" : s.includes("hold") ? "mod" : "closed"; };

  const lifts = (rep.lifts || []).slice();
  const sub = document.getElementById("lift-sub");
  if (lifts.length) {
    const order = { open: 0, sched: 1, mod: 2, closed: 3 };
    lifts.sort((a, b) => (isExposed(b.name) - isExposed(a.name)) || (order[statusCls(a.status)] - order[statusCls(b.status)]) || a.name.localeCompare(b.name));
    if (sub) sub.textContent = `Resort lift status${rep.status === "stale" ? " (stale)" : ""}: ${rep.lifts_open} of ${rep.lifts_total} open or scheduled; operations ${(rep.operating_status || "n/a").toLowerCase()}. ` +
      `Wind-exposed lifts also show the peak daytime (8 AM–4 PM) summit gust forecast for the next 24 h${peakRow.time ? ` (${new Date(peakRow.time).toLocaleString([], { weekday: "short", hour: "numeric" })})` : ""}: 45–64 mph intermittent holds possible, ≥ 65 mph holds likely.`;
    const card = l => {
      const exp = isExposed(l.name);
      return `<div class="lift-item"><div><b>${l.name}</b><small>${l.type || ""} · ${l.area || ""}</small></div>
        <div class="lift-tags"><span class="lift-status-tag st-${statusCls(l.status)}">${(l.status || "unknown").toLowerCase()}</span>
        ${exp ? `<span class="lift-status-tag tag-${gustLevel}" title="Wind-exposed lift">${gustLabel}</span>` : ""}</div></div>`;
    };
    // Priority lifts in the configured order (prefix match on the feed name), the rest behind an expander
    const pri = resort.priority_lifts || [];
    const used = new Set();
    const first = [];
    pri.forEach(p => {
      const hit = lifts.find(l => !used.has(l.name) && l.name.toLowerCase().startsWith(p.toLowerCase()));
      if (hit) { used.add(hit.name); first.push(hit); }
    });
    const rest = lifts.filter(l => !used.has(l.name));
    const openDetails = grid.querySelector("details.lift-more");
    const wasOpen = openDetails ? openDetails.open : false;
    grid.innerHTML = (first.length ? first : lifts).map(card).join("") +
      (first.length && rest.length ? `<details class="lift-more"${wasOpen ? " open" : ""}><summary>All other lifts (${rest.length}) · ${rest.filter(l => ["open", "sched"].includes(statusCls(l.status))).length} open or scheduled</summary>
        <div class="lift-grid lift-grid-inner">${rest.map(card).join("")}</div></details>` : "");
  } else {
    if (sub) sub.textContent = `Resort lift status unavailable. Peak daytime summit gust forecast, next 24 h: ${Math.round(peak)} mph (45–64 intermittent holds possible, ≥ 65 holds likely).`;
    grid.innerHTML = exposedNames.map(n => `<div class="lift-item"><div><b>${n}</b><small>wind-exposed</small></div><span class="lift-status-tag tag-${gustLevel}">${gustLabel}</span></div>`).join("");
  }
  setupOneTimeLiftScrollObserver();
}

function setupOneTimeLiftScrollObserver() {
  if (liftObserverSetup) return;
  const grid = document.getElementById("lift-status-grid");
  if (!grid || typeof IntersectionObserver === "undefined") return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        // Trigger subtle highlight pulse ONCE on entry
        const holdTags = grid.querySelectorAll(".tag-hold");
        holdTags.forEach(t => t.classList.add("pulse-once"));
        observer.disconnect(); // Never pulse again!
        liftObserverSetup = true;
      }
    });
  }, { threshold: 0.15 });

  observer.observe(grid);
}
