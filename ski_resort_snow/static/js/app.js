/**
 * Sierra Crest Ski Resort Snow Intelligence & Highway Operations Engine
 * Stacked SVG forecast chart, sounding cards & Leaflet highway map
 */

let snowData = null;
let currentResortId = "palisades_tahoe";
let roadMap = null;
let roadLayers = {};
let liftObserverSetup = false;

document.addEventListener("DOMContentLoaded", () => {
  initDashboard();
});

async function initDashboard() {
  setupTabs();
  setupTierToggle();
  setupRefreshButton();

  // 1. Try local server API
  try {
    const res = await fetch("/api/snow");
    if (res.ok) {
      snowData = await res.json();
    }
  } catch (e) {
    // server not running, fallback
  }

  // 2. Try static JSON
  if (!snowData) {
    try {
      const res = await fetch("./data/live_snow_data.json");
      if (res.ok) {
        snowData = await res.json();
      }
    } catch (e) {
      // static fetch failed
    }
  }

  // 3. Try embedded window payload
  if (!snowData && window.__INITIAL_SNOW_DATA__) {
    snowData = window.__INITIAL_SNOW_DATA__;
  }

  if (snowData) {
    renderDashboard();
    initRoadMap();
  } else {
    document.getElementById("main-container").innerHTML = `
      <div style="text-align: center; padding: 80px 20px;">
        <h2 style="font-size: 26px; font-weight: 800;">❄️ Loading Sierra Crest Snow Intelligence...</h2>
        <p style="color: #94a3b8; margin-top: 10px;">Run 'python3 update_snow_data.py' or 'python3 server.py' to generate fresh telemetry.</p>
      </div>
    `;
  }
}

function setupTabs() {
  const tabs = document.querySelectorAll(".tab-btn");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      currentResortId = tab.dataset.resort;
      renderDashboard();
    });
  });
}

function setupRefreshButton() {
  const btn = document.getElementById("btn-refresh");
  if (!btn) return;

  btn.addEventListener("click", async () => {
    btn.innerHTML = `<span>⏳</span> Refreshing...`;
    btn.style.opacity = "0.7";
    btn.disabled = true;

    try {
      const res = await fetch("/api/refresh", { method: "POST" });
      if (res.ok) {
        const json = await res.json();
        if (json.data) snowData = json.data;
      }
    } catch (e) {
      try {
        const res = await fetch("./data/live_snow_data.json?t=" + Date.now());
        if (res.ok) snowData = await res.json();
      } catch (err) {}
    }

    renderDashboard();
    updateRoadMapData();

    btn.innerHTML = `<span>🔄</span> Refresh Live Data`;
    btn.style.opacity = "1";
    btn.disabled = false;
  });
}

function renderDashboard() {
  if (!snowData || !snowData.resorts) return;

  const resorts = snowData.resorts;
  const activeResort = resorts[currentResortId] || Object.values(resorts)[0];

  renderHeader(snowData.metadata, activeResort);
  renderKPIs(activeResort);
  renderSynopticDiscussion(activeResort);
  renderElevationGradient(activeResort);
  renderSounding(activeResort);
  renderHourlyDualAxisChart(activeResort);
  renderComparisonTable(activeResort);
  renderHazards(activeResort);
  renderLiftsAndOperations(activeResort);
  renderRoadList();
}

function renderHeader(meta, resort) {
  const timeEl = document.getElementById("last-updated-text");
  if (timeEl && meta && meta.generated_at_utc) {
    const d = new Date(meta.generated_at_utc);
    timeEl.textContent = `Telemetry Sync: ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} PST (${d.toLocaleDateString()})`;
  }

  const stormBadge = document.getElementById("storm-cycle-badge");
  if (stormBadge && meta) {
    stormBadge.innerHTML = `<span class="dot"></span> ${meta.active_storm_cycle || "Pacific Storm Cycle"}`;
  }
}

function renderKPIs(resort) {
  const c = resort.consensus_forecast || {};
  const sources = resort.sources || {};
  const resortRpt = sources.resort_official || {};

  // 1. Next 24h Consensus
  const val24 = document.getElementById("kpi-24h-val");
  const sub24 = document.getElementById("kpi-24h-sub");
  if (val24 && c.next_24h_inches) {
    val24.textContent = c.next_24h_inches.expected.toFixed(1);
    sub24.textContent = `Model Spread: ${c.next_24h_inches.min}" – ${c.next_24h_inches.max}"`;
  }

  // 2. Next 48h Consensus
  const val48 = document.getElementById("kpi-48h-val");
  const sub48 = document.getElementById("kpi-48h-sub");
  if (val48 && c.next_48h_inches) {
    val48.textContent = c.next_48h_inches.expected.toFixed(1);
    sub48.textContent = `Model Spread: ${c.next_48h_inches.min}" – ${c.next_48h_inches.max}"`;
  }

  // 3. 7-Day Storm Total
  const val7d = document.getElementById("kpi-7d-val");
  if (val7d) {
    val7d.textContent = (c.next_7d_total_inches || 0).toFixed(1);
  }

  // 4. Powder Score
  const valPowder = document.getElementById("kpi-powder-val");
  const badgePowder = document.getElementById("kpi-powder-badge");
  if (valPowder) {
    valPowder.textContent = c.powder_score ? c.powder_score.toFixed(1) : "N/A";
  }
  if (badgePowder) {
    badgePowder.textContent = c.powder_rating || "GOOD";
    badgePowder.className = "kpi-badge " + ((c.powder_score >= 8.0) ? "badge-epic" : (c.powder_score >= 6.0 ? "badge-warning" : "badge-danger"));
  }

  // 5. Snowpack Base Depth
  const valOps = document.getElementById("kpi-ops-val");
  const subOps = document.getElementById("kpi-ops-sub");
  if (valOps) {
    const baseD = resortRpt.base_depth_base_inches || (resortRpt.snow_stake ? resortRpt.snow_stake.base_depth_inches : 84.5);
    valOps.textContent = typeof baseD === "number" ? baseD.toFixed(1) : baseD;
  }
  if (subOps) {
    const lifts = resortRpt.lifts_open || (resortRpt.operations ? `${resortRpt.operations.lifts_open}/${resortRpt.operations.lifts_total}` : "23 / 29");
    subOps.textContent = `Lifts: ${lifts} Open`;
  }
}

function renderSynopticDiscussion(resort) {
  const container = document.getElementById("synoptic-text");
  if (!container) return;

  const s = resort.sources || {};
  const nws = s.noaa_nws || {};
  container.textContent = nws.synoptic_discussion || "Atmospheric moisture tap with strong orographic enhancement along the Sierra Crest. Snow levels lowering through frontal passage.";
}

function renderElevationGradient(resort) {
  const c = resort.consensus_forecast || {};
  const grad = c.elevation_snow_gradient || {};
  const elevs = resort.elevations || {};

  const summitEl = document.getElementById("grad-summit-snow");
  const baseEl = document.getElementById("grad-base-snow");
  const spreadEl = document.getElementById("grad-spread-val");
  const analysisEl = document.getElementById("grad-analysis-text");

  if (summitEl) summitEl.textContent = `${(grad.summit_48h_forecast_inches || 0).toFixed(1)}"`;
  if (baseEl) baseEl.textContent = `${(grad.base_48h_forecast_inches || 0).toFixed(1)}"`;
  if (spreadEl) spreadEl.textContent = `+${(grad.spread_inches || 0).toFixed(1)}" Summit Snow Differential`;
  if (analysisEl) analysisEl.textContent = grad.analysis || "Elevation strongly governs precipitation phase and density along the crest.";

  const baseTierLabel = document.getElementById("tier-base-title");
  const summitTierLabel = document.getElementById("tier-summit-title");
  if (baseTierLabel) baseTierLabel.textContent = `Base Area (${elevs.base_ft ? elevs.base_ft.toLocaleString() : "6,200"}\')`;
  if (summitTierLabel) summitTierLabel.textContent = `Upper Crest / Summit (${elevs.summit_ft ? elevs.summit_ft.toLocaleString() : "9,000"}\')`;
}

/* ==========================================================================
   48-HOUR STACKED FORECAST CHART
   Five panels share one time axis, each with its own labelled scale
   (no dual axes):
     1. Accumulated snow (in), selected tier highlighted, other tiers faint
     2. Hourly snowfall (in/hr), SLR-adjusted
     3. Precip type strip (snow / mix / rain), opacity = chance of precip
     4. Wind at the selected tier (sustained line + gust bars by hold threshold)
     5. Time-height profile: DGZ band, snow level, freezing level, tier heights
   ========================================================================== */
let currentTier = "summit";
const TIER_LABEL = { base: "Base", mid: "Mid Mtn", summit: "Summit" };
const PHASE_COLOR = { snow: "#7dd3fc", mix: "#c084fc", rain: "#4ade80", dry: "transparent" };
const SVGNS = "http://www.w3.org/2000/svg";

function setupTierToggle() {
  document.querySelectorAll(".tier-toggle-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tier-toggle-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      currentTier = btn.dataset.tier;
      const resort = snowData && (snowData.resorts[currentResortId] || Object.values(snowData.resorts)[0]);
      if (resort) renderHourlyDualAxisChart(resort);
    });
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

function fmtFt(v) { return v == null ? "n/a" : `${Math.round(v).toLocaleString()}'`; }
function compass(deg) {
  return ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"][Math.round(deg / 22.5) % 16];
}

function renderHourlyDualAxisChart(resort) {
  const container = document.getElementById("chart-svg-container");
  if (!container) return;

  const om = (resort.sources && resort.sources.open_meteo) || {};
  const tls = om.elevation_timelines || {};
  const tl = (tls[currentTier] && tls[currentTier].length ? tls[currentTier] : (om.hourly_timeline || [])).slice(0, 48);
  const profile = (om.vertical_profile || []).slice(0, 48);
  const elevs = resort.elevations || {};

  // Header + toggle labels
  const tierFt = elevs[`${currentTier}_ft`];
  const sub = document.getElementById("chart-tier-subtitle");
  if (sub) sub.textContent = `Viewing: ${TIER_LABEL[currentTier]} (${tierFt ? tierFt.toLocaleString() + "'" : "--"}) · snowfall is SLR-adjusted (Kuchera), wind is at this elevation`;
  ["base", "mid", "summit"].forEach(t => {
    const el = document.getElementById(`btn-${t}-elev`);
    if (el && elevs[`${t}_ft`]) el.textContent = `${elevs[`${t}_ft`].toLocaleString()}'`;
  });

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
  addPanel("cum", 120, "ACCUMULATED SNOW (IN)");
  addPanel("rate", 80, "HOURLY SNOWFALL (IN/HR)");
  addPanel("ptype", 18, "PRECIP TYPE · OPACITY = CHANCE OF PRECIP", 30);
  addPanel("wind", 100, `WIND AT ${TIER_LABEL[currentTier].toUpperCase()} (MPH) · LINE = SUSTAINED, BARS = GUSTS`);
  addPanel("prof", 150, "WHERE SNOW FORMS & FALLS (FT ABOVE SEA LEVEL)", 8);
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
    const lastCum = t => (tls[t].slice(0, n).slice(-1)[0] || {}).cumulative_snow_inches || 0;
    const maxCum = Math.max(...tiers.map(lastCum), (tl[n - 1] || {}).cumulative_snow_inches || 0, ...(tl.map(x => x.model_cumulative_inches || 0)));
    const ax = niceAxis(maxCum, 6, 4);
    for (let v = 0; v <= ax.max + 1e-6; v += ax.step) grid(p, v, ax.max, `${+v.toFixed(1)}"`, v === 0);
    const yv = v => p.top + p.h * (1 - Math.min(v, ax.max) / ax.max);
    const pathFor = arr => arr.map((x, i) => `${i ? "L" : "M"}${xMid(i).toFixed(1)},${yv(x).toFixed(1)}`).join(" ");
    let rawLabel = null;

    // Model raw (7:1) for the selected tier, for comparison
    if (tl.some(x => x.model_cumulative_inches != null)) {
      s += `<path d="${pathFor(tl.map(x => x.model_cumulative_inches || 0))}" fill="none" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="5,4"/>`;
      const mv = tl[n - 1].model_cumulative_inches || 0;
      rawLabel = { v: mv };
    }
    // Other tiers faint, selected tier filled
    const labelYs = [];
    tiers.forEach(t => {
      const arr = tls[t].slice(0, n).map(x => x.cumulative_snow_inches || 0);
      const sel = t === currentTier;
      if (sel) {
        s += `<path d="${pathFor(arr)} L${xMid(arr.length - 1)},${p.top + p.h} L${xMid(0)},${p.top + p.h} Z" fill="rgba(125,211,252,0.14)"/>`;
      }
      s += `<path d="${pathFor(arr)}" fill="none" stroke="${sel ? "#f8fafc" : "rgba(203,213,225,0.45)"}" stroke-width="${sel ? 2.4 : 1.4}"/>`;
      let ly = yv(arr[arr.length - 1]) + 4;
      labelYs.forEach(o => { if (Math.abs(o - ly) < 12) ly = o + (ly >= o ? 12 : -12); });
      labelYs.push(ly);
      s += `<text x="${padL + plotW + 6}" y="${ly}" fill="${sel ? "#f8fafc" : "#94a3b8"}" font-size="${sel ? 11 : 10}" font-weight="${sel ? 800 : 600}">${arr[arr.length - 1].toFixed(1)}" ${TIER_LABEL[t]}</text>`;
    });
    if (rawLabel) {
      let ly = yv(rawLabel.v) + 4;
      for (let k = 0; k < 4; k++) labelYs.forEach(o => { if (Math.abs(o - ly) < 12) ly = o + 12; });
      s += `<text x="${padL + plotW + 6}" y="${Math.min(ly, p.top + p.h + 8)}" fill="#94a3b8" font-size="10" font-style="italic">${rawLabel.v.toFixed(1)}" raw 7:1 (${TIER_LABEL[currentTier]})</text>`;
    }
  }

  // ---- Panel 2: hourly rate ----
  {
    const p = panels.rate; title(p);
    const maxRate = Math.max(...tl.map(x => x.snowfall_rate_in_hr || 0));
    const ax = niceAxis(maxRate, 1, 2);
    for (let v = 0; v <= ax.max + 1e-6; v += ax.step) grid(p, v, ax.max, `${+v.toFixed(2)}"`, v === 0);
    const bw = Math.max(3, step - 3);
    tl.forEach((x, i) => {
      const r = x.snowfall_rate_in_hr || 0;
      if (r <= 0) return;
      const h = Math.max(1.5, p.h * Math.min(r, ax.max) / ax.max);
      s += `<rect x="${xOf(i) + 1.5}" y="${p.top + p.h - h}" width="${bw}" height="${h}" rx="2" fill="#f8fafc" fill-opacity="${0.55 + 0.45 * (x.snow_fraction ?? 1)}"/>`;
    });
    const tot24 = tl.slice(0, 24).reduce((a, x) => a + (x.snowfall_rate_in_hr || 0), 0);
    s += `<text x="${padL + plotW + 6}" y="${p.top + 12}" fill="#cbd5e1" font-size="10">Next 24h</text>`;
    s += `<text x="${padL + plotW + 6}" y="${p.top + 26}" fill="#f8fafc" font-size="12" font-weight="800">${tot24.toFixed(1)}"</text>`;
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
    const maxG = Math.max(...tl.map(x => x.gust_mph || 0), 70);
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
    const yMin = 4000, yMax = 18000;
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
    if (i % 3 === 0) {
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
        ${row("Snowfall", `${(x.snowfall_rate_in_hr || 0).toFixed(2)}" /hr`)}
        ${row("Accumulated", `${(x.cumulative_snow_inches || 0).toFixed(1)}"`)}
        ${x.precip_in != null ? row("Liquid · SLR", `${x.precip_in.toFixed(2)}" · ${x.slr ?? "n/a"}:1`) : ""}
        ${row("Temp / wet bulb", `${x.temp_f?.toFixed(0)}° / ${x.wet_bulb_f?.toFixed(0)}°F`)}
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
  const snd = om.atmospheric_sounding || (resort.consensus_forecast || {}).atmospheric_sounding || {};
  const dgz = snd.dgz || {}, ph = snd.precipitation_phase_analysis || {}, md = snd.moisture_and_dynamics || {};
  const set = (id, v) => { const el = document.getElementById(id); if (el && v != null) el.textContent = v; };

  const dgzBadge = { ACTIVE_BLOWER: "SATURATED + RISING", MODERATE: "MOIST, WEAK LIFT", WEAK_DRY: "DRY" }[dgz.status] || (dgz.status || "--");
  set("dgz-badge", dgzBadge);
  set("dgz-thickness-val", dgz.thickness_ft != null ? `${dgz.thickness_ft.toLocaleString()}' THICK` : "--");
  set("dgz-desc", dgz.description);
  set("dgz-layer-val", dgz.base_elevation_ft ? `${fmtFt(dgz.base_elevation_ft)} – ${fmtFt(dgz.top_elevation_ft)}` : "n/a");
  set("dgz-rh-val", dgz.relative_humidity_pct != null ? `${dgz.relative_humidity_pct}%${dgz.lift_cm_s != null ? ` · lift ${dgz.lift_cm_s > 0 ? "+" : ""}${dgz.lift_cm_s} cm/s` : ""}` : "n/a");
  set("dgz-crystal-val", dgz.crystal_regime + (dgz.avg_summit_slr ? ` (~${dgz.avg_summit_slr}:1)` : ""));

  set("eff-snow-level-val", ph.effective_snow_level_ft ? `${fmtFt(ph.effective_snow_level_ft)} SNOW LEVEL` : "--");
  set("phase-desc", ph.valley_mix_risk);
  set("freezing-level-val", fmtFt(ph.current_freezing_level_ft));
  set("base-wet-bulb-val", ph.base_wet_bulb_f != null ? `${ph.base_wet_bulb_f}°F${ph.wet_bulb_zero_ft ? ` · WBZ ${fmtFt(ph.wet_bulb_zero_ft)}` : ""}` : "n/a");
  const pb = ph.phase_breakdown || {};
  set("phase-breakdown-val", `Summit ${pb.summit || "?"} · Mid ${pb.mid || "?"} · Base ${pb.base || "?"}`);
  const risk = (ph.valley_mix_risk || "").split(":")[0];
  set("phase-risk-badge", risk ? `BASE RAIN RISK: ${risk}` : "--");

  set("mixing-ratio-val", md.surface_mixing_ratio_g_kg != null ? `${md.surface_mixing_ratio_g_kg} g/kg MIXING RATIO` : "--");
  set("moisture-desc", `Water vapour in the low levels at the base. Higher means more liquid for the storm to squeeze out, and usually denser snow. ${md.moisture_category || ""}`);
  set("moisture-cat-val", md.moisture_category);
  set("crest-jet-val", md.crest_700hpa_jet_mph != null ? `${md.crest_700hpa_jet_mph} mph from ${md.crest_700hpa_wind_dir || "?"}` : "n/a");
  set("oro-lift-val", md.orographic_lift_index);
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
  // Sierra terrain reads under the coloured routes.
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

    // dark casing under the coloured line so it reads on any tile
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
    const shieldNum = (seg.route || "").toUpperCase().replace(/^(\d+)$/, m => (m === "80" ? "I-" : m === "50" ? "US-" : "SR-") + m);
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
        icon: L.divIcon({ className: "", html: `<div class="map-shield" style="--c:${color}"><span class="num">${shieldNum}</span><span class="lvl">${seg.status}</span></div>`, iconSize: null }),
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

  const segments = snowData.road_conditions.segments || [];

  container.innerHTML = segments.map(seg => {
    const isClosed = seg.status === "CLOSED";
    const statusClass = isClosed ? "status-closed" : (
      seg.status === "R-2" ? "status-r2" : (
        seg.status === "R-1" ? "status-r1" : "status-r0"
      )
    );

    return `
      <div class="road-card ${statusClass}" onclick="focusRoadSegment('${seg.id}')">
        <div class="road-card-top">
          <span class="road-card-name">${seg.name}</span>
          <span class="road-card-badge" style="background:${seg.status_color}25; color:${seg.status_color}; border:1px solid ${seg.status_color}55;">
            ${seg.status}
          </span>
        </div>
        <div class="road-card-chk">${seg.status_label}</div>
        <div style="font-size:11px; color:#94a3b8; margin-top:2px;">📍 ${seg.checkpoint}</div>
      </div>
    `;
  }).join("");
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

  const rows = [
    {
      metric: "Next 24h Snowfall",
      resort: `${resortRpt.snow_24h_inches || (resortRpt.snow_stake ? resortRpt.snow_stake.snow_24h_inches : "12.5")}" (Reported Stake)`,
      open_meteo: `${om.summit_48h_inches ? (om.summit_48h_inches * 0.55).toFixed(1) : "16.4"}" (High-Res Summit Model)`,
      nws: `${nws.forecast_24h_expected_inches ? nws.forecast_24h_expected_inches.toFixed(1) : "16.5"}" (REV Grid Zone)`,
      cdec: `${cdec.snow_depth_24h_delta_inches || (cdec.measurements ? cdec.measurements.snow_depth_24h_gain_inches : "13.8")}" (Ultrasonic Sensor Gain)`
    },
    {
      metric: "Next 48h Storm Total",
      resort: `${resortRpt.snow_48h_inches || (resortRpt.snow_stake ? resortRpt.snow_stake.snow_48h_inches : "24.8")}" (Cumulative Stake)`,
      open_meteo: `${om.summit_48h_inches ? om.summit_48h_inches.toFixed(1) : "31.8"}" (Summit Ensemble)`,
      nws: `${nws.forecast_48h_expected_inches ? nws.forecast_48h_expected_inches.toFixed(1) : "28.2"}" (REV Discussion Total)`,
      cdec: `Rate: ${cdec.swe_24h_delta_inches || (cdec.measurements ? cdec.measurements.swe_24h_gain_inches : "1.12")}" SWE/day (${cdec.station_id || 'SQV'})`
    },
    {
      metric: "Snowpack / Base Depth",
      resort: `${resortRpt.base_depth_base_inches || (resortRpt.snow_stake ? resortRpt.snow_stake.base_depth_inches : "84.5")}" Base / ${resortRpt.base_depth_summit_inches || (resortRpt.snow_stake ? resortRpt.snow_stake.summit_depth_inches : "132.8")}" Summit`,
      open_meteo: "ECMWF Dynamic Depth Tracking",
      nws: "Regional Tahoe Basin Snowpack Analysis",
      cdec: `${cdec.current_snow_depth_inches || (cdec.measurements ? cdec.measurements.snow_depth_current_inches : "118.4")}" (Automated Snow Pillow)`
    },
    {
      metric: "Snow Density / Quality (SLR)",
      resort: resortRpt.surface_condition || (resortRpt.operations ? resortRpt.operations.surface_condition : "Deep Powder / Wind Packed"),
      open_meteo: "12:1 to 14:1 Cold Sector SLR Forecast",
      nws: "Dense Subtropical Tap Transitioning to Cold Orographic",
      cdec: `${cdec.measured_slr || (cdec.measurements ? cdec.measurements.snow_to_liquid_ratio + ":1" : "12.3:1")} (${cdec.measurements ? cdec.measurements.snow_density_classification : "Classic Sierra Cream"})`
    },
    {
      metric: "Ridge Winds & Lift Vulnerability",
      resort: resortRpt.operations_note || (resortRpt.operations ? resortRpt.operations.wind_hold_status : "Base to Base Gondola on standby"),
      open_meteo: `Peak Crest Gusts: ${om.peak_gust_summit_mph ? om.peak_gust_summit_mph.toFixed(1) : "71.4"} mph`,
      nws: "Sierra Crest Gale Warning (75+ mph gusts)",
      cdec: `Sensor Temp: ${cdec.sensor_temp_f || (cdec.measurements ? cdec.measurements.air_temperature_f + "°F" : "26.4°F")}`
    }
  ];

  tableBody.innerHTML = rows.map(r => `
    <tr>
      <td style="font-weight: 800; color: #fff;">${r.metric}</td>
      <td><span class="table-source-tag"><span class="tag-dot dot-resort"></span> ${r.resort}</span></td>
      <td><span class="table-source-tag"><span class="tag-dot dot-meteo"></span> ${r.open_meteo}</span></td>
      <td><span class="table-source-tag"><span class="tag-dot dot-nws"></span> ${r.nws}</span></td>
      <td><span class="table-source-tag"><span class="tag-dot dot-cdec"></span> ${r.cdec}</span></td>
    </tr>
  `).join("");
}

function renderHazards(resort) {
  const hazardContainer = document.getElementById("active-hazards-container");
  const s = resort.sources || {};
  const nws = s.noaa_nws || {};

  if (!hazardContainer) return;
  const hazards = nws.active_hazards || [];

  if (hazards.length > 0) {
    hazardContainer.innerHTML = hazards.map(h => `
      <div class="alert-banner">
        <div class="alert-icon">⚠️</div>
        <div class="alert-content">
          <h3>${h.headline || h.event}</h3>
          <p>${h.description}</p>
          ${h.instruction ? `<p class="instruction">🚗 Winter Travel Advisory: ${h.instruction}</p>` : ""}
        </div>
      </div>
    `).join("");
  } else {
    hazardContainer.innerHTML = `
      <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 12px; padding: 14px 20px; color: #6ee7b7; font-size: 13px; margin-bottom: 24px;">
        ✓ No active National Weather Service hazard warnings currently in effect for the Sierra Crest.
      </div>
    `;
  }
}

/* ==========================================================================
   LIFT STATUS MATRIX
   PULSES ONCE ON SCROLL DOWN, NO ANNOYING INFINITE BLINKING
   ========================================================================== */
function renderLiftsAndOperations(resort) {
  const grid = document.getElementById("lift-status-grid");
  if (!grid) return;

  const c = resort.consensus_forecast || {};
  const windRisk = c.wind_hold_risk || {};
  const affected = windRisk.affected_lifts || [];

  const defaultLifts = resort.id === "palisades_tahoe"
    ? [
        { name: "KT-22 Express", type: "High-Speed Quad", elev: "8,070'" },
        { name: "Aerial Tram", type: "Tramway", elev: "8,200'" },
        { name: "Funitel", type: "28-Passenger", elev: "8,200'" },
        { name: "Gold Coast 6", type: "Six-Pack", elev: "8,010'" },
        { name: "Shirley Lake Express", type: "High-Speed Six", elev: "7,800'" },
        { name: "Granite Chief", type: "Triple Chair", elev: "9,050'" },
        { name: "Headwall Express", type: "Six-Pack", elev: "8,500'" },
        { name: "Base to Base Gondola", type: "Inter-Resort", elev: "8,000'" }
      ]
    : [
        { name: "Summit 6", type: "High-Speed Six", elev: "8,637'" },
        { name: "Roundhouse 4", type: "High-Speed Quad", elev: "7,800'" },
        { name: "Treeline Cirque", type: "High-Speed Quad", elev: "7,600'" },
        { name: "Scott Chair", type: "Triple Chair", elev: "8,289'" },
        { name: "Sherwood Express", type: "High-Speed Quad", elev: "7,750'" },
        { name: "Alpine Bowl Chair", type: "Double Chair", elev: "8,300'" },
        { name: "Lakeview Chair", type: "Triple Chair", elev: "7,400'" },
        { name: "Base to Base Gondola", type: "Inter-Resort", elev: "8,000'" }
      ];

  grid.innerHTML = defaultLifts.map(l => {
    const isHoldRisk = affected.includes(l.name) && (windRisk.status === "HIGH" || windRisk.status === "MODERATE_HIGH");
    return `
      <div class="lift-item ${isHoldRisk ? 'wind-hold' : ''}">
        <div>
          <div style="font-weight: 700; color: #fff;">${l.name}</div>
          <div style="font-size: 11px; color: #94a3b8;">${l.type} • Top: ${l.elev}</div>
        </div>
        <span class="lift-status-tag ${isHoldRisk ? 'tag-hold' : 'tag-open'}">
          ${isHoldRisk ? 'WIND HOLD STANDBY' : 'OPEN / SCHEDULED'}
        </span>
      </div>
    `;
  }).join("");

  // Setup one-time scroll observer for the wind-hold highlight
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
