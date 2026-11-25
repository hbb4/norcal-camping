/**
 * Sierra Snow: analysis panels
 *  - Skew-T log-P (model sounding at the selected hour, or observed REV/OAK radiosonde)
 *  - Ice-crystal habit diagram (temperature vs. ice supersaturation) with model levels
 *  - Precipitation type by elevation (vertical) + T / Tw / T-Td table per tier
 *  - Supercooled liquid water above the summit (HRRR or RRFS native fields): time-height chart and column total
 *  - Route shields (Interstate, US, California)
 *  - Sources & verification tables
 */
(() => {
  const $ = id => document.getElementById(id);
  const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const FT = 3.28084;
  const state = { resort: null, hour: 0, skewSrc: "model", slwModel: "hrrr" };
  try { if (localStorage.getItem("slwModel") === "rrfs") state.slwModel = "rrfs"; } catch (e) { /* no storage: HRRR */ }

  // ---------------------------------------------------------------- thermo
  const esW = t => 6.112 * Math.exp(17.67 * t / (t + 243.5));
  const esI = t => 6.112 * Math.exp(22.46 * t / (t + 272.62));
  const rhFrom = (t, td) => Math.min(100, 100 * esW(td) / esW(t));
  const rhIce = (t, td) => (t >= 0 ? rhFrom(t, td) : 100 * esW(td) / esI(t));
  // Psychrometric wet bulb (bisection); valid at any temperature, needs pressure.
  function wetBulbP(t, td, p) {
    if (td >= t) return t;
    const e = esW(td);
    let lo = td, hi = t;
    for (let i = 0; i < 40; i++) {
      const mid = (lo + hi) / 2;
      const f = esW(mid) - 0.00066 * p * (1 + 0.00115 * mid) * (t - mid) - e;
      if (f > 0) hi = mid; else lo = mid;
    }
    return (lo + hi) / 2;
  }
  const fmtFt = v => (v == null ? "n/a" : `${Math.round(v).toLocaleString()} ft`);
  const tC = c => (c == null ? "--" : U.celsius() ? `${c.toFixed(1)} °C` : `${(c * 9 / 5 + 32).toFixed(0)} °F`);
  const tF = f => (f == null ? "--" : U.temp(f));
  const dDiff = f => (f == null ? "--" : U.celsius() ? `${(f * 5 / 9).toFixed(1)}°C` : `${f.toFixed(0)}°F`);
  const pst = iso => (iso ? new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "n/a");
  const utc = iso => (iso ? `${iso.slice(5, 10).replace("-", "/")} ${iso.slice(11, 13)}Z` : "n/a");
  const ago = iso => {
    if (!iso) return "never";
    const m = Math.round((Date.now() - new Date(iso)) / 60000);
    return m < 1 ? "just now" : m < 90 ? `${m} min ago` : m < 48 * 60 ? `${Math.round(m / 60)} h ago` : `${Math.round(m / 1440)} d ago`;
  };
  window.Fmt = { ago, pst, utc };

  // ---------------------------------------------------------------- route shields
  // Shapes follow the MUTCD / Caltrans designs: Interstate (M1-1) red-and-blue shield with a
  // concave top; US Route (M1-4) white shield on a black square; California State Route
  // green "miner's spade" with a flat top. Legend text appears only at sizes where it can render.
  function routeShield(route, size = 22) {
    const r = String(route || "").toUpperCase();
    const num = (r.match(/\d+/) || [""])[0];
    if (!num) return "";
    const big = size >= 24;
    const fs = num.length >= 3 ? 8 : 10;
    const font = `font-family="Inter, Arial, sans-serif" font-weight="800" text-anchor="middle"`;
    const h = Math.round(size * 26 / 24);
    if (r === "80" || r.startsWith("I")) {
      const outer = "M1.2,1.6 Q12,5.6 22.8,1.6 C23.7,7 23.7,13.5 20.6,18.2 Q17.6,22.6 12,25 Q6.4,22.6 3.4,18.2 C0.3,13.5 0.3,7 1.2,1.6 Z";
      const inner = "M2.3,2.9 Q12,6.7 21.7,2.9 C22.4,7.6 22.4,13.3 19.7,17.5 Q16.9,21.4 12,23.6 Q7.1,21.4 4.3,17.5 C1.6,13.3 1.6,7.6 2.3,2.9 Z";
      const id = `ish${Math.random().toString(36).slice(2, 8)}`;
      return `<svg class="shield" width="${size}" height="${h}" viewBox="0 0 24 26" aria-label="Interstate ${num}" role="img">
        <defs><clipPath id="${id}"><path d="${inner}"/></clipPath></defs>
        <path d="${outer}" fill="#fff"/>
        <g clip-path="url(#${id})"><rect x="0" y="0" width="24" height="26" fill="#003f87"/><rect x="0" y="0" width="24" height="8.6" fill="#af1e2d"/></g>
        <path d="M1.5,8.6 H22.5" stroke="#fff" stroke-width="0.9"/>
        ${big ? `<text x="12" y="7.3" font-size="2.7" fill="#fff" ${font} letter-spacing=".15">INTERSTATE</text>` : ""}
        <text x="12" y="${num.length >= 3 ? 18 : 18.6}" font-size="${fs}" fill="#fff" ${font}>${num}</text></svg>`;
    }
    if (r === "50" || r.startsWith("US")) {
      return `<svg class="shield" width="${size}" height="${size}" viewBox="0 0 24 24" aria-label="U.S. Route ${num}" role="img">
        <rect x="0" y="0" width="24" height="24" rx="2" fill="#111"/>
        <path d="M3.6,2.2 H20.4 Q21.8,2.2 21.8,4.2 Q21.8,6.4 20.9,7.8 Q22.2,10 21.9,13.2 Q21.4,19.4 12,22.3 Q2.6,19.4 2.1,13.2 Q1.8,10 3.1,7.8 Q2.2,6.4 2.2,4.2 Q2.2,2.2 3.6,2.2 Z" fill="#fff"/>
        <text x="12" y="${num.length >= 3 ? 15.4 : 16}" font-size="${num.length >= 3 ? 8.5 : 10.5}" fill="#111" ${font}>${num}</text></svg>`;
    }
    if (r.startsWith("NV")) {
      // Nevada State Route: white outline of the state on a black square, black numerals
      const nv = [[0, 0], [1, 0], [1, 0.843], [0.88, 0.857], [0.899, 1], [0, 0.429]];
      const hgt = 20.4, wid = hgt * 0.66, x0 = (24 - wid) / 2, y0 = 1.8;
      const pts = nv.map(([x, y]) => `${(x0 + x * wid).toFixed(2)},${(y0 + y * hgt).toFixed(2)}`).join(" ");
      return `<svg class="shield" width="${size}" height="${size}" viewBox="0 0 24 24" aria-label="Nevada State Route ${num}" role="img">
        <rect x="0" y="0" width="24" height="24" rx="2" fill="#111"/>
        <polygon points="${pts}" fill="#fff" stroke="#fff" stroke-width="0.6" stroke-linejoin="round"/>
        <text x="${(x0 + wid * 0.5).toFixed(2)}" y="9.6" font-size="${num.length >= 3 ? 6.4 : 8}" fill="#111" ${font}>${num}</text></svg>`;
    }
    // California State Route: green spade, white border, CALIFORNIA across the top
    return `<svg class="shield" width="${size}" height="${h}" viewBox="0 0 24 26" aria-label="California State Route ${num}" role="img">
      <path d="M2.6,1.2 H21.4 Q23,1.2 23,2.9 V8.6 C23,15.3 17.7,21.3 12,25.2 C6.3,21.3 1,15.3 1,8.6 V2.9 Q1,1.2 2.6,1.2 Z" fill="#fff"/>
      <path d="M3.3,2.4 H20.7 Q21.8,2.4 21.8,3.5 V8.7 C21.8,14.7 16.9,20.1 12,23.7 C7.1,20.1 2.2,14.7 2.2,8.7 V3.5 Q2.2,2.4 3.3,2.4 Z" fill="#00703c"/>
      ${big ? `<text x="12" y="6.3" font-size="2.6" fill="#fff" ${font} letter-spacing=".1">CALIFORNIA</text>` : ""}
      <text x="12" y="${num.length >= 3 ? 16.6 : 17.2}" font-size="${fs}" fill="#fff" ${font}>${num}</text></svg>`;
  }
  window.routeShield = routeShield;

  // ---------------------------------------------------------------- data access
  function om() { return ((state.resort || {}).sources || {}).open_meteo || {}; }
  function modelLevels(h) {
    const sh = om().sounding_hourly || [];
    const rec = sh[Math.min(h, sh.length - 1)];
    return rec ? { time: rec.time, levels: rec.levels, ground_m: rec.ground_m } : null;
  }
  function observed(st) { return (((typeof snowData !== "undefined" && snowData) || {}).observed_soundings || {})[st] || null; }
  function pressureAtHeight(levels, zM) {
    const pts = levels.filter(l => l[1] != null).map(l => [l[1], Math.log(l[0])]).sort((a, b) => a[0] - b[0]);
    for (let i = 0; i < pts.length - 1; i++) {
      if (zM >= pts[i][0] && zM <= pts[i + 1][0]) {
        const f = (zM - pts[i][0]) / (pts[i + 1][0] - pts[i][0]);
        return Math.exp(pts[i][1] + f * (pts[i + 1][1] - pts[i][1]));
      }
    }
    return null;
  }

  // ---------------------------------------------------------------- skew-T
  function renderSkewT() {
    const box = $("skewt");
    if (!box || !state.resort) return;
    const src = state.skewSrc;
    let levels, title, groundP = null, hasW = false;
    const elevs = state.resort.elevations || {};
    if (src === "model") {
      const m = modelLevels(state.hour);
      if (!m) { box.innerHTML = `<p class="mini-label" style="padding:20px">${esc(((om().atmospheric_sounding || {}).reason) || "No model sounding available.")} The observed Reno sounding is still available above.</p>`; $("skewt-sub").textContent = ""; return; }
      levels = m.levels; hasW = true;
      const q = (om().query_points || {}).summit || {};
      const pm = om().profile_model;
      title = `Model: ${pm ? `${pm.label} column (${(om().model || {}).label} has no vertical profile)` : ((om().primary_model || {}).label || "primary model")} at ${q.lat?.toFixed(3)}, ${q.lon?.toFixed(3)} · valid ${new Date(m.time).toLocaleString([], { weekday: "short", hour: "numeric" })} (${utc(m.time)}). Levels below the base are shaded (model extrapolation below terrain).`;
      groundP = pressureAtHeight(levels, (elevs.base_ft || 6200) / FT);
    } else {
      const o = observed(src);
      if (!o || !o.levels) { box.innerHTML = `<p class="mini-label">${esc(src)} sounding unavailable${o && o.error_message ? `: ${esc(o.error_message)}` : ""}.</p>`; return; }
      levels = o.levels;
      title = `Observed: ${esc(o.name)} radiosonde, ${utc(o.valid_utc)} (${pst(o.valid_utc)} local) · ${esc(o.position)} · station elevation ${Math.round(o.elevation_m * FT).toLocaleString()} ft · ${o.status === "stale" ? "stale, " : ""}fetched ${ago(o.fetched_at_utc)}`;
      groundP = levels[0] ? levels[0][0] : null;
    }
    $("skewt-sub").textContent = title;
    // init and valid time, prominently
    const RUN_NAMES = { ncep_hrrr_conus: "HRRR", ncep_gfs025: "GFS", ncep_gfs013: "GFS", ecmwf_ifs: "ECMWF IFS", ecmwf_ifs025: "ECMWF IFS 0.25°",
      ecmwf_aifs025_single: "ECMWF AIFS", dwd_icon: "ICON", ukmo_global_deterministic_10km: "UKMO", cmc_gem_gdps: "GEM", cmc_gem_rdps: "GEM regional" };
    const tEl = $("skewt-times");
    if (tEl) {
      const fmtLocal = d => d.toLocaleString([], { weekday: "short", month: "numeric", day: "numeric", hour: "numeric" });
      const fmtUtc = d => `${String(d.getUTCMonth() + 1).padStart(2, "0")}/${String(d.getUTCDate()).padStart(2, "0")} ${String(d.getUTCHours()).padStart(2, "0")}Z`;
      if (src === "model") {
        const o = om(), valid = new Date(modelLevels(state.hour).time);
        const runs = ((o.profile_model && o.profile_model.runs) || o.column_runs || (o.model || {}).runs || []).filter(r => r.run_init_utc);
        let r = runs[0];
        if (runs.length > 1 && r && (valid - new Date(r.run_init_utc)) / 3600e3 > 47) r = runs[1];   // HRRR hands over to GFS after ~47 h
        const init = r ? new Date(r.run_init_utc) : null;
        tEl.innerHTML = `<span><small>Init</small>${init ? `${fmtUtc(init)} <em>${esc(RUN_NAMES[r.model] || r.model || "")}</em>` : "n/a"}</span>
          <span><small>Valid</small>${fmtLocal(valid)} <em>${fmtUtc(valid)}</em></span>
          ${init ? `<span><small>Forecast hour</small>+${Math.round((valid - init) / 3600e3)} h</span>` : ""}`;
      } else {
        const o = observed(src), v = new Date(o.valid_utc);
        tEl.innerHTML = `<span><small>Observed</small>${esc(o.name || src)} radiosonde</span><span><small>Valid</small>${fmtLocal(v)} <em>${fmtUtc(v)}</em></span>`;
      }
    }

    const W = 760, H = 580, L = 52, R = 92, T = 32, B = 30, PW = W - L - R, PH = H - T - B;
    const pTop = 200, pBot = 1050, Tmin = -40, Tmax = 40;
    const sx = PW / (Tmax - Tmin), skew = 1.0;
    const Y = p => T + PH * (Math.log(p) - Math.log(pTop)) / (Math.log(pBot) - Math.log(pTop));
    const X = (t, p) => L + (t - Tmin) * sx + (T + PH - Y(p)) * skew;
    const pAt = y => Math.exp(Math.log(pTop) + (y - T) / PH * (Math.log(pBot) - Math.log(pTop)));
    let s = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" font-family="var(--font-sans)">
      <defs><clipPath id="skclip"><rect x="${L}" y="${T}" width="${PW}" height="${PH}"/></clipPath></defs>
      <rect x="${L}" y="${T}" width="${PW}" height="${PH}" fill="rgba(255,255,255,0.015)" stroke="rgba(255,255,255,0.12)"/>
      <g clip-path="url(#skclip)">`;
    // DGZ band
    const band = (t1, t2) => `${X(t1, pBot)},${Y(pBot)} ${X(t1, pTop)},${Y(pTop)} ${X(t2, pTop)},${Y(pTop)} ${X(t2, pBot)},${Y(pBot)}`;
    s += `<polygon points="${band(-12, -18)}" fill="rgba(125,211,252,0.13)"/>`;
    // below-ground shading
    if (groundP) s += `<rect x="${L}" y="${Y(groundP)}" width="${PW}" height="${T + PH - Y(groundP)}" fill="rgba(148,163,184,0.12)"/>`;
    // isobars
    [1000, 900, 850, 800, 700, 600, 500, 400, 300, 250, 200].forEach(p => {
      s += `<line x1="${L}" x2="${L + PW}" y1="${Y(p)}" y2="${Y(p)}" stroke="rgba(255,255,255,${[1000, 850, 700, 500, 300].includes(p) ? 0.12 : 0.05})"/>`;
    });
    // isotherms
    for (let t = -100; t <= 40; t += 10) {
      const zero = t === 0;
      s += `<line x1="${X(t, pBot)}" y1="${Y(pBot)}" x2="${X(t, pTop)}" y2="${Y(pTop)}" stroke="${zero ? "rgba(255,255,255,0.38)" : "rgba(255,255,255,0.08)"}" stroke-width="1.1"/>`;
    }
    // dry adiabats
    for (let th = 240; th <= 440; th += 10) {
      let d = "";
      for (let p = pBot; p >= pTop; p -= 25) d += `${d ? "L" : "M"}${X(th * Math.pow(p / 1000, 0.2857) - 273.15, p).toFixed(1)},${Y(p).toFixed(1)}`;
      s += `<path d="${d}" fill="none" stroke="rgba(251,146,60,0.22)" stroke-width="1"/>`;
    }
    // moist (pseudo) adiabats
    const Rd = 287.04, cp = 1005.7, Lv = 2.501e6, eps = 0.622;
    for (let t0 = -20; t0 <= 36; t0 += 4) {
      let tK = t0 + 273.15, lnp = Math.log(1000), d = `M${X(t0, 1000).toFixed(1)},${Y(1000).toFixed(1)}`;
      // also extend down to pBot
      const steps = 60, dl = (Math.log(pTop) - Math.log(1000)) / steps;
      for (let i = 0; i < steps; i++) {
        const p = Math.exp(lnp), es = esW(tK - 273.15), rs = eps * es / (p - es);
        const dTdlnp = (Rd * tK + Lv * rs) / (cp + (Lv * Lv * rs * eps) / (Rd * tK * tK));
        tK += dTdlnp * dl; lnp += dl;
        d += ` L${X(tK - 273.15, Math.exp(lnp)).toFixed(1)},${Y(Math.exp(lnp)).toFixed(1)}`;
      }
      s += `<path d="${d}" fill="none" stroke="rgba(74,222,128,0.2)" stroke-width="1" stroke-dasharray="4 3"/>`;
    }
    // profiles
    const lv = levels.filter(l => l[0] >= pTop && l[2] != null).sort((a, b) => b[0] - a[0]);
    const path = idx => lv.filter(l => l[idx] != null).map((l, i) => `${i ? "L" : "M"}${X(l[idx], l[0]).toFixed(1)},${Y(l[0]).toFixed(1)}`).join(" ");
    const tw = lv.filter(l => l[3] != null).map(l => [l[0], wetBulbP(l[2], l[3], l[0])]);
    s += `<path d="${tw.map((l, i) => `${i ? "L" : "M"}${X(l[1], l[0]).toFixed(1)},${Y(l[0]).toFixed(1)}`).join(" ")}" fill="none" stroke="#60a5fa" stroke-width="1.6"/>`;
    s += `<path d="${path(3)}" fill="none" stroke="#4ade80" stroke-width="2.2"/>`;
    s += `<path d="${path(2)}" fill="none" stroke="#f87171" stroke-width="2.4"/>`;
    s += `</g>`;
    // tier lines
    [["base", "Base"], ["mid", "Mid"], ["summit", "Summit"]].forEach(([k, lbl]) => {
      const ft = elevs[`${k}_ft`]; const p = ft ? pressureAtHeight(levels, ft / FT) : null;
      if (!p) return;
      s += `<line x1="${L}" x2="${L + PW}" y1="${Y(p)}" y2="${Y(p)}" stroke="rgba(203,213,225,0.5)" stroke-dasharray="3 4"/>
        <text x="${L + PW - 4}" y="${Y(p) - 3}" text-anchor="end" fill="#cbd5e1" font-size="10" font-weight="600">${lbl} ${ft.toLocaleString()} ft · ${Math.round(p)} hPa</text>`;
    });
    // axes labels
    [1000, 850, 700, 500, 400, 300, 200].forEach(p => {
      const z = (() => { const pts = levels.filter(l => l[1] != null); for (let i = 0; i < pts.length - 1; i++) { const a = pts[i], b = pts[i + 1]; if ((p <= a[0] && p >= b[0]) || (p >= a[0] && p <= b[0])) { const f = (Math.log(p) - Math.log(a[0])) / (Math.log(b[0]) - Math.log(a[0])); return a[1] + f * (b[1] - a[1]); } } return null; })();
      s += `<text x="${L - 6}" y="${Y(p) + 3}" text-anchor="end" fill="#94a3b8" font-size="10" font-family="var(--font-mono)">${p}</text>`;
      if (z != null && (!groundP || p <= groundP)) s += `<text x="${L - 6}" y="${Y(p) + 14}" text-anchor="end" fill="#64748b" font-size="8.5" font-family="var(--font-mono)">${(z * FT / 1000).toFixed(1)}k ft</text>`;
    });
    for (let t = -40; t <= 40; t += 10) s += `<text x="${X(t, pBot)}" y="${T + PH + 14}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="var(--font-mono)">${t}°</text>`;
    s += `<text x="${L + PW / 2}" y="${H - 2}" text-anchor="middle" fill="#64748b" font-size="10">Temperature (°C) · isotherms skewed 45°</text>`;
    s += `<text x="${X(-15, 330)}" y="${Y(330)}" fill="#7dd3fc" font-size="10" font-weight="700" text-anchor="middle" transform="rotate(-45 ${X(-15, 330)} ${Y(330)})">DGZ</text>`;
    // wind barbs (mph -> kt), one per ~50 hPa
    const bx = L + PW + 34;
    s += `<line x1="${bx}" x2="${bx}" y1="${T}" y2="${T + PH}" stroke="rgba(255,255,255,0.08)"/>`;
    let lastP = 9999;
    lv.forEach(l => {
      if (l[4] == null || l[5] == null || lastP - l[0] < 45) return;
      lastP = l[0];
      s += barb(bx, Y(l[0]), l[4], l[5] / 1.15078);
    });
    s += `<text x="${bx}" y="${T + PH + 14}" text-anchor="middle" fill="#64748b" font-size="9">kt</text>`;
    // hover layer
    s += `<line id="sk-cross" x1="${L}" x2="${L + PW}" y1="0" y2="0" stroke="#fff" stroke-opacity="0.4" visibility="hidden"/>
      <rect id="sk-hit" x="${L}" y="${T}" width="${PW}" height="${PH}" fill="transparent" style="cursor:crosshair"/></svg>`;
    box.innerHTML = s;

    const svg = box.querySelector("svg"), hit = $("sk-hit"), cross = $("sk-cross"), out = $("skewt-readout");
    const baseFt = elevs.base_ft || 6200;
    const basePres = pressureAtHeight(levels, baseFt / FT) || groundP;
    const showAt = (p, lead) => {
      const interp = idx => { for (let i = 0; i < lv.length - 1; i++) { const a = lv[i], b = lv[i + 1]; if (p <= a[0] && p >= b[0] && a[idx] != null && b[idx] != null) { const f = (Math.log(p) - Math.log(a[0])) / (Math.log(b[0]) - Math.log(a[0])); return a[idx] + f * (b[idx] - a[idx]); } } return null; };
      const t = interp(2), td = interp(3), z = interp(1), ws = interp(5), wd = interp(4), w = hasW ? interp(6) : null;
      const rh = t != null && td != null ? rhFrom(t, td) : null;
      out.innerHTML = `${lead ? `<span class="mini-label">${lead}</span><br>` : ""}<b>${Math.round(p)} hPa</b> · ${z != null ? `${Math.round(z * FT).toLocaleString()} ft` : ""}${groundP && p > groundP + 0.5 ? " (below base)" : ""}<br>
        T ${tC(t)} · Td ${tC(td)} · Tw ${t != null && td != null ? tC(wetBulbP(t, td, p)) : "--"}<br>
        T−Td ${t != null && td != null ? (U.celsius() ? `${(t - td).toFixed(1)} °C` : `${((t - td) * 1.8).toFixed(0)} °F`) : "--"} · RH ${rh != null ? Math.round(rh) : "--"}% (ice ${t != null && td != null ? Math.round(rhIce(t, td)) : "--"}%)<br>
        Wind ${wd != null ? Math.round(wd) + "°" : "--"} ${ws != null ? Math.round(ws) + " mph" : ""}${w != null ? ` · vertical motion ${w > 0 ? "+" : ""}${w.toFixed(0)} cm/s` : ""}`;
    };
    const mgr = src === "model" ? (modelLevels(state.hour) || {}).ground_m : null;
    const belowGround = mgr != null && baseFt / FT < mgr - 50;
    const showBase = () => { if (basePres) showAt(basePres, `Base ${baseFt.toLocaleString()} ft${belowGround ? ` · below this column's terrain (${Math.round(mgr * FT).toLocaleString()} ft), so these values are extrapolated` : ""} · hover for other levels`); };
    showBase();
    hit.addEventListener("mousemove", ev => {
      const pt = svg.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY;
      const loc = pt.matrixTransform(svg.getScreenCTM().inverse());
      cross.setAttribute("y1", loc.y); cross.setAttribute("y2", loc.y); cross.setAttribute("visibility", "visible");
      showAt(pAt(loc.y));
    });
    hit.addEventListener("mouseleave", () => { cross.setAttribute("visibility", "hidden"); showBase(); });
  }

  function barb(x, y, dirDeg, kt) {
    const len = 22;
    let g = `<g transform="translate(${x},${y}) rotate(${dirDeg})" stroke="#cbd5e1" stroke-width="1.3" fill="#cbd5e1">`;
    if (kt < 2.5) return `<circle cx="${x}" cy="${y}" r="3" fill="none" stroke="#cbd5e1"/>`;
    g += `<line x1="0" y1="0" x2="0" y2="${-len}"/>`;
    let rem = Math.round(kt / 5) * 5, pos = -len;
    while (rem >= 50) { g += `<polygon points="0,${pos} 9,${pos + 3} 0,${pos + 6}" stroke="none"/>`; pos += 7; rem -= 50; }
    while (rem >= 10) { g += `<line x1="0" y1="${pos}" x2="9" y2="${pos - 3}"/>`; pos += 4; rem -= 10; }
    if (rem >= 5) { if (pos === -len) pos += 4; g += `<line x1="0" y1="${pos}" x2="5" y2="${pos - 1.7}"/>`; }
    return g + `</g>`;
  }

  // ---------------------------------------------------------------- habit diagram
  // Morphology regions after Kobayashi (1961), Libbrecht (2005, 2017) and Bailey & Hallett (2009), approximate.
  // Temperature sets the basic shape (plate-like near 0 to -3 C and -8 to -22 C, column-like near -3 to -8 C).
  // At one temperature, supersaturation over ice sets how elaborate the crystal gets: faceted and solid at a small
  // vapor excess, then thin, hollow or sectored, then needles and dendrites near water saturation. Boundaries are
  // fractions of the supersaturation at water saturation for that temperature, so they curve with temperature.
  const HABIT_BANDS = [
    { t0: 0, t1: -3, cuts: [0.3], names: ["Thick plates", "Thin plates"], glyphs: ["plate", "plate"] },
    { t0: -3, t1: -8, cuts: [0.2, 0.55], names: ["Solid columns", "Hollow columns", "Needles"], glyphs: ["column", "column", "needle"] },
    { t0: -8, t1: -12, cuts: [0.25, 0.6], names: ["Thick plates", "Thin plates", "Sectored plates"], glyphs: ["plate", "plate", "sector"] },
    { t0: -12, t1: -17, cuts: [0.15, 0.35, 0.6, 1.0], names: ["Thick plates", "Thin plates", "Sectored plates", "Stellar dendrites", "Fernlike dendrites"], glyphs: ["plate", "plate", "sector", "dendrite", "dendrite"] },
    { t0: -17, t1: -22, cuts: [0.2, 0.5], names: ["Thick plates", "Thin plates", "Sectored plates"], glyphs: ["plate", "plate", "sector"] },
    { t0: -22, t1: -30, cuts: [0.35], names: ["Plates, short columns", "Polycrystals, side planes"], glyphs: ["column", "poly"] },
  ];
  const swIce = t => 100 * (esW(t) / esI(t) - 1);   // % over ice when the air is saturated for liquid water
  function habitAt(t, si) {
    if (t == null || si == null) return null;
    if (t > 0) return { name: "above 0 °C: no ice growth", kind: "warm" };
    if (si < 0) return { name: "subsaturated: crystals sublimate", kind: "sub" };
    if (t < -30) return { name: "below −30 °C: columns, bullet rosettes", kind: "cold" };
    const b = HABIT_BANDS.find(x => t <= x.t0 && t >= x.t1) || HABIT_BANDS[HABIT_BANDS.length - 1];
    const sw = swIce(t);
    const f = sw > 0.05 ? si / sw : 9;
    let k = 0;
    while (k < b.cuts.length && f >= b.cuts[k]) k++;
    return { name: b.names[k], glyph: b.glyphs[k], frac: f };
  }
  window.habitAt = habitAt;
  function glyph(kind, cx, cy, r) {
    const hex = Array.from({ length: 6 }, (_, i) => `${(cx + r * Math.cos(Math.PI / 3 * i)).toFixed(1)},${(cy + r * Math.sin(Math.PI / 3 * i)).toFixed(1)}`).join(" ");
    const st = `stroke="#e0f2fe" stroke-width="1.2" fill="none"`;
    if (kind === "plate") return `<polygon points="${hex}" ${st} fill="rgba(224,242,254,0.15)"/>`;
    if (kind === "needle") return `<line x1="${cx}" y1="${cy - r}" x2="${cx}" y2="${cy + r}" ${st} stroke-width="1.6"/>`;
    if (kind === "column") return `<rect x="${cx - r * 0.35}" y="${cy - r}" width="${r * 0.7}" height="${r * 2}" ${st}/>`;
    if (kind === "poly") return `<rect x="${cx - r * 0.3}" y="${cy - r}" width="${r * 0.6}" height="${r * 1.4}" ${st} transform="rotate(-25 ${cx} ${cy})"/><rect x="${cx - r * 0.3}" y="${cy - r * 0.6}" width="${r * 0.6}" height="${r * 1.4}" ${st} transform="rotate(35 ${cx} ${cy})"/>`;
    if (kind === "sector") return `<polygon points="${hex}" ${st}/>` + Array.from({ length: 3 }, (_, i) => `<line x1="${cx + r * Math.cos(Math.PI / 3 * i)}" y1="${cy + r * Math.sin(Math.PI / 3 * i)}" x2="${cx - r * Math.cos(Math.PI / 3 * i)}" y2="${cy - r * Math.sin(Math.PI / 3 * i)}" ${st}/>`).join("");
    let g = "";   // dendrite
    for (let i = 0; i < 6; i++) {
      const a = Math.PI / 3 * i, ex = cx + r * Math.cos(a), ey = cy + r * Math.sin(a);
      g += `<line x1="${cx}" y1="${cy}" x2="${ex}" y2="${ey}" ${st}/>`;
      [0.45, 0.72].forEach(f => {
        const bx = cx + r * f * Math.cos(a), by = cy + r * f * Math.sin(a);
        [-0.6, 0.6].forEach(d => g += `<line x1="${bx}" y1="${by}" x2="${bx + r * 0.28 * Math.cos(a + d)}" y2="${by + r * 0.28 * Math.sin(a + d)}" ${st}/>`);
      });
    }
    return g;
  }

  // tier points: the selected model's 2 m values (the resort's station readings at hour 0)
  function tierHabitPoints(h) {
    const r = state.resort, tls = om().elevation_timelines || {}, el = (r && r.elevations) || {};
    return ["base", "mid", "summit"].map(t => {
      const x = (tls[t] || [])[h] || {};
      const ob = h === 0 && window.Obs ? Obs.forTier(r, t) : null;
      const tf = ob ? ob.temp_f : x.temp_f, tdf = ob ? ob.dew_point_f : x.dew_point_f;
      if (tf == null || tdf == null) return null;
      const tc = (tf - 32) * 5 / 9, tdc = Math.min(tc, (tdf - 32) * 5 / 9);
      const si = 100 * esW(tdc) / esI(Math.min(tc, 0)) - 100;
      return { t, tc, tf, si: tc > 0 ? null : si, ft: el[`${t}_ft`], obs: !!ob, habit: habitAt(tc, tc > 0 ? 0 : si) };
    }).filter(Boolean);
  }

  function renderHabit() {
    const box = $("habit-diagram");
    if (!box || !state.resort) return;
    // Temperature down the vertical axis like a thermometer (0 °C at the top). Supersaturation over ice across:
    // a square-root scale from 0 to 40% (so the narrow regions near 0 to 5% are readable), plus a strip for
    // subsaturated air on the left and one for air above 0 °C on top.
    const W = 760, H = 456, L = 62, R = 14, T = 34, B = 44, PW = W - L - R, PH = H - T - B, SUB = 46;
    const Smax = 40, Tmin = -30, Tmax = 0;
    const Y = t => T + PH * (Tmax - Math.max(Tmin, Math.min(Tmax, t))) / (Tmax - Tmin);
    const X = sp => sp < 0 ? L + SUB * (1 + Math.max(-20, sp) / 20) : L + SUB + (PW - SUB) * Math.sqrt(Math.min(sp, Smax) / Smax);
    let s = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" font-family="var(--font-sans)">`;
    s += `<rect x="${L}" y="${T}" width="${SUB}" height="${PH}" fill="rgba(148,163,184,0.04)"/>
      <text x="${L + SUB / 2}" y="${T + PH / 2}" fill="#64748b" font-size="9.5" text-anchor="middle" transform="rotate(-90 ${L + SUB / 2} ${T + PH / 2})">subsaturated: crystals sublimate</text>
      <rect x="${L}" y="${T - 22}" width="${PW}" height="18" fill="rgba(74,222,128,0.06)"/>
      <text x="${L + 6}" y="${T - 9}" fill="#86efac" font-size="9.5">above 0 °C: melting, no ice growth</text>`;
    HABIT_BANDS.forEach(b => {
      const n = b.names.length;
      b.names.forEach((name, k) => {
        const lo = t => (k === 0 ? 0 : b.cuts[k - 1] * swIce(t)), hi = t => (k === n - 1 ? Smax : Math.min(Smax, b.cuts[k] * swIce(t)));
        const ts = [];
        for (let t = b.t0; t >= b.t1 - 1e-9; t -= 0.25) ts.push(t);
        const left = ts.map(t => `${X(lo(t)).toFixed(1)},${Y(t).toFixed(1)}`);
        const right = ts.slice().reverse().map(t => `${X(hi(t)).toFixed(1)},${Y(t).toFixed(1)}`);
        const cplx = n > 1 ? k / (n - 1) : 0;
        const fill = b.glyphs[k] === "dendrite" ? `rgba(125,211,252,${0.22 + 0.1 * cplx})` : `rgba(${Math.round(148 - 23 * cplx)},${Math.round(163 + 48 * cplx)},${Math.round(184 + 68 * cplx)},${(0.05 + 0.13 * cplx).toFixed(3)})`;
        s += `<polygon points="${left.concat(right).join(" ")}" fill="${fill}" stroke="rgba(255,255,255,0.10)" stroke-width="0.8"><title>${name}: ${b.t0} to ${b.t1} °C</title></polygon>`;
        // label at the region's middle, only where it fits
        const tm = (b.t0 + b.t1) / 2, x0 = X(lo(tm)), x1 = X(hi(tm)), wpx = x1 - x0, hpx = Y(b.t1) - Y(b.t0);
        const words = name.split(" "), fs = 10, cw = fs * 0.56;
        const one = name.length * cw + 8, two = Math.max(...[words.slice(0, Math.ceil(words.length / 2)).join(" "), words.slice(Math.ceil(words.length / 2)).join(" ")].map(w => w.length)) * cw + 8;
        const cx = (x0 + x1) / 2, cy = (Y(b.t0) + Y(b.t1)) / 2;
        const showGlyph = wpx > one + 30 && hpx > 24;
        const tx = showGlyph ? cx - 9 : cx;
        if (wpx >= one && hpx >= 14) s += `<text x="${tx}" y="${cy + 3.5}" text-anchor="middle" fill="${cplx > 0.5 ? "#e2e8f0" : "#94a3b8"}" font-size="${fs}" font-weight="${cplx > 0.5 ? 600 : 500}">${name}</text>`;
        else if (wpx >= two && hpx >= 26 && words.length > 1) {
          const a = words.slice(0, Math.ceil(words.length / 2)).join(" "), c = words.slice(Math.ceil(words.length / 2)).join(" ");
          s += `<text x="${cx}" y="${cy - 2}" text-anchor="middle" fill="${cplx > 0.5 ? "#e2e8f0" : "#94a3b8"}" font-size="${fs}">${a}<tspan x="${cx}" dy="12">${c}</tspan></text>`;
        }
        if (showGlyph && wpx >= one) s += glyph(b.glyphs[k], tx + one / 2 + 10, cy, Math.min(8, hpx / 3.5));
      });
      s += `<line x1="${L}" x2="${L + PW}" y1="${Y(b.t1)}" y2="${Y(b.t1)}" stroke="rgba(255,255,255,0.14)"/>`;
    });
    // water saturation: the vapor excess over ice of air saturated for liquid water
    let d = "";
    for (let t = -0.2; t >= Tmin; t -= 0.5) d += `${d ? "L" : "M"}${X(swIce(t)).toFixed(1)},${Y(t).toFixed(1)}`;
    s += `<path d="${d}" fill="none" stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="5 4"/>
      <text x="${X(swIce(-28)) + 6}" y="${Y(-28) + 4}" fill="#fcd34d" font-size="10">water saturation</text>
      <line x1="${L + SUB}" x2="${L + SUB}" y1="${T}" y2="${T + PH}" stroke="rgba(255,255,255,0.25)"/>`;
    for (let t = Tmin; t <= Tmax; t += 5) s += `<text x="${L - 8}" y="${Y(t) + 3.5}" text-anchor="end" fill="#94a3b8" font-size="10" font-family="var(--font-mono)">${t}°C</text>`;
    [-20, -10].forEach(sp => { s += `<text x="${X(sp)}" y="${T + PH + 15}" text-anchor="middle" fill="#64748b" font-size="9.5" font-family="var(--font-mono)">${sp}</text>`; });
    [0, 1, 2, 5, 10, 20, 30, 40].forEach(sp => {
      s += `<line x1="${X(sp)}" x2="${X(sp)}" y1="${T + PH}" y2="${T + PH + 4}" stroke="#64748b"/><text x="${X(sp)}" y="${T + PH + 15}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="var(--font-mono)">${sp}%</text>`;
    });
    s += `<text x="${L + SUB + (PW - SUB) / 2}" y="${H - 8}" text-anchor="middle" fill="#64748b" font-size="10">Supersaturation over ice (RH w.r.t. ice − 100%), square-root scale</text>`;
    // model levels at this hour (ice-supersaturated or not), labeled in hPa
    const m = modelLevels(state.hour);
    const baseP = m ? pressureAtHeight(m.levels, ((state.resort.elevations || {}).base_ft || 6200) / FT) : null;
    let sup = 0, sub = 0;
    if (m) {
      m.levels.forEach(l => {
        const [p, z, t, td] = l;
        if (td == null || t > 0 || t < -30 || (baseP && p > baseP)) return;
        const si = rhIce(t, td) - 100;
        si >= 0 ? sup++ : sub++;
        const kft = z != null ? `${(z * FT / 1000).toFixed(1)}k` : `${p}`;
        s += `<g><circle cx="${X(si)}" cy="${Y(t)}" r="3.6" fill="none" stroke="#f9a8d4" stroke-width="1.4"/>
          <text x="${X(si) + 6}" y="${Y(t) - 4}" fill="#f9a8d4" font-size="9" font-family="var(--font-mono)">${kft}</text>
          <title>Model level ${p} hPa${z != null ? `, ${Math.round(z * FT).toLocaleString()} ft` : ""}: ${t.toFixed(1)} °C, ${si >= 0 ? "+" : ""}${si.toFixed(0)}% over ice</title></g>`;
      });
    }
    // the dendritic growth zone: its mean supersaturation over ice, drawn across -12 to -18 C
    const pv = (om().vertical_profile || [])[state.hour] || {};
    const dgz = pv.dgz_rhi_pct != null && pv.dgz_base_ft != null ? { si: pv.dgz_rhi_pct - 100, lift: pv.dgz_lift_cm_s, base: pv.dgz_base_ft, top: pv.dgz_top_ft } : null;
    if (dgz) {
      const x = X(dgz.si), y0 = Y(-12), y1 = Y(-18);
      s += `<g><rect x="${x - 6}" y="${y0}" width="12" height="${y1 - y0}" rx="6" fill="#22d3ee" fill-opacity="0.85" stroke="#0b1220" stroke-width="2"/>
        <text x="${x + 11}" y="${Y(-15) + 4}" fill="#a5f3fc" font-size="11" font-weight="800" style="paint-order:stroke" stroke="#0b1220" stroke-width="3">DGZ</text>
        <title>Dendritic growth zone ${(dgz.base / 1000).toFixed(1)}–${(dgz.top / 1000).toFixed(1)}k ft: ${dgz.si >= 0 ? "+" : ""}${dgz.si.toFixed(0)}% over ice${dgz.lift != null ? `, lift ${dgz.lift} cm/s` : ""}</title></g>`;
    }
    // tiers
    const COL = { base: "#34d399", mid: "#a78bfa", summit: "#fb7185" };
    const pts = tierHabitPoints(state.hour);
    pts.forEach(pt => {
      const x = pt.tc > 0 ? L + 214 + { base: 0, mid: 22, summit: 44 }[pt.t] : X(pt.si), y = pt.tc > 0 ? T - 13 : Y(pt.tc);
      s += `<g><circle cx="${x}" cy="${y}" r="8.5" fill="${COL[pt.t]}" stroke="#0b1220" stroke-width="2"/>
        <text x="${x}" y="${y + 3.6}" text-anchor="middle" fill="#0b1220" font-size="10" font-weight="800">${pt.t[0].toUpperCase()}</text>
        <title>${pt.t}: ${pt.tc.toFixed(1)} °C${pt.si != null ? `, ${pt.si.toFixed(1)}% over ice` : ""} → ${pt.habit ? pt.habit.name : ""}</title></g>`;
    });
    box.innerHTML = s + `</svg>
      <ul class="habit-tiers">${dgz ? `<li><i style="background:#22d3ee;border-radius:6px">D</i><b>DGZ ${(dgz.base / 1000).toFixed(1)}–${(dgz.top / 1000).toFixed(1)}k ft</b>
        −12 to −18 °C, ${dgz.si >= 0 ? "+" : "−"}${Math.abs(dgz.si).toFixed(0)}% over ice${dgz.lift != null ? `, lift ${dgz.lift >= 0 ? "+" : "−"}${Math.abs(Math.round(dgz.lift))} cm/s` : ""} → <b>${esc((habitAt(-15, dgz.si) || {}).name || "–")}</b>${dgz.si >= 0 && (dgz.lift ?? 0) >= 10 ? " (growing fast: saturated and rising)" : dgz.si < 0 ? "" : " (weak lift: slow growth)"}</li>` : ""}${pts.slice().reverse().map(pt => `<li><i style="background:${COL[pt.t]}">${pt.t[0].toUpperCase()}</i><b>${{ base: "Base", mid: "Mid", summit: "Summit" }[pt.t]}${pt.ft ? ` ${pt.ft.toLocaleString()} ft` : ""}</b>
        ${U.temp(pt.tf)}${pt.obs ? "*" : ""} (${pt.tc.toFixed(1)} °C)${pt.si != null ? `, ${pt.si >= 0 ? "+" : ""}${pt.si.toFixed(1)}% over ice` : ""} → <b>${esc(pt.habit ? pt.habit.name : "–")}</b></li>`).join("")}</ul>
      <p class="habit-status">${m ? `${new Date(m.time).toLocaleString([], { weekday: "short", hour: "numeric" })}. Circles: tiers (2 m values of ${esc(((om().model || {}).label) || "the selected model")}${pts.some(p => p.obs) ? "; * resort station readings at hour 0" : ""}). Bar: the dendritic growth zone (−12 to −18 °C) at its mean supersaturation; most snow grows aloft, and the DGZ is where dendrites (high snow/liquid ratio) form, so it matters more than the tiers. Rings: ${(om().profile_model || {}).label || "model"} column levels between 0 and −30 °C above the base, labeled by height in thousands of feet (${sup} ice-supersaturated, ${sub} subsaturated; levels drier than −20% sit on the left edge). Tier circles show how crystals change on the way down.` : `No model profile for ${esc(((om().model || {}).label) || "this model")}; tier circles only.`}</p>`;
  }

  // ---------------------------------------------------------------- precip type by elevation
  function renderPhase() {
    const box = $("phase-svg");
    if (!box || !state.resort) return;
    const r = state.resort, o = om(), tls = o.elevation_timelines || {};
    const h = state.hour;
    const prof = (o.vertical_profile || [])[h] || {};
    const elevs = r.elevations || {};
    const tsum = ((tls.summit || [])[h]) || {};
    const sl = prof.snow_level_ft ?? tsum.snow_level_ft;
    const wbz = prof.wet_bulb_zero_ft ?? tsum.wet_bulb_zero_ft;
    const fz = prof.freezing_level_ft ?? tsum.freezing_level_ft;
    const pm = o.profile_model;
    const mLabel = (o.model || {}).label || "model";
    // Vertical range: fixed across hours and models (server scales), clamped around the mountain
    const base = elevs.base_ft || 6200, top = elevs.summit_ft || 9000, lv = (o.scales || {}).levels_ft;
    let lo = Math.min(base - 1000, lv ? lv[0] - 500 : base - 2000);
    let hi = Math.max(top + 1000, lv ? lv[1] + 500 : top + 2000);
    lo = Math.max(0, Math.max(base - 5000, Math.floor(lo / 1000) * 1000));
    hi = Math.min(top + 7000, Math.ceil(hi / 1000) * 1000);

    const W = Math.max(300, Math.round(box.clientWidth || 360)), narrow = W < 440;
    const H = 210, T = 10, B = 8, PH = H - T - B;
    const axW = 28, barX = axW + 6, barW = narrow ? 18 : 28, barR = barX + barW;
    const tblX = barR + (narrow ? 20 : 36);
    const Y = ft => T + PH * (1 - (Math.max(lo, Math.min(hi, ft)) - lo) / (hi - lo));
    const f = ft => ((Math.max(lo, Math.min(hi, ft)) - lo) / (hi - lo)).toFixed(3);
    const slx = sl ?? (wbz != null ? wbz - 500 : null);
    let s = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg" font-family="var(--font-sans)">
      <defs><linearGradient id="phgrad" x1="0" y1="1" x2="0" y2="0">`;
    if (slx != null) {
      s += `<stop offset="0" stop-color="#4ade80" stop-opacity=".35"/><stop offset="${f(slx - 1000)}" stop-color="#4ade80" stop-opacity=".35"/>
        <stop offset="${f(slx - 250)}" stop-color="#c084fc" stop-opacity=".4"/><stop offset="${f(slx + 500)}" stop-color="#7dd3fc" stop-opacity=".42"/><stop offset="1" stop-color="#7dd3fc" stop-opacity=".42"/>`;
    } else s += `<stop offset="0" stop-color="#7dd3fc" stop-opacity=".4"/><stop offset="1" stop-color="#7dd3fc" stop-opacity=".4"/>`;
    s += `</linearGradient></defs><rect x="${barX}" y="${T}" width="${barW}" height="${PH}" rx="6" fill="url(#phgrad)" stroke="rgba(255,255,255,0.12)"/>`;
    const step = hi - lo > 10000 ? 2000 : 1000;
    for (let ft = Math.ceil(lo / step) * step; ft <= hi; ft += step) s += `<text x="${axW}" y="${Y(ft) + 4}" text-anchor="end" fill="#64748b" font-size="10.5" font-family="var(--font-mono)">${ft / 1000}k</text>`;
    const lvLine = (ft, color, dash, w) => ft == null ? "" : `<line x1="${barX - 4}" x2="${barR + 4}" y1="${Y(ft)}" y2="${Y(ft)}" stroke="${color}" stroke-width="${w}" ${dash ? `stroke-dasharray="${dash}"` : ""}/>`;
    s += lvLine(fz, "#fbbf24", "4 3", 2) + lvLine(wbz, "#60a5fa", "", 2) + lvLine(sl, "#f8fafc", "", 2.2);

    // table columns
    // column widths scale to the space right of the bar (minimum widths fit the text)
    const base_cols = narrow ? [["Air", 40], ["Wet bulb", 50], ["T − Td", 44], ["RH", 38]] : [["Air", 44], ["Wet bulb", 58], ["T − Td", 50], ["RH", 40], ["Precip", 62]];
    const avail = W - tblX - 4, nameW0 = narrow ? 56 : 62, need = nameW0 + base_cols.reduce((a, c) => a + c[1], 0);
    const k = Math.max(0.75, Math.min(1.6, avail / need));
    const cols = base_cols.map(([l, w]) => [l, Math.round(w * k)]);
    const nameW = Math.round(nameW0 * Math.min(k, 1.2));
    let cx = tblX + nameW;
    const colX = cols.map(([, w]) => { cx += w; return cx; });   // right edges
    const headY = () => (rowsTop != null ? rowsTop - 19 : 12);
    let rowsTop = null;

    // rows positioned at their elevation, spread so they never overlap
    const tiers = ["summit", "mid", "base"].filter(t => elevs[`${t}_ft`]);
    const rows = tiers.map(t => ({ t, ft: elevs[`${t}_ft`], y: Y(elevs[`${t}_ft`]) }));
    const gapY = 32;
    rows.forEach((rw, i) => { rw.ry = Math.max(rw.y, T + 26, i ? rows[i - 1].ry + gapY : 0); });
    const over = rows.length ? rows[rows.length - 1].ry - (H - 20) : 0;
    if (over > 0) rows.forEach(rw => { rw.ry -= over; });
    // column headers sit right above the first row
    rowsTop = rows.length ? rows[0].ry - 4 : null;
    s += cols.map(([lbl], i) => `<text x="${i === 4 ? colX[i] - cols[i][1] + 6 : colX[i]}" y="${headY()}" text-anchor="${i === 4 ? "start" : "end"}" fill="#64748b" font-size="10.5" font-weight="600">${lbl}</text>`).join("");
    s += `<line x1="${tblX}" x2="${colX[colX.length - 1]}" y1="${headY() + 5}" y2="${headY() + 5}" stroke="rgba(255,255,255,0.08)"/>`;
    if (narrow) s += `<text x="${tblX}" y="${headY()}" fill="#64748b" font-size="10.5" font-weight="600">Tier</text>`;
    const fmtT = v => (v == null ? "--" : tF(v));
    const phaseCol = { snow: "#7dd3fc", mix: "#c084fc", rain: "#4ade80", ice: "#fb7185", dry: "#64748b" };
    const obsList = [];
    rows.forEach(rw => {
      const x = (tls[rw.t] || [])[h] || {};
      const ob = h === 0 && window.Obs ? Obs.forTier(r, rw.t) : null;
      if (ob) obsList.push(ob);
      const mT = x.temp_f, mTw = x.wet_bulb_f, mDd = x.dew_point_depression_f ?? (x.temp_f != null && x.dew_point_f != null ? x.temp_f - x.dew_point_f : null), mRh = x.relative_humidity_pct;
      const oTw = ob ? Obs.wetBulbF(ob.temp_f, ob.dew_point_f, ob.elevation_ft || rw.ft) : null;
      const vals = ob ? [fmtT(ob.temp_f), fmtT(oTw), dDiff(ob.temp_f - ob.dew_point_f), `${Math.round(ob.humidity_pct)}%`] : [fmtT(mT), fmtT(mTw), dDiff(mDd), mRh != null ? `${mRh}%` : "--"];
      const sub = ob ? [narrow ? fmtT(mT) : `model ${fmtT(mT)}`, fmtT(mTw), dDiff(mDd), mRh != null ? `${mRh}%` : ""] : null;
      // tier line across the bar and the callout to its row
      s += `<line x1="${barX - 3}" x2="${barR + 3}" y1="${rw.y}" y2="${rw.y}" stroke="rgba(203,213,225,0.55)" stroke-dasharray="3 3"/>
        <path d="M${barR + 4},${rw.y} L${barR + 10},${rw.y} L${tblX - 10},${rw.ry} L${tblX - 3},${rw.ry}" fill="none" stroke="rgba(203,213,225,0.3)"/>`;
      const ph = x.precip_phase || "dry";
      const phTxt = ph === "dry" ? "none" : (x.precip_phase_label || ph).toLowerCase();
      s += `<text x="${tblX}" y="${rw.ry + 4}" fill="#e2e8f0" font-size="12" font-weight="650">${{ base: "Base", mid: "Mid", summit: "Summit" }[rw.t]}</text>
        <text x="${tblX}" y="${rw.ry + 17}" fill="${narrow ? (phaseCol[ph] || "#94a3b8") : "#64748b"}" font-size="10">${narrow ? phTxt : `${rw.ft.toLocaleString()} ft`}</text>`;
      vals.forEach((v, i) => { s += `<text x="${colX[i]}" y="${rw.ry + 4}" text-anchor="end" fill="${ob ? "#f8fafc" : "#e2e8f0"}" font-size="12" style="font-variant-numeric:tabular-nums">${v}</text>`; });
      if (sub) sub.forEach((v, i) => { if (v) s += `<text x="${colX[i]}" y="${rw.ry + 17}" text-anchor="end" fill="#64748b" font-size="9.5" style="font-variant-numeric:tabular-nums">${i ? v : v}</text>`; });
      if (!narrow) s += `<text x="${colX[4] - cols[4][1] + 6}" y="${rw.ry + 4}" fill="${phaseCol[ph] || "#94a3b8"}" font-size="11.5" font-weight="600">${phTxt}</text>`;
    });
    box.innerHTML = s + `</svg>`;

    // levels, highest first, with their source
    const lsrc = pm ? pm.label : mLabel;
    const levels = [
      ["Freezing level", fz, `<i class="lvl-sw" style="border-top:2px dashed #fbbf24"></i>`, lsrc],
      ["Wet-bulb zero", wbz, `<i class="lvl-sw" style="border-top:2px solid #60a5fa"></i>`, lsrc],
      ["Snow level", sl, `<i class="lvl-sw" style="border-top:2px solid #f8fafc"></i>`, pm ? mLabel : (o.vertical_profile || []).length ? "wet-bulb zero − 500 ft" : mLabel],
    ].filter(l => l[1] != null).sort((a, b) => b[1] - a[1]);
    // base rain risk for this hour: the base elevation against this hour's snow level
    const prb = $("phase-risk-badge");
    if (prb) {
      const baseFt = elevs.base_ft, slh = slx;
      const xb = (tls.base || [])[h] || {};
      const dryH = (xb.precip_in || 0) < 0.005;
      const risk = baseFt == null || slh == null ? null : baseFt > slh + 500 ? "low" : baseFt >= slh ? "moderate" : "high";
      prb.textContent = risk ? `Base rain risk: ${risk}${dryH ? " (dry)" : ""}` : "Base rain risk: n/a";
      prb.className = "chip " + (risk === "low" ? "chip-good" : risk === "moderate" ? "chip-warn" : risk === "high" ? "chip-bad" : "");
      prb.title = risk ? `Selected hour: snow level ${Math.round(slh).toLocaleString()} ft, base ${baseFt.toLocaleString()} ft. Low: base more than 500 ft above the snow level; moderate: base at or up to 500 ft above it; high: base below it.${dryH ? " No precipitation at the base this hour." : ""}` : "";
    }
    const lvBox = $("phase-levels");
    if (lvBox) lvBox.innerHTML = levels.map(([n, v, sw, src]) => `<dt>${sw}${n} <small>${esc(src)}</small></dt><dd>${fmtFt(v)}</dd>`).join("") || `<dt>Levels</dt><dd>n/a</dd>`;
    const t0 = tsum.time;
    const when = t0 ? new Date(t0).toLocaleString([], { weekday: "short", hour: "numeric" }) : "";
    const obsTxt = obsList.length ? ` Hour 0 values are resort station readings (${obsList.map(ob => `${(ob.name || "").replace(/,? el\. (\d+)'?/, " $1 ft")}`).join(", ")}; observed ${obsList[0].observed.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}); small numbers are the model at each tier.` : "";
    const set = (id, v) => { const e = $(id); if (e) e.textContent = v; };
    set("phase-desc", pm
      ? `${when}. Precipitation type and tier values: ${mLabel}, adjusted to each tier's elevation. Snow level: ${mLabel}. Freezing level and wet-bulb zero: ${pm.label} column.${obsTxt}`
      : (o.vertical_profile || []).length
        ? `${when}. Snow fraction: 100% at or above the wet-bulb zero, 0% 1,000 ft below it; overridden by surface wet bulb (≤ 31 °F snow, ≥ 36 °F rain). Sleet/freezing rain risk: layer > +0.5 °C at least 1,000 ft deep above a sub-freezing wet bulb.${obsTxt}`
        : `${when}. ${mLabel}'s own snow level and precipitation type.${obsTxt}`);
  }

  // ---------------------------------------------------------------- dendritic growth zone
  function renderDGZ() {
    const box = $("dgz-chart");
    if (!box || !state.resort) return;
    const o = om(), prof = o.vertical_profile || [], elevs = state.resort.elevations || {};
    const set = (id, v) => { const e = $(id); if (e) e.textContent = v; };
    const pm = o.profile_model;
    if (!prof.length) {
      box.innerHTML = `<p class="mini-label" style="padding:12px 0">No vertical profile for this model.</p>`;
      ["dgz-height", "dgz-rhi", "dgz-w"].forEach(id => set(id, "n/a"));
      return;
    }
    const h = Math.min(state.hour, prof.length - 1), p = prof[h] || {};
    const kind = x => x.dgz_base_ft == null ? "none" : (x.dgz_rhi_pct ?? 0) >= 100 ? ((x.dgz_lift_cm_s ?? -1) >= 10 ? "act" : "sat") : "dry";
    const k = kind(p);
    const badge = $("dgz-badge");
    if (badge) { badge.textContent = { act: "Saturated, rising", sat: "Saturated, weak lift", dry: "Subsaturated", none: "Not found" }[k]; badge.className = "chip " + (k === "act" ? "chip-ice" : ""); }
    set("dgz-height", p.dgz_base_ft != null ? `${(p.dgz_base_ft / 1000).toFixed(1)}–${(p.dgz_top_ft / 1000).toFixed(1)}k ft` : "n/a");
    set("dgz-pres", p.dgz_base_hpa != null ? `${p.dgz_base_hpa}–${p.dgz_top_hpa} hPa` : "");
    const dp = $("dgz-pres"); if (dp && dp.parentElement) dp.parentElement.title = p.dgz_base_ft != null ? `Layer between −12 and −18 °C, ${(p.dgz_thickness_ft || 0).toLocaleString()} ft thick` : "";
    set("dgz-rhi", p.dgz_rhi_pct != null ? `${p.dgz_rhi_pct}%` : "n/a");
    set("dgz-w", p.dgz_lift_cm_s != null ? `${p.dgz_lift_cm_s >= 0.5 ? "+" : p.dgz_lift_cm_s <= -0.5 ? "−" : ""}${Math.abs(p.dgz_lift_cm_s).toFixed(0)} cm/s` : "n/a");
    const next = prof.slice(h, h + 24);
    set("dgz-hours-val", `${next.filter(x => kind(x) === "act").length} of ${next.length} h`);
    const st = ((o.elevation_timelines || {}).summit || []).slice(h, h + 24).filter(x => (x.precip_in || 0) >= 0.01 && x.slr);
    const liq = st.reduce((a, x) => a + x.precip_in, 0);
    set("dgz-crystal-val", liq > 0 ? `${(st.reduce((a, x) => a + x.slr * x.precip_in, 0) / liq).toFixed(1)}:1` : "no precipitation");
    set("dgz-source", `Profile: ${pm ? `${pm.label} column at the summit point (${(o.model || {}).label} has no vertical profile)` : `${(o.model || {}).label || "model"} column at the summit point`}. Click the chart to pick an hour.`);

    const W = Math.max(280, Math.round(box.clientWidth || 340)), H = 150, L = 40, R = 6, T = 6, Bm = 18, PW = W - L - R, PH = H - T - Bm;
    const zlo = Math.min(4000, Math.floor(((elevs.base_ft || 6200) - 1500) / 1000) * 1000), zhi = 24000;
    const Y = ft => T + PH * (1 - (Math.max(zlo, Math.min(zhi, ft)) - zlo) / (zhi - zlo));
    const n = prof.length, dx = PW / n;
    let s = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg" font-family="var(--font-sans)">
      <rect x="${L}" y="${T}" width="${PW}" height="${PH}" fill="rgba(255,255,255,0.02)" stroke="rgba(255,255,255,0.08)"/>`;
    for (let ft = 8000; ft <= zhi; ft += 8000) s += `<line x1="${L}" x2="${L + PW}" y1="${Y(ft)}" y2="${Y(ft)}" stroke="rgba(255,255,255,0.05)"/><text x="${L - 5}" y="${Y(ft) + 3.5}" text-anchor="end" fill="#64748b" font-size="9.5" font-family="var(--font-mono)">${ft / 1000}k</text>`;
    prof.forEach((x, i) => {
      if (x.dgz_base_ft == null) return;
      const kk = kind(x);
      const fill = kk === "act" ? `fill="#22d3ee" fill-opacity="0.95"` : kk === "sat" ? `fill="#7dd3fc" fill-opacity="0.5"` : `fill="#d6bc96" fill-opacity="${(0.1 + 0.3 * Math.min(1, (x.dgz_rhi_pct || 0) / 100)).toFixed(2)}"`;
      s += `<rect x="${(L + i * dx).toFixed(1)}" y="${Y(x.dgz_top_ft).toFixed(1)}" width="${(dx + 0.4).toFixed(1)}" height="${Math.max(1, Y(x.dgz_base_ft) - Y(x.dgz_top_ft)).toFixed(1)}" ${fill}/>`;
    });
    const fzp = prof.map((x, i) => x.freezing_level_ft != null ? `${i ? "L" : "M"}${(L + (i + 0.5) * dx).toFixed(1)},${Y(x.freezing_level_ft).toFixed(1)}` : "").join(" ").replace(/^ *L/, "M");
    s += `<path d="${fzp}" fill="none" stroke="#fbbf24" stroke-opacity="0.7" stroke-width="1.2" stroke-dasharray="3 2"/>`;
    [["summit", "Summit"], ["base", "Base"]].forEach(([t, lbl]) => {
      const ft = elevs[`${t}_ft`]; if (!ft) return;
      s += `<line x1="${L}" x2="${L + PW}" y1="${Y(ft)}" y2="${Y(ft)}" stroke="rgba(203,213,225,0.4)" stroke-dasharray="2 3"/><text x="${L + 3}" y="${Y(ft) - 3}" fill="#94a3b8" font-size="9.5">${lbl}</text>`;
    });
    (((o.elevation_timelines || {}).summit) || []).forEach((x, i) => {
      const d = new Date(x.time);
      if (d.getHours() === 0 && i > 0) s += `<line x1="${L + i * dx}" x2="${L + i * dx}" y1="${T}" y2="${T + PH}" stroke="rgba(255,255,255,0.06)"/><text x="${L + i * dx + 2}" y="${H - 5}" fill="#64748b" font-size="9.5">${d.toLocaleDateString([], { weekday: "short" })}</text>`;
    });
    s += `<line x1="${L + (h + 0.5) * dx}" x2="${L + (h + 0.5) * dx}" y1="${T}" y2="${T + PH}" stroke="#f8fafc" stroke-opacity="0.8" stroke-width="1.5"/>
      <rect id="dgz-hit" x="${L}" y="${T}" width="${PW}" height="${PH}" fill="transparent" style="cursor:pointer"/></svg>`;
    box.innerHTML = s;
    const hit = $("dgz-hit"), svg = box.querySelector("svg");
    hit && hit.addEventListener("click", ev => {
      const pt = svg.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY;
      const loc = pt.matrixTransform(svg.getScreenCTM().inverse());
      const hour = Math.max(0, Math.min(n - 1, Math.floor((loc.x - L) / dx)));
      document.dispatchEvent(new CustomEvent("snow:sethour", { detail: { hour } }));
    });
  }

  // ---------------------------------------------------------------- supercooled liquid water (HRRR, RRFS)
  // One-hue sequential ramp (orange, OKLCH L 0.50 -> 0.90) on a 1-2.5-5 scale, validated as an ordinal ramp against the
  // card surface (monotone lightness, adjacent steps >= 0.06, darkest step 2.9:1). Liquid at or above 0 °C is neutral gray.
  const SLW_EDGES = [0.01, 0.025, 0.05, 0.1, 0.25, 0.5];           // g/kg, lower edge of each bin
  const SLW_RAMP = ["#944e12", "#b56116", "#d67523", "#f08f47", "#fcb17e", "#ffd2b1"];
  const SLW_WARM = "rgba(148,163,184,0.38)";
  const SLW_LINE = "#f08f47";
  const slwBin = v => { let k = -1; while (k + 1 < SLW_EDGES.length && v >= SLW_EDGES[k + 1]) k++; return k; };
  const fmtQ = v => (v == null ? "–" : v >= 0.095 ? v.toFixed(2) : v >= 0.0095 ? v.toFixed(3) : v > 0 ? "<0.01" : "0");
  const fmtCol = v => (v == null ? "–" : v >= 0.095 ? v.toFixed(2) : v >= 0.0005 ? v.toFixed(3) : "0");
  // riming hatch: a dark and a light line every 5 px, so it shows on every step of the ramp (chart and key share it)
  const slwHatch = id => `<pattern id="${id}" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">`
    + `<line x1="0.8" y1="0" x2="0.8" y2="5" stroke="#0b1220" stroke-opacity="0.75" stroke-width="1.5"/>`
    + `<line x1="2.7" y1="0" x2="2.7" y2="5" stroke="#f8fafc" stroke-opacity="0.6" stroke-width="0.9"/></pattern>`;

  // Key above the chart: the ramp as a stepped scale with its bin edges, what hatching, gray and no fill mean (with the
  // thresholds from the data), then the lines. Every swatch uses the chart's own fills, strokes and hatch.
  function slwKey(th) {
    const sw = (w, h, body) => `<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" aria-hidden="true">${body}</svg>`;
    const bw = 44, bh = 14, x0 = 14, tip = 8, nb = SLW_RAMP.length, sx = x0 + nb * bw + tip;
    let sc = "";
    SLW_RAMP.forEach((c, k) => {
      const x = x0 + k * bw, hi = SLW_EDGES[k + 1];
      const rng = `<title>${hi != null ? `${SLW_EDGES[k]} to ${hi} g/kg` : `${SLW_EDGES[k]} g/kg or more`}</title>`;
      sc += k < nb - 1 ? `<rect x="${x}" y="0" width="${bw - 1}" height="${bh}" fill="${c}">${rng}</rect>`
        : `<path d="M${x},0H${x + bw - 1}L${x + bw - 1 + tip},${bh / 2}L${x + bw - 1},${bh}H${x}Z" fill="${c}">${rng}</path>`;
      sc += `<line x1="${x}" x2="${x}" y1="${bh}" y2="${bh + 4}" stroke="#6b7a90"/><text x="${x}" y="${bh + 15}" text-anchor="middle">${SLW_EDGES[k]}</text>`;
    });
    sc += `<text x="${sx + 6}" y="${bh / 2 + 3.5}" class="unit">g/kg</text>`;
    const box = (body, id) => sw(35, 16, (id ? `<defs>${slwHatch(id)}</defs>` : "") + body);
    const hatched = box([1, 3, 5].map((s, k) => `<rect x="${k * 12}" y="0" width="11" height="16" fill="${SLW_RAMP[s]}"/><rect x="${k * 12}" y="0" width="11" height="16" fill="url(#slw-hatch-key)"/>`).join(""), "slw-hatch-key");
    const line = attrs => sw(24, 12, `<line x1="1" x2="23" y1="6" y2="6" stroke-linecap="round" ${attrs}/>`);
    const item = (swatch, txt) => `<div class="slw-key-item">${swatch}<span>${txt}</span></div>`;
    const lineItem = (swatch, txt) => `<span>${swatch}${txt}</span>`;
    return `<div class="slw-key-scale"><span class="slw-key-head">Supercooled liquid in each cell</span>`
      + `<svg viewBox="0 0 ${sx + 36} ${bh + 19}" width="${sx + 36}" height="${bh + 19}" role="img" aria-label="Orange steps: ${SLW_EDGES.join(", ")} g/kg and more; lighter is more liquid">${sc}</svg>`
      + `<small>Each step starts at the value under its left edge; the pointed one is ${SLW_EDGES[nb - 1]} g/kg and more. Lighter is more liquid.</small></div>`
      + `<div class="slw-key-items">`
      + item(hatched, `<b>Hatched:</b> riming layer, supercooled liquid ≥ ${th.liquid} g/kg with snow + graupel ≥ ${th.snow_graupel} g/kg in the same cell. The orange under the hatching still gives the liquid.`)
      + item(box(`<rect width="35" height="16" fill="${SLW_WARM}"/>`), `<b>Gray:</b> liquid at 0 °C or warmer (not supercooled, not counted)`)
      + item(box(`<rect x="0.5" y="0.5" width="34" height="15" fill="rgba(255,255,255,0.02)" stroke="rgba(148,163,184,0.5)" stroke-dasharray="2 2"/>`), `<b>No fill:</b> less than ${th.liquid} g/kg of liquid`)
      + `</div><div class="slw-key-lines">`
      + lineItem(line('stroke="#f8fafc" stroke-opacity="0.9" stroke-width="1.6"'), "0 °C")
      + lineItem(line('stroke="#cbd5e1" stroke-opacity="0.75" stroke-width="1.1" stroke-dasharray="4 3"'), "−10 and −20 °C")
      + lineItem(sw(24, 12, `<rect x="0" y="2" width="24" height="8" fill="rgba(125,211,252,0.16)"/><path d="M0,2H24M0,10H24" stroke="#7dd3fc" stroke-opacity="0.7"/>`), "DGZ, −12 to −18 °C")
      + lineItem(line('stroke="rgba(203,213,225,0.6)" stroke-dasharray="3 3"'), "Summit height")
      + lineItem(sw(24, 12, `<rect x="0" y="5" width="24" height="7" fill="rgba(148,163,184,0.2)"/><path d="M0,5H24" stroke="rgba(203,213,225,0.35)"/>`), "Below the model terrain")
      + lineItem(sw(12, 12, `<line x1="6" x2="6" y1="0" y2="12" stroke="#f8fafc" stroke-opacity="0.8" stroke-width="1.5"/>`), "Selected hour")
      + lineItem(line(`stroke="${SLW_LINE}" stroke-width="2"`), "Column total (lower chart)")
      + lineItem(sw(24, 12, `<defs>${slwHatch("slw-hatch-key2")}</defs><rect x="0" y="2" width="24" height="10" fill="#d67523" fill-opacity="0.45"/><rect x="0" y="2" width="24" height="10" fill="url(#slw-hatch-key2)"/>`), "Part in riming layers (lower chart)")
      + `</div>`;
  }

  const SLW_LAST = { hrrr: 48, rrfs: 84 };              // last forecast hour of each model's 00/06/12/18Z runs
  function slwData() {
    const s = ((state.resort || {}).sources || {})[`${state.slwModel}_slw`] || {};
    const t0 = ((((om().elevation_timelines || {}).summit) || [])[0] || {}).time;
    return { s, hours: (s.hours || []).filter(x => !t0 || x.time >= t0) };
  }
  // the HRRR | RRFS switch: the active model, and each model's run (cycle, length) from its data
  function slwSwitch() {
    const seg = $("slw-model"), src = (state.resort || {}).sources || {};
    if (!seg) return;
    seg.querySelectorAll(".seg-btn").forEach(b => {
      const m = b.dataset.model, d = src[`${m}_slw`] || {}, on = m === state.slwModel;
      b.classList.toggle("active", on);
      b.setAttribute("aria-selected", on ? "true" : "false");
      b.innerHTML = `${esc(d.model || m.toUpperCase())} <span>${(d.hours || []).length ? `${d.cycle_utc.slice(11, 13)}Z · ${d.last_fh ?? SLW_LAST[m]} h` : "no data"}</span>`;
    });
  }
  // dashboard hour -> index into the model's hours (-1 when the hour is outside the run)
  function slwIndex(hours, h) {
    const t = ((((om().elevation_timelines || {}).summit) || [])[h] || {}).time;
    return t ? hours.findIndex(x => x.time === t) : Math.min(h, hours.length - 1);
  }
  // marching squares: path data of the `lev` contour through grid[i][k] at (xs[i], ys[k]); null cells are skipped
  function contour(grid, xs, ys, lev) {
    let d = "";
    const cut = (a, b, xa, ya, xb, yb) => { const f = (lev - a) / (b - a); return [xa + f * (xb - xa), ya + f * (yb - ya)]; };
    for (let i = 0; i + 1 < xs.length; i++) for (let k = 0; k + 1 < ys.length; k++) {
      const a = grid[i][k], b = grid[i + 1][k], c = grid[i + 1][k + 1], e = grid[i][k + 1];
      if (a == null || b == null || c == null || e == null) continue;
      const p = [];
      if ((a < lev) !== (b < lev)) p.push(cut(a, b, xs[i], ys[k], xs[i + 1], ys[k]));
      if ((b < lev) !== (c < lev)) p.push(cut(b, c, xs[i + 1], ys[k], xs[i + 1], ys[k + 1]));
      if ((c < lev) !== (e < lev)) p.push(cut(c, e, xs[i + 1], ys[k + 1], xs[i], ys[k + 1]));
      if ((e < lev) !== (a < lev)) p.push(cut(e, a, xs[i], ys[k + 1], xs[i], ys[k]));
      for (let q = 0; q + 1 < p.length; q += 2) d += `M${p[q][0].toFixed(1)},${p[q][1].toFixed(1)}L${p[q + 1][0].toFixed(1)},${p[q + 1][1].toFixed(1)}`;
    }
    return d;
  }

  function renderSLW() {
    const box = $("slw-chart");
    if (!box || !state.resort) return;
    const { s, hours } = slwData();
    const set = (id, v) => { const e = $(id); if (e) e.textContent = v; };
    const M = s.model || state.slwModel.toUpperCase();
    slwSwitch();
    set("slw-sub", `${M} cloud water and rain water colder than 0 °C above the summit, by hour and pressure level.`);
    const badge = $("slw-badge"), legend = $("slw-legend"), kvBox = $("slw-kv"), table = $("slw-table");
    const stats = ["slw-col", "slw-summit", "slw-peak", "slw-rime"];
    if (!hours.length) {
      const why = s.status === "error" || !s.status ? `${M} supercooled liquid is unavailable${s.error_message ? ` (${s.error_message})` : ""}.` : `The cached ${M} run has no hours from now on; the next refresh fetches a newer one.`;
      box.innerHTML = `<p class="mini-label" style="padding:12px 0">${esc(why)}</p>`;
      const tip = $("slw-tip"); if (tip) tip.style.display = "none";      // its chart (and mouseleave) is gone
      stats.forEach(id => { set(id, "n/a"); set(`${id}-sub`, ""); });
      if (badge) { badge.textContent = "No data"; badge.className = "chip"; }
      [legend, kvBox, table].forEach(e => { if (e) e.innerHTML = ""; });
      set("slw-note", "");
      return;
    }
    const lv = s.levels_hpa, nl = lv.length, n = hours.length;
    const th = s.thresholds_g_kg || { liquid: 0.01, snow_graupel: 0.01 };
    const si = slwIndex(hours, state.hour), sel = si >= 0 ? hours[si] : null;
    const summitFt = (s.point || {}).elevation_ft || (state.resort.elevations || {}).summit_ft;
    const when = t => new Date(t).toLocaleString([], { weekday: "short", hour: "numeric" });
    const zft = (x, k) => (x.z_m && x.z_m[k] != null ? Math.round(x.z_m[k] * FT) : null);
    const liq = (x, k) => (x.qc[k] || 0) + (x.qr[k] || 0);
    const above = (x, k) => lv[k] <= x.psfc_hpa;
    const slwLevels = x => lv.map((_, k) => k).filter(k => x.slw[k] >= th.liquid);
    const peakOf = x => x.slw.reduce((b, v, k) => (v > (b ? b.v : 0) ? { v, k } : b), null);

    // ---- numbers: selected hour, then the 24 h from it
    if (sel) {
      const ks = slwLevels(sel), sm = sel.summit;
      set("slw-col", `${fmtCol(sel.slw_col_kg_m2)} kg/m²`);
      set("slw-col-sub", ks.length ? `${lv[ks[0]]}–${lv[ks[ks.length - 1]]} hPa, ${tC(sel.t_c[ks[0]])} to ${tC(sel.t_c[ks[ks.length - 1]])}` : `no level with ${th.liquid} g/kg or more`);
      set("slw-summit", sm ? `${fmtQ(sm.slw_g_kg)} g/kg` : "n/a");
      set("slw-summit-sub", sm ? `${tC(sm.t_c)} at ${summitFt ? `${summitFt.toLocaleString()} ft` : "the summit"} (${Math.round(sm.p_hpa)} hPa)` : `below the ${M} levels used`);
    } else {
      set("slw-col", "n/a"); set("slw-col-sub", `after the ${M} run (ends ${when(hours[n - 1].time)})`);
      set("slw-summit", "n/a"); set("slw-summit-sub", "");
    }
    const win = si >= 0 ? hours.slice(si, si + 24) : [];
    let pk = null;
    win.forEach(x => { const p = peakOf(x); if (p && (!pk || p.v > pk.v)) pk = { ...p, x }; });
    const hasPk = pk && pk.v >= th.liquid;
    set("slw-peak", hasPk ? `${fmtQ(pk.v)} g/kg` : win.length ? "none" : "n/a");
    set("slw-peak-sub", hasPk ? `${when(pk.x.time)} · ${lv[pk.k]} hPa (${(zft(pk.x, pk.k) / 1000).toFixed(1)}k ft), ${tC(pk.x.t_c[pk.k])}` : win.length ? `no level with ${th.liquid} g/kg or more` : "");
    const rimeH = win.filter(x => x.rime.some(Boolean)), maxRime = Math.max(0, ...win.map(x => x.rime_col_kg_m2 || 0));
    set("slw-rime", win.length ? `${rimeH.length} of ${win.length} h` : "n/a");
    set("slw-rime-sub", !win.length ? "" : rimeH.length ? `up to ${fmtCol(maxRime)} kg/m² of liquid in them` : "no snow or graupel in a supercooled layer");
    if (badge) {
      const [txt, cls] = !sel ? ["After the run", ""] : sel.rime.some(Boolean) ? ["Riming layer", "chip-slw"] : slwLevels(sel).length ? ["Supercooled liquid", "chip-slw"] : ["None", ""];
      badge.textContent = txt; badge.className = `chip ${cls}`.trim();
    }
    const cell = s.cell || {};
    const slwH = win.filter(x => slwLevels(x).length).length;
    const grH = win.filter(x => x.qg.some((v, k) => v >= th.snow_graupel && x.t_c[k] < 0 && above(x, k))).length;
    if (kvBox) kvBox.innerHTML = `
      <dt>Hours with supercooled liquid, 24 h from the selected hour</dt><dd>${win.length ? `${slwH} of ${win.length} h` : "n/a"}</dd>
      <dt>Hours with graupel below 0 °C, same 24 h</dt><dd>${win.length ? `${grH} h` : "n/a"}</dd>
      <dt>${M} cell (3 km)</dt><dd>${cell.lat != null ? `${cell.lat.toFixed(3)}, ${cell.lon.toFixed(3)} · terrain ${cell.terrain_ft.toLocaleString()} ft` : "n/a"}</dd>`;
    const run = s.cycle_utc ? `${M} ${s.cycle_utc.slice(11, 13)}Z ${new Date(s.cycle_utc).toLocaleDateString([], { month: "short", day: "numeric" })} run` : `${M} run`;
    const miss = (s.missing_hours || []).filter(fh => fh > hours[0].fh);
    set("slw-note", `${run}, hours ${hours[0].fh}–${hours[n - 1].fh} (fetched ${ago(s.fetched_at_utc)}), native pressure-level output on AWS, at the 3 km cell nearest the summit point (${cell.offset_km ?? "?"} km away). `
      + `Supercooled liquid: cloud water + rain water at levels colder than 0 °C and above the model terrain; the column total runs from the model surface to ${s.column_top_hpa || 450} hPa. `
      + `The snow/liquid ratios on this page come from crystal habit and temperature and leave out riming, so snow that rimes on the way down is denser than they give. Click the chart to pick an hour.`
      + (miss.length ? ` Hours not decoded (retried on the next refresh): ${miss.join(", ")}.` : "")
      + (s.status === "stale" ? ` Stale: ${s.stale_reason || "the latest fetch failed"}.` : ""));
    if (legend) legend.innerHTML = slwKey(th);

    // ---- chart: pressure levels (log p) by hour, column total below
    const W = Math.max(320, Math.round(box.clientWidth || 900)), narrow = W < 600;
    const L = narrow ? 46 : 64, R = narrow ? 36 : 50, T = 8, HH = narrow ? 200 : 236, GAP = 28, CH = narrow ? 62 : 74, AX = 32;
    const PW = W - L - R, y0c = T + HH + GAP, yAx = y0c + CH, H = yAx + AX;
    const dx = PW / n, gap = dx >= 6 ? 1 : 0;
    const X = i => L + i * dx, cx = i => (X(i) + dx / 2).toFixed(1);
    const lnp = lv.map(p => Math.log(p));
    const lo = lnp[0] + (lnp[0] - lnp[1]) / 2, hi = lnp[nl - 1] - (lnp[nl - 2] - lnp[nl - 1]) / 2;
    const Yl = l => T + HH * (l - hi) / (lo - hi);
    const Yp = p => Yl(Math.log(Math.min(Math.exp(lo), Math.max(Math.exp(hi), p))));
    const yc = lnp.map(Yl);
    const yBot = lnp.map((l, k) => Yl(k === 0 ? lo : (lnp[k - 1] + l) / 2));
    const yTop = lnp.map((l, k) => Yl(k === nl - 1 ? hi : (l + lnp[k + 1]) / 2));
    let g = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg" font-family="var(--font-sans)">
      <defs>${slwHatch("slw-hatch")}
        <clipPath id="slw-clip"><rect x="${L}" y="${T}" width="${PW}" height="${HH}"/></clipPath></defs>
      <rect x="${L}" y="${T}" width="${PW}" height="${HH}" fill="rgba(255,255,255,0.02)" stroke="rgba(255,255,255,0.08)"/>`;
    const zMed = k => { const v = hours.map(x => x.z_m[k]).filter(z => z != null).sort((a, b) => a - b); return v.length ? v[v.length >> 1] : null; };
    lv.forEach((p, k) => {
      if (p % 50) return;
      const z = zMed(k);
      g += `<line x1="${L}" x2="${L + PW}" y1="${yc[k].toFixed(1)}" y2="${yc[k].toFixed(1)}" stroke="rgba(255,255,255,0.05)"/>
        <text x="${L - 6}" y="${(yc[k] + 3).toFixed(1)}" text-anchor="end" fill="#94a3b8" font-size="10" font-family="var(--font-mono)">${p}${k === nl - 1 && !narrow ? " hPa" : ""}</text>`;
      if (z != null) g += `<text x="${L - 6}" y="${(yc[k] + 13).toFixed(1)}" text-anchor="end" fill="#64748b" font-size="8.5" font-family="var(--font-mono)">${(z * FT / 1000).toFixed(1)}k${narrow ? "" : " ft"}</text>`;
    });
    // DGZ band, under the liquid
    hours.forEach((x, i) => {
      for (let k = 0; k + 1 < nl; k++) {
        if (!above(x, k)) continue;
        const t1 = x.t_c[k], t2 = x.t_c[k + 1];
        let a = 0, b = 1;
        if (t1 === t2) { if (t1 > -12 || t1 < -18) continue; } else {
          const fa = (-12 - t1) / (t2 - t1), fb = (-18 - t1) / (t2 - t1);
          a = Math.max(0, Math.min(fa, fb)); b = Math.min(1, Math.max(fa, fb));
          if (a >= b) continue;
        }
        const ya = yc[k] + a * (yc[k + 1] - yc[k]), yb = yc[k] + b * (yc[k + 1] - yc[k]);
        g += `<rect x="${X(i).toFixed(1)}" y="${Math.min(ya, yb).toFixed(1)}" width="${(dx + 0.4).toFixed(1)}" height="${Math.abs(yb - ya).toFixed(1)}" fill="rgba(125,211,252,0.16)"/>`;
      }
    });
    // liquid by level: supercooled on the ramp, at or above 0 °C in gray; riming layers hatched
    hours.forEach((x, i) => {
      const ys = Yp(x.psfc_hpa);
      for (let k = 0; k < nl; k++) {
        const q = liq(x, k);
        if (!above(x, k) || q < th.liquid) continue;
        const y0 = yTop[k] + gap / 2, y1 = Math.min(yBot[k], ys) - gap / 2;
        if (y1 - y0 < 0.5) continue;
        const r = `x="${(X(i) + gap / 2).toFixed(1)}" y="${y0.toFixed(1)}" width="${Math.max(0.6, dx - gap).toFixed(1)}" height="${(y1 - y0).toFixed(1)}"`;
        g += `<rect ${r} fill="${x.t_c[k] < 0 ? SLW_RAMP[Math.max(0, slwBin(q))] : SLW_WARM}"/>`;
        if (x.rime[k]) g += `<rect ${r} fill="url(#slw-hatch)"/>`;
      }
    });
    // model terrain
    let terr = `M${L},${T + HH}`, edge = "";
    hours.forEach((x, i) => { const y = Yp(x.psfc_hpa).toFixed(1); terr += `L${X(i).toFixed(1)},${y}L${X(i + 1).toFixed(1)},${y}`; edge += `${i ? "L" : "M"}${X(i).toFixed(1)},${y}L${X(i + 1).toFixed(1)},${y}`; });
    g += `<path d="${terr}L${L + PW},${T + HH}Z" fill="rgba(148,163,184,0.2)"/><path d="${edge}" fill="none" stroke="rgba(203,213,225,0.35)"/>`;
    // isotherms (marching squares over the level centers, above the terrain only)
    const xs = [L, ...hours.map((_, i) => X(i) + dx / 2), L + PW];
    const tg = hours.map(x => x.t_c.map((t, k) => (above(x, k) ? t : null)));
    const grid = [tg[0], ...tg, tg[n - 1]];
    const iso = (lev, attrs) => { const d = contour(grid, xs, yc, lev); return d ? `<path d="${d}" fill="none" stroke-linecap="round" ${attrs}/>` : ""; };
    g += `<g clip-path="url(#slw-clip)">${iso(-12, 'stroke="#7dd3fc" stroke-opacity="0.7" stroke-width="1"')}${iso(-18, 'stroke="#7dd3fc" stroke-opacity="0.7" stroke-width="1"')}`
      + `${iso(-10, 'stroke="#cbd5e1" stroke-opacity="0.75" stroke-width="1.1" stroke-dasharray="4 3"')}${iso(-20, 'stroke="#cbd5e1" stroke-opacity="0.75" stroke-width="1.1" stroke-dasharray="4 3"')}`
      + `${iso(0, 'stroke="#f8fafc" stroke-opacity="0.9" stroke-width="1.6"')}</g>`;
    // isotherm labels where each one last appears: in the right margin if it reaches the end, else where it leaves the chart
    const lastCross = lev => {
      for (let i = n - 1; i >= 0; i--) {
        const x = hours[i];
        for (let k = 0; k + 1 < nl; k++) {
          if (!above(x, k)) continue;
          const a = x.t_c[k], b = x.t_c[k + 1];
          if (a !== b && (a - lev) * (b - lev) <= 0) return { i, y: yc[k] + (lev - a) / (b - a) * (yc[k + 1] - yc[k]) };
        }
      }
      return null;
    };
    const labs = [[0, "0 °C"], [-10, "−10 °C"], [-15, "DGZ"], [-20, "−20 °C"]].map(([lev, txt]) => ({ ...lastCross(lev), txt })).filter(o => o.y != null);
    const edgeLabs = labs.filter(o => o.i >= n - 2).sort((a, b) => a.y - b.y);
    edgeLabs.forEach((o, i) => { if (i && o.y - edgeLabs[i - 1].y < 11) o.y = edgeLabs[i - 1].y + 11; });
    const ink = o => (o.txt === "0 °C" ? "#e2e8f0" : "#94a3b8");
    edgeLabs.forEach(o => { g += `<text x="${L + PW + 5}" y="${(o.y + 3.5).toFixed(1)}" fill="${ink(o)}" font-size="9.5">${o.txt.replace(" °C", narrow ? "°" : " °C")}</text>`; });
    labs.filter(o => o.i < n - 2).forEach(o => {
      const x0 = Math.min(+cx(o.i) + 5, L + PW - 40);
      g += `<text x="${x0.toFixed(1)}" y="${(o.y + 3.5).toFixed(1)}" fill="${ink(o)}" font-size="9.5" stroke="#0f1726" stroke-width="3" stroke-linejoin="round" paint-order="stroke">${o.txt}</text>`;
    });
    // summit height
    const sp = hours.map((x, i) => (x.summit ? [X(i) + dx / 2, Yp(x.summit.p_hpa)] : null));
    const spd = sp.map((p, i) => (p ? `${i && sp[i - 1] ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}` : "")).join("");
    const sp0 = sp.find(Boolean);
    if (sp0) g += `<path d="${spd}" fill="none" stroke="rgba(203,213,225,0.6)" stroke-dasharray="3 3"/><text x="${L + 4}" y="${(sp0[1] - 4).toFixed(1)}" fill="#cbd5e1" font-size="9.5" font-weight="600" stroke="#0f1726" stroke-width="3" stroke-linejoin="round" paint-order="stroke">Summit${summitFt ? ` ${summitFt.toLocaleString()} ft` : ""}</text>`;
    // column total
    const cols = hours.map(x => x.slw_col_kg_m2 || 0), rimes = hours.map(x => x.rime_col_kg_m2 || 0);
    const cmax = [0.05, 0.1, 0.2, 0.25, 0.5, 1, 2, 2.5, 5, 10].find(v => v >= Math.max(...cols)) || Math.ceil(Math.max(...cols));
    const Yc = v => y0c + CH * (1 - v / cmax);
    g += `<text x="${L}" y="${y0c - 8}" fill="#cbd5e1" font-size="10" font-weight="700" letter-spacing="0.6">COLUMN SUPERCOOLED LIQUID (KG/M² = MM)</text>
      <rect x="${L}" y="${y0c}" width="${PW}" height="${CH}" fill="rgba(255,255,255,0.02)" stroke="rgba(255,255,255,0.08)"/>`;
    [0, cmax / 2, cmax].forEach(v => {
      g += `<line x1="${L}" x2="${L + PW}" y1="${Yc(v).toFixed(1)}" y2="${Yc(v).toFixed(1)}" stroke="rgba(255,255,255,${v ? 0.05 : 0.14})"/>
        <text x="${L - 6}" y="${(Yc(v) + 3.5).toFixed(1)}" text-anchor="end" fill="#94a3b8" font-size="9.5" font-family="var(--font-mono)">${+v.toFixed(3)}</text>`;
    });
    const area = vals => `M${cx(0)},${Yc(0)}${vals.map((v, i) => `L${cx(i)},${Yc(v).toFixed(1)}`).join("")}L${cx(n - 1)},${Yc(0)}Z`;
    g += `<path d="${area(cols)}" fill="${SLW_LINE}" fill-opacity="0.12"/>`;
    if (rimes.some(v => v > 0)) g += `<path d="${area(rimes)}" fill="#d67523" fill-opacity="0.45"/><path d="${area(rimes)}" fill="url(#slw-hatch)"/>`;
    g += `<path d="${cols.map((v, i) => `${i ? "L" : "M"}${cx(i)},${Yc(v).toFixed(1)}`).join("")}" fill="none" stroke="${SLW_LINE}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`;
    const imax = cols.indexOf(Math.max(...cols));
    if (cols[imax] > 0) g += `<text x="${Math.min(L + PW - 4, Math.max(L + 24, +cx(imax)))}" y="${(Yc(cols[imax]) - 5).toFixed(1)}" text-anchor="middle" fill="#e2e8f0" font-size="9.5" font-family="var(--font-mono)">${fmtCol(cols[imax])}</text>`;
    // time axis: shorter day names and sparser hour labels when the run is long for the width
    const shortDay = dx * 24 < 100, every = [narrow ? 12 : 6, 12, 24].find(h => h * dx >= 40) || 24;
    const labelAt = every === 24 ? 12 : 0;              // daily labels at noon: midnight already carries the day name
    const dayFmt = d => (shortDay ? `${d.toLocaleDateString([], { weekday: "short" })} ${d.getDate()}`
      : d.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" }));
    const firstMid = hours.findIndex(x => new Date(x.time).getHours() === 0);
    if (firstMid !== 0 && (firstMid < 0 || firstMid * dx > (shortDay ? 46 : 70))) g += `<text x="${L + 3}" y="${yAx + 26}" fill="#cbd5e1" font-size="10" font-weight="700">${dayFmt(new Date(hours[0].time))}</text>`;
    hours.forEach((x, i) => {
      const d = new Date(x.time), hr = d.getHours();
      if (hr === 0 && i > 0) g += `<line x1="${X(i).toFixed(1)}" x2="${X(i).toFixed(1)}" y1="${T}" y2="${yAx}" stroke="rgba(255,255,255,0.12)"/>`;
      if (hr === 0) g += `<text x="${(X(i) + 3).toFixed(1)}" y="${yAx + 26}" fill="#cbd5e1" font-size="10" font-weight="700">${dayFmt(d)}</text>`;
      if (hr % every === labelAt) g += `<text x="${cx(i)}" y="${yAx + 12}" text-anchor="middle" fill="#94a3b8" font-size="9.5">${d.toLocaleTimeString([], { hour: "numeric" })}</text>`;
    });
    if (si >= 0) g += `<line x1="${cx(si)}" x2="${cx(si)}" y1="${T}" y2="${yAx}" stroke="#f8fafc" stroke-opacity="0.8" stroke-width="1.5"/>`;
    g += `<line id="slw-cross" x1="0" x2="0" y1="${T}" y2="${yAx}" stroke="#fff" stroke-opacity="0.35" visibility="hidden"/>
      <rect id="slw-cell" fill="none" stroke="#f8fafc" stroke-width="1.2" visibility="hidden"/>
      <rect id="slw-hit" x="${L}" y="${T}" width="${PW}" height="${yAx - T}" fill="transparent" style="cursor:pointer"/></svg>`;
    box.innerHTML = g;

    // ---- hover: every value at the hour (and the level under the pointer); click picks the hour
    const svg = box.querySelector("svg"), hit = $("slw-hit"), cross = $("slw-cross"), cellBox = $("slw-cell"), tip = $("slw-tip"), wrap = $("slw-wrap");
    const at = ev => { const pt = svg.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY; return pt.matrixTransform(svg.getScreenCTM().inverse()); };
    const hourAt = p => Math.max(0, Math.min(n - 1, Math.floor((p.x - L) / dx)));
    hit.addEventListener("mousemove", ev => {
      const p = at(ev), i = hourAt(p), x = hours[i];
      cross.setAttribute("x1", cx(i)); cross.setAttribute("x2", cx(i)); cross.setAttribute("visibility", "visible");
      const k = p.y <= T + HH ? lv.findIndex((_, q) => p.y >= yTop[q] && p.y <= yBot[q]) : -1;
      const row = (a, b) => `<div class="tt-row"><span class="tt-label">${a}</span><span class="tt-val">${b}</span></div>`;
      const rows = [];
      if (k >= 0 && above(x, k)) {
        rows.push(row(`${lv[k]} hPa · ${zft(x, k).toLocaleString()} ft`, tC(x.t_c[k])));
        rows.push(row(x.t_c[k] < 0 ? "Supercooled liquid" : "Liquid (0 °C or warmer)", `${fmtQ(liq(x, k))} g/kg`));
        rows.push(row("cloud water · rain", `${fmtQ(x.qc[k])} · ${fmtQ(x.qr[k])}`));
        rows.push(row("snow · graupel · cloud ice", `${fmtQ(x.qs[k])} · ${fmtQ(x.qg[k])} · ${fmtQ(x.qi[k])}`));
        if (x.rime[k]) rows.push(row("Riming layer", "yes"));
        cellBox.setAttribute("x", X(i)); cellBox.setAttribute("width", dx);
        cellBox.setAttribute("y", yTop[k]); cellBox.setAttribute("height", Math.max(1, Math.min(yBot[k], Yp(x.psfc_hpa)) - yTop[k]));
        cellBox.setAttribute("visibility", "visible");
      } else {
        if (k >= 0) rows.push(row(`${lv[k]} hPa`, "below the model terrain"));
        cellBox.setAttribute("visibility", "hidden");
      }
      rows.push(row("Column supercooled liquid", `${fmtCol(x.slw_col_kg_m2)} kg/m²`));
      rows.push(row("in riming layers", `${fmtCol(x.rime_col_kg_m2)} kg/m²`));
      if (x.summit) rows.push(row(`At ${summitFt ? summitFt.toLocaleString() : "summit"} ft`, `${tC(x.summit.t_c)} · ${fmtQ(x.summit.slw_g_kg)} g/kg`));
      tip.innerHTML = `<div class="tt-time">${new Date(x.time).toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "numeric" })} · ${M} +${x.fh} h</div>${rows.join("")}`;
      tip.style.display = "block";
      const wr = wrap.getBoundingClientRect(), tw = tip.offsetWidth || 260;
      let left = ev.clientX - wr.left + 16; if (left + tw > wr.width) left = ev.clientX - wr.left - tw - 16;
      tip.style.left = `${Math.max(0, left)}px`; tip.style.top = `${Math.max(0, ev.clientY - wr.top - 30)}px`;
    });
    hit.addEventListener("mouseleave", () => { tip.style.display = "none"; cross.setAttribute("visibility", "hidden"); cellBox.setAttribute("visibility", "hidden"); });
    hit.addEventListener("click", ev => {
      const t = hours[hourAt(at(ev))].time;
      const hour = (((om().elevation_timelines || {}).summit) || []).findIndex(x => x.time === t);
      if (hour >= 0) document.dispatchEvent(new CustomEvent("snow:sethour", { detail: { hour } }));
    });

    // ---- the same numbers as a table: hours with supercooled liquid
    if (table) {
      const rowsT = hours.filter(x => slwLevels(x).length);
      table.innerHTML = rowsT.length ? `<thead><tr><th>Valid</th><th>Column</th><th>In riming layers</th><th>Peak</th><th>Levels with supercooled liquid</th><th>Graupel below 0 °C</th></tr></thead><tbody>`
        + rowsT.map(x => {
          const ks = slwLevels(x), p = peakOf(x);
          return `<tr><td>${new Date(x.time).toLocaleString([], { weekday: "short", hour: "numeric" })}<small>${M} +${x.fh} h</small></td><td><b>${fmtCol(x.slw_col_kg_m2)}</b> kg/m²</td><td>${fmtCol(x.rime_col_kg_m2)} kg/m²</td>
            <td>${fmtQ(p.v)} g/kg<small>${lv[p.k]} hPa, ${tC(x.t_c[p.k])}</small></td><td>${lv[ks[0]]}–${lv[ks[ks.length - 1]]} hPa<small>${ks.length} of ${nl} levels</small></td><td>${fmtCol(x.graupel_col_kg_m2)} kg/m²</td></tr>`;
        }).join("") + `</tbody>`
        : `<tbody><tr><td class="muted">No hour of this run has ${th.liquid} g/kg or more of supercooled liquid at the summit cell.</td></tr></tbody>`;
    }
  }

  // ---------------------------------------------------------------- sources & verification
  function renderSources() {
    if (!state.resort) return;
    const o = om(), sources = state.resort.sources || {}, nws = sources.noaa_nws || {}, cdec = sources.cdec_snotel || {}, rep = sources.resort_official || {};
    const summit = o.summit || {}, ens = summit.ensemble || {};
    const num = v => typeof v === "number" && !isNaN(v);
    const L = v => (num(v) ? U.liquid(v) : "–"), S = v => (num(v) ? U.snow(v) : "–");
    const run = r => (r && r.run_init_utc ? `${utc(r.run_init_utc)}` : (r && r.run_note) || "–");

    // models
    const rows = [];
    const cur = (o.model || {}).id;
    (o.model_comparison || o.available_models || []).forEach(m => {
      const sm = m.summary || m;
      const runs = m.members ? `latest run of each (${m.members.length} models)` : (m.runs || []).map(run).join(" / ");
      if (m.error || m.status === "error") { rows.push(`<tr><td><b>${esc(m.label)}</b></td><td>${esc(m.provider || "")}</td><td>${esc(m.grid || "")}</td><td colspan="7" class="muted">${esc(m.error || "unavailable")}</td></tr>`); return; }
      rows.push(`<tr${m.id === cur ? ' class="row-primary"' : ""}><td><b>${esc(m.label)}</b>${m.id === cur ? "<small>selected</small>" : ""}</td><td>${esc(m.provider)}</td><td>${esc(m.grid)}${m.cell_elevation_ft ? `<small>summit cell ${m.cell_elevation_ft.toLocaleString()} ft</small>` : ""}</td>
        <td>${esc(m.sounding_label || "")}${m.sounding_has_vertical_velocity || /^none/.test(m.sounding_label || "") ? "" : '<small>no vertical velocity: SLR weighted by layer depth</small>'}</td>
        <td>${runs || "–"}</td><td>${sm.hours_available ?? m.hours_available ?? "?"} h</td>
        <td>${L(sm.liquid_48h)}</td><td>${L(sm.liquid_7d)}${sm.covers_7d === false ? "<sup>†</sup>" : ""}</td>
        <td>${S(sm.snow_48h)}</td><td>${S(sm.snow_7d)}${sm.covers_7d === false ? "<sup>†</sup>" : ""}</td></tr>`);
    });
    const nwsRow = (g, label, used) => g ? rows.push(`<tr><td><b>NWS ${esc(g.wfo || "")} gridded forecast</b><small>${label} · shown separately, not blended</small></td><td>NWS ${esc(g.wfo || "")} (forecaster-edited)</td>
      <td>2.5 km${g.grid_elevation_ft || g.elevation_ft ? ` · cell ${(g.grid_elevation_ft || g.elevation_ft).toLocaleString()} ft` : ""}</td><td>–</td>
      <td>fetched ${ago(nws.fetched_at_utc)}</td><td>${g.total_through_utc ? Math.max(0, Math.round((new Date(g.total_through_utc) - Date.now()) / 3600e3)) + " h" : "~7 d"}</td><td>–</td><td>–</td><td>${S(g.next_48h_inches)}</td><td>${S(g.total_snow_inches)}</td></tr>`) : null;
    nwsRow(nws.summit_grid, "cell at the summit point", nws.snowfall_grid_used === "summit");
    nwsRow(nws.grid, "cell at the base point", nws.snowfall_grid_used !== "summit");
    if (ens.members) rows.push(`<tr><td><b>Ensembles</b><small>${ens.members} members</small></td><td>NOAA · ECMWF · DWD</td><td>GEFS · ECMWF ENS · ICON-EPS</td><td>uses selected model</td><td>latest</td><td>168 h</td>
      <td>${L(ens.liquid_48h && ens.liquid_48h.p10)}–${L(ens.liquid_48h && ens.liquid_48h.p90)}</td><td>–</td>
      <td>${S(ens.snow_48h.p10)}–${S(ens.snow_48h.p90)}</td><td>${S(ens.snow_7d.p10)}–${S(ens.snow_7d.p90)}</td></tr>`);
    $("models-table").innerHTML = `<thead><tr><th>Model</th><th>Provider</th><th>Grid</th><th>Sounding</th><th>Run (UTC)</th><th>Length</th><th>Liquid 48 h</th><th>Liquid 7 d</th><th>Snow 48 h</th><th>Snow 7 d</th></tr></thead><tbody>${rows.join("")}</tbody>`;
    const q = (o.query_points || {}).summit || {};
    $("models-sub").innerHTML = `Summit point ${q.lat ?? "?"}, ${q.lon ?? "?"} at ${(q.elevation_ft || 0).toLocaleString()} ft. Snow uses each model's own snow fraction and SLR from its sounding. NBM and ECMWF HRES are surface-only in Open-Meteo, so their soundings come from GFS and ECMWF IFS 0.25°. Select a model in the bar at the top of the page.`;
    const mfoot = $("models-foot");
    const short = (o.model_comparison || o.available_models || []).filter(m => (m.summary || m).covers_7d === false && !m.error);
    if (mfoot) {
      mfoot.hidden = !short.length;
      mfoot.textContent = short.length ? `† Run ends before 7 days (${short.map(m => `${m.label} ${(m.summary || m).hours_available ?? m.hours_available ?? "?"} h`).join(", ")}), so its 7-day total covers only the hours it has.` : "";
    }

    // SLR methods
    const sm = summit.slr_methods || {};
    const slrRow = (key, name, when) => {
      const m = sm[key] || {};
      return `<tr${key === "cobb" || key === "nbm" ? ' class="row-primary"' : ""}><td><b>${name}</b><small>${when}</small></td><td>${m.slr_48h != null ? m.slr_48h + ":1" : "–"}</td><td>${m.slr_7d != null ? m.slr_7d + ":1" : "–"}</td><td>${S(m.snow_48h)}</td><td>${S(m.snow_7d)}</td></tr>`;
    };
    const lw = (sm.cobb || {}).lift_weighted;
    if (sm.nbm) {
      $("slr-table").innerHTML = `<thead><tr><th>Method</th><th>SLR 48 h</th><th>SLR 7 d</th><th>Snow 48 h</th><th>Snow 7 d</th></tr></thead><tbody>
        ${slrRow("nbm", "NBM's own (used)", "NBM snowfall and SNOWLR fields, as published by NOAA")}
        ${slrRow("fixed_10", "Fixed 10:1", "climatological rule of thumb, for reference")}</tbody>`;
    } else
    $("slr-table").innerHTML = `<thead><tr><th>Method</th><th>SLR 48 h</th><th>SLR 7 d</th><th>Snow 48 h</th><th>Snow 7 d</th></tr></thead><tbody>
      ${slrRow("cobb", "Cobb-style (used)", lw === false ? "habit SLR of ice-saturated layers, weighted by depth (this model has no vertical velocity)" : "habit SLR of ice-saturated rising layers, weighted by lift × depth")}
      ${slrRow("experimental_adjusted", "Cobb-style + wind/near-freezing adjustment", "experimental, not calibrated; for comparison only")}
      ${slrRow("kuchera", "Kuchera", "warmest temperature below 500 hPa; used on model snowfall maps")}
      ${slrRow("fixed_10", "Fixed 10:1", "climatological rule of thumb")}
      ${slrRow("model_field_7to1", "Open-Meteo snowfall field", "the API's own snowfall variable: fixed ~7:1")}
      </tbody>`;

    // observations
    const m = cdec.measurements || {};
    const obsRows = [];
    obsRows.push(`<tr><td><b>CDEC ${esc(cdec.station_id || "")}</b><small>${esc(cdec.station_name || "")} · ${(cdec.elevation_ft || 0).toLocaleString()} ft</small></td>
      <td>Depth ${S(m.snow_depth_current_inches)} (24 h ${num(m.snow_depth_24h_gain_inches) ? "+" + U.snow(m.snow_depth_24h_gain_inches) : "–"}, 48 h ${num(m.snow_depth_48h_gain_inches) ? "+" + U.snow(m.snow_depth_48h_gain_inches) : "–"})<br>
      SWE ${L(m.swe_current_inches)} (48 h +${L(m.swe_48h_gain_inches)}) · ${tF(m.air_temperature_f)}${m.snow_to_liquid_ratio ? ` · measured SLR ${m.snow_to_liquid_ratio}:1 (settled)` : ""}</td>
      <td>${cdec.status === "success" ? "live" : esc(cdec.status)} · ${ago(cdec.fetched_at_utc || cdec.timestamp_utc)}</td></tr>`);
    ["KREV"].forEach(st => {
      const so = observed(st);
      if (!so) return;
      obsRows.push(`<tr><td><b>Radiosonde ${st}</b><small>${esc(so.name || "")}</small></td><td>${so.levels ? `${so.levels.length} levels, valid ${utc(so.valid_utc)}` : esc(so.error_message || "unavailable")}</td>
        <td>${esc(so.status)} · ${ago(so.fetched_at_utc)}</td></tr>`);
    });
    const ra = rep.snow_areas || {};
    const areaTxt = t => { const a = ra[t] || {}; return a.new_7d_in == null && a.base_depth_in == null ? "" : `${t} ${a.elevation_ft ? a.elevation_ft.toLocaleString() + " ft" : ""}: 24 h ${S(a.new_24h_in)}, 72 h ${S(a.new_72h_in)}, 7 d ${S(a.new_7d_in)}, depth ${S(a.base_depth_in)}`; };
    obsRows.push(`<tr><td><b>Resort snow report</b><small>MtnPowder feed (resort widget)</small></td>
      <td>${["success", "stale"].includes(rep.status) ? `${["base", "mid"].map(areaTxt).filter(Boolean).join("<br>")}<br>Storm ${S(rep.storm_total_in)} · season ${S(rep.season_total_in)} · report updated ${pst(rep.report_updated)}` : esc(rep.error_message || "unavailable")}</td>
      <td>${esc(rep.status || "unavailable")} · ${ago(rep.fetched_at_utc)}</td></tr>`);
    $("obs-table").innerHTML = `<thead><tr><th>Source</th><th>Latest values</th><th>Status</th></tr></thead><tbody>${obsRows.join("")}</tbody>`;

    // resort weather stations vs. model, current hour
    const st = rep.weather_stations || {};
    const tl0 = t => ((o.elevation_timelines || {})[t] || [])[0] || {};
    // free-air temperature at the station's own height, from the model column for the same hour
    const col0 = (() => {
      const t0 = (tl0("summit") || {}).time;
      const sh = (o.sounding_hourly || []).find(x => x.time === t0) || (o.sounding_hourly || [])[0];
      const lv = sh ? (sh.levels || []).map(l => ({ z: l[1], t: l[2] })).filter(l => l.z != null && l.t != null).sort((a, b) => a.z - b.z) : [];
      lv.ground = sh ? sh.ground_m : null;
      return lv;
    })();
    const freeAirF = ft => {
      if (!col0.length || ft == null) return null;
      const z = ft * 0.3048;
      if (col0.ground != null && z < col0.ground - 50) return "below";   // under the model's terrain: no free air there
      if (z <= col0[0].z) return col0[0].t * 9 / 5 + 32;
      for (let i = 1; i < col0.length; i++) if (z <= col0[i].z) {
        const a = col0[i - 1], b = col0[i];
        return (a.t + (b.t - a.t) * (z - a.z) / Math.max(1e-6, b.z - a.z)) * 9 / 5 + 32;
      }
      return null;
    };
    const colLabel = (o.profile_model || {}).label || ((o.model || {}).label);
    const ceil = ((state.resort.sources || {}).noaa_nws || {}).ceiling_obs || {};
    const ceilTxt = ceil.status === "success" ? (ceil.ceiling_msl_ft != null ? `ceiling ${ceil.ceiling_msl_ft.toLocaleString()} ft (${{ BKN: "broken", OVC: "overcast", VV: "obscured" }[ceil.ceiling_amount] || ceil.ceiling_amount})`
      : ceil.layers && ceil.layers.length ? `no ceiling; lowest clouds ${ceil.layers[0].base_msl_ft.toLocaleString()} ft` : "no ceiling") : null;
    const windTxt = (dir, sp, gu) => `${dir ? dir + " " : ""}${sp != null ? Math.round(sp) : "–"} mph (gust ${gu != null ? Math.round(gu) : "–"})`;
    const stRows = ["summit", "mid", "base"].filter(t => st[t]).map(t => {
      const w = st[t], m = tl0(t), diff = (a, b) => (a != null && b != null ? `${a - b > 0 ? "+" : ""}${Math.round(a - b)}` : "–");
      const nm = String(w.name || t).replace(/,?\s*el\.\s*[\d,]+'?\s*$/i, "");
      const at = w.observed_at ? new Date(String(w.observed_at).replace(/([+-]\d{2})(\d{2})$/, "$1:$2")) : null;
      const fa = freeAirF(w.elevation_ft);
      return `<tr><td><b>${esc(nm)}</b><small>${w.elevation_ft ? w.elevation_ft.toLocaleString() + " ft · " : ""}observed ${at && !isNaN(at) ? at.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "n/a"}</small></td>
        <td>${tF(w.temp_f)} <small>model 2 m ${tF(m.temp_f)} (Δ ${diff(w.temp_f, m.temp_f)}°F)</small></td>
        <td>${fa === "below" ? `<small>below the column's terrain (${Math.round(col0.ground * 3.28084).toLocaleString()} ft)</small>` : fa != null ? `${tF(fa)} <small>Δ ${diff(w.temp_f, fa)}°F</small>` : "–"}</td>
        <td>${tF(w.dew_point_f)} <small>model ${tF(m.dew_point_f)}</small></td>
        <td>${windTxt(w.wind_dir, w.wind_mph, w.gust_mph)} <small>model ${windTxt(m.wind_dir_deg != null ? compass16(m.wind_dir_deg) : "", m.wind_mph, m.gust_mph)}</small></td>
        <td>${esc(w.skies || "")}${ceilTxt ? `<small>${esc(ceilTxt)}</small>` : ""}<small>model cloud ${m.cloud_cover_pct != null ? Math.round(m.cloud_cover_pct) + "%" : "–"}</small></td></tr>`;
    });
    const stEl = $("stations-table");
    const stSub = $("stations-sub");
    if (stSub) {
      const qp = o.query_points || {};
      const tiers = ["base", "mid", "summit"].filter(t => st[t] && qp[t]).map(t => `${t} ${(qp[t].elevation_ft || 0).toLocaleString()} ft`);
      stSub.textContent = `Measured at the resort's own stations. Model 2 m values are ${(o.model || {}).label || "the selected forecast"}'s first hour at the matching tier${tiers.length ? ` (${tiers.join(", ")})` : ""}. Free air is the ${colLabel || "model"} column's temperature at each station's height, same hour. Δ is station minus model.`;
    }
    if (stEl) stEl.innerHTML = stRows.length ? `<thead><tr><th>Resort station</th><th>Temperature</th><th>Free air</th><th>Dew point</th><th>Wind (gust)</th><th>Sky</th></tr></thead><tbody>${stRows.join("")}</tbody>${ceil.status === "success" ? `<tfoot><tr><td colspan="6" class="muted">Ceiling: ${esc(ceil.name)} (${esc(ceil.station)}, ${ceil.elevation_ft ? ceil.elevation_ft.toLocaleString() + " ft, " : ""}nearest cloud-base sensor; the resort stations don't measure it), observed ${new Date(ceil.observed_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}. Heights are above sea level.${ceil.layers && ceil.layers.length ? ` Layers: ${ceil.layers.map(l => `${l.amount} ${l.base_msl_ft != null ? l.base_msl_ft.toLocaleString() + " ft" : "?"}`).join(", ")}.` : ""}</td></tr></tfoot>` : ""}`
      : `<tbody><tr><td class="muted">Resort weather stations unavailable.</td></tr></tbody>`;

    // verification
    const hist = (((typeof snowData !== "undefined" && snowData) || {}).verification || {}).history || [];
    const mine = hist.filter(h => h.resort_id === state.resort.id);
    $("verify-table").innerHTML = mine.length ? `<thead><tr><th>Forecast issued</th><th>Sensor</th><th>Liquid fcst / measured</th><th>Error</th><th>Snow fcst (method used then)</th><th>Kuchera</th><th>10:1</th><th>Depth change</th><th>Resort reported</th><th>Notes</th></tr></thead><tbody>` +
      mine.map(h => `<tr><td>${pst(h.issued_utc)}<small>window ${pst(h.window_start_utc)} – ${pst(h.window_end_utc)}</small></td>
        <td>${esc(h.station)} ${h.elevation_ft ? `${h.elevation_ft.toLocaleString()} ft` : ""}</td>
        <td>${L(h.forecast_liquid_in)} / ${L(h.observed_swe_gain_in)}</td>
        <td class="${Math.abs(h.liquid_error_pct || 0) > 25 ? "bad" : ""}">${h.liquid_error_pct != null ? (h.liquid_error_pct > 0 ? "+" : "") + h.liquid_error_pct + "%" : "–"}</td>
        <td>${S(h.forecast_snow_in.primary)}</td><td>${S(h.forecast_snow_in.kuchera)}</td><td>${S(h.forecast_snow_in.fixed_10)}</td>
        <td>${num(h.observed_depth_gain_in) ? (h.observed_depth_gain_in >= 0 ? "+" : "") + U.snow(h.observed_depth_gain_in) : "–"}${h.observed_slr_settled ? `<small>${h.observed_slr_settled}:1 settled</small>` : ""}</td>
        <td>${h.resort_report ? `mid 7 d ${S((h.resort_report.mid || {}).new_7d_in)} · storm ${S(h.resort_report.storm_total_in)}<small>as of ${pst(h.resort_report.as_of_utc)}; rolling totals, may include snow outside the window</small>` : "–"}</td>
        <td class="muted">${esc(h.proxy || h.model || "")}</td></tr>`).join("") + `</tbody>`
      : `<tbody><tr><td class="muted">No completed 48 h windows yet. The first verification appears 48 h after the first archived run.</td></tr></tbody>`;

    // query points
    const pts = o.query_points || {};
    const prow = (name, p, extra) => `<tr><td><b>${name}</b></td><td>${p.lat != null ? `${(+p.lat).toFixed(4)}, ${(+p.lon).toFixed(4)}` : "–"}</td><td>${p.elevation_ft ? p.elevation_ft.toLocaleString() + " ft" : "–"}</td><td class="muted">${esc(p.note || "")}</td><td>${extra}</td></tr>`;
    const tierUse = "Model grid-cell fields; temperature and dew point moved to this elevation along the model's own column";
    const sp = o.sensor_point || {};
    $("points-table").innerHTML = `<thead><tr><th>Point</th><th>Lat, lon</th><th>Elevation used</th><th>Location</th><th>Used for</th></tr></thead><tbody>
      ${prow("Base", pts.base || {}, tierUse)}${prow("Mid", pts.mid || {}, tierUse)}${prow("Summit", pts.summit || {}, tierUse + "; model sounding, model comparison, NWS grid")}
      ${o.nbm_grid_points ? ["base", "mid", "summit"].map(t => {
        const a = (o.nbm_elevation_adjustment || {})[t];
        const gp = o.nbm_grid_points[t];
        const note = a ? `line fit every hour through ${a.neighbors} surrounding 2.5 km cells (terrain ${a.neighbor_elevation_ft[0].toLocaleString()}–${a.neighbor_elevation_ft[1].toLocaleString()} ft, from the NWS grid), evaluated at the tier height; nearest cell ${a.grid_elevation_ft.toLocaleString()} ft at ${gp.grid_lat}, ${gp.grid_lon}${a.extrapolation_ft > 50 ? `; the tier is ${a.extrapolation_ft} ft ${a.target_elevation_ft > a.neighbor_elevation_ft[1] ? "above the highest" : "below the lowest"} cell, so the line is extended that far past the data` : ""}; median temperature lapse ${a.lapse_f_per_kft ? a.lapse_f_per_kft.median : "?"} °F/1,000 ft`
          : "nearest 2.5 km NBM grid point; values are for this cell's terrain";
        return prow(`NBM (${t})`, { lat: a ? (pts[t] || {}).lat : gp.grid_lat, lon: a ? (pts[t] || {}).lon : gp.grid_lon, elevation_ft: a ? a.target_elevation_ft : gp.grid_elevation_ft, note },
          a ? `7-day snow ${U.snow(a.snow_total_grid_in)} at the cell → ${U.snow(a.snow_total_adjusted_in)} at ${a.target_elevation_ft.toLocaleString()} ft` : "NBM values for this tier");
      }).join("") : ""}
      ${prow(`Sensor ${esc(sp.id || cdec.station_id || "")}`, { lat: cdec.latitude ?? sp.lat, lon: cdec.longitude ?? sp.lon, elevation_ft: cdec.elevation_ft, note: cdec.location_note || "CDEC-listed elevation" }, "Forecast at the sensor for verification")}
      ${prow(`NWS ${(nws.grid || {}).wfo || ""} base cell`, { lat: (nws.grid || {}).lat, lon: (nws.grid || {}).lon, elevation_ft: (nws.grid || {}).elevation_ft, note: `grid ${(nws.grid || {}).x ?? ""},${(nws.grid || {}).y ?? ""}; 2.5 km cell mean elevation` }, "Alerts, Area Forecast Discussion, base snowfall")}
      ${nws.summit_grid ? prow(`NWS ${nws.summit_grid.wfo} summit cell`, { lat: nws.summit_grid.lat, lon: nws.summit_grid.lon, elevation_ft: nws.summit_grid.grid_elevation_ft, note: `grid ${nws.summit_grid.x},${nws.summit_grid.y}; the crest is the REV/STO office boundary` }, "Summit-cell gridded snowfall, shown beside the model forecast (not blended)") : ""}
      </tbody>`;
    const ea = o.elevation_adjustment || {};
    const cellTxt = ["base", "mid", "summit"].filter(t => ea[t] && ea[t].cell_elevation_ft).map(t => {
      const a = ea[t], sh = a.temp_shift_f || {};
      return `${t}: cell ${a.cell_elevation_ft.toLocaleString()} ft, shift ${sh.median > 0 ? "+" : ""}${sh.median ?? "?"}°F (fixed 6.5 °C/km would be ${a.fixed_lapse_shift_f > 0 ? "+" : ""}${a.fixed_lapse_shift_f}°F)`;
    });
    $("points-sub").textContent = "Each tier is queried at its own coordinates. Open-Meteo models: the model's own grid-cell values (no Open-Meteo downscaling); the cell's height comes from its surface pressure on the model column, and temperature and dew point are moved to the tier height by the column's own change between the two heights, so inversions the model has are kept."
      + (cellTxt.length ? ` ${(o.model || {}).label || "This model"}, median of the first 24 h: ${cellTxt.join("; ")}.` : "")
      + " NBM: a line fit through the surrounding NBM cells, evaluated at the tier height. Precipitation is not elevation-adjusted for Open-Meteo models; wind uses pressure-level data at the tier height (summit) or the 10 m model wind (base).";
  }

  // ---------------------------------------------------------------- elevation bands
  const TIER_COLOR = { base: "#fbbf24", mid: "#c084fc", summit: "#38bdf8" };
  function renderBands() {
    const box = $("bands-chart");
    if (!box || !state.resort) return;
    const o = om(), tls = o.elevation_timelines || {}, elevs = state.resort.elevations || {};
    const tiers = ["base", "mid", "summit"].filter(t => (tls[t] || []).length);
    if (!tiers.length) { box.innerHTML = ""; return; }
    const n = Math.max(...tiers.map(t => tls[t].length));
    const time = tls[tiers[tiers.length - 1]].map(x => x.time);
    const hasVis = tiers.some(t => tls[t].some(x => x.visibility_mi != null));
    const W = 1040, L = 56, R = 96, PW = W - L - R, step = PW / n;
    const X = i => L + (i + 0.5) * step;
    const panels = [
      { key: "t", title: `TEMPERATURE (°${U.celsius() ? "C" : "F"})`, h: 150 },
      { key: "rh", title: "RELATIVE HUMIDITY AT 2 M (%)", h: 100 },
      { key: "vis", title: "VISIBILITY (MI, CAPPED AT 10)", h: 90 },
    ];
    let y = 8; panels.forEach(p => { p.top = y + 16; y += 16 + p.h + 26; });
    const axisY = y - 14, H = axisY + 30;
    const tv = f => (f == null ? null : U.tempNum(f));
    let s = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" font-family="var(--font-sans)">`;
    time.forEach((t, i) => { if (new Date(t).getHours() === 0 && i) s += `<line x1="${L + i * step}" x2="${L + i * step}" y1="${panels[0].top - 4}" y2="${axisY}" stroke="rgba(255,255,255,0.1)" stroke-dasharray="2 3"/>`; });
    const path = (arr, Y) => { let d = "", pen = false; arr.forEach((v, i) => { if (v == null) { pen = false; return; } d += `${pen ? "L" : "M"}${X(i).toFixed(1)},${Y(v).toFixed(1)} `; pen = true; }); return d; };
    panels.forEach(p => {
      s += `<text x="${L}" y="${p.top - 6}" fill="#cbd5e1" font-size="10" font-weight="700" letter-spacing="0.6">${p.title}</text>`;
      let lo, hi, series = [];
      if (p.key === "t") {
        tiers.forEach(t => { series.push({ t, v: tls[t].map(x => tv(x.temp_f)), dash: false }); series.push({ t, v: tls[t].map(x => tv(x.free_air_temp_f)), dash: true }); });
        const fixedT = (o.scales || {}).temp_f;
        const all = fixedT ? fixedT.map(tv) : series.flatMap(x => x.v).filter(v => v != null);
        lo = Math.floor(Math.min(...all) / 5) * 5; hi = Math.ceil(Math.max(...all) / 5) * 5; if (hi - lo < 10) hi = lo + 10;
      } else if (p.key === "rh") {
        tiers.forEach(t => series.push({ t, v: tls[t].map(x => x.relative_humidity_pct), dash: false })); lo = 0; hi = 100;
      } else {
        tiers.forEach(t => series.push({ t, v: tls[t].map(x => (x.visibility_mi == null ? null : Math.min(10, x.visibility_mi))), dash: false })); lo = 0; hi = 10;
      }
      const Y = v => p.top + p.h * (1 - (v - lo) / (hi - lo));
      const stepT = p.key === "t" ? (hi - lo > 40 ? 10 : 5) : p.key === "rh" ? 25 : 2.5;
      for (let v = lo; v <= hi + 1e-6; v += stepT) {
        s += `<line x1="${L}" x2="${L + PW}" y1="${Y(v)}" y2="${Y(v)}" stroke="rgba(255,255,255,${v === lo ? 0.16 : 0.05})"/>
          <text x="${L - 8}" y="${Y(v) + 3.5}" fill="#94a3b8" font-size="10" text-anchor="end" font-family="var(--font-mono)">${v}</text>`;
      }
      if (p.key === "t") { const fz = U.celsius() ? 0 : 32; if (fz > lo && fz < hi) s += `<line x1="${L}" x2="${L + PW}" y1="${Y(fz)}" y2="${Y(fz)}" stroke="#fbbf24" stroke-opacity=".5" stroke-dasharray="5 4"/><text x="${L + 4}" y="${Y(fz) - 4}" fill="#fcd34d" font-size="9.5">${U.celsius() ? "0 °C" : "32 °F"}</text>`; }
      if (p.key === "vis" && !hasVis) { s += `<text x="${L + PW / 2}" y="${p.top + p.h / 2}" text-anchor="middle" fill="#64748b" font-size="11">This model does not provide visibility.</text>`; return; }
      const labels = [];
      // resort station readings at hour 0 (temperature and humidity panels)
      if (p.key === "t" || p.key === "rh") {
        ["base", "mid", "summit"].forEach(t => {
          const ob = window.Obs ? Obs.forTier(state.resort, t) : null;
          if (!ob) return;
          const v = p.key === "t" ? tv(ob.temp_f) : ob.humidity_pct;
          if (v == null) return;
          s += `<rect x="${X(0) - 4}" y="${Y(v) - 4}" width="8" height="8" transform="rotate(45 ${X(0)} ${Y(v)})" fill="${TIER_COLOR[t]}" stroke="#0b1220" stroke-width="1.2"><title>${t} station ${p.key === "t" ? tF(ob.temp_f) : Math.round(v) + "%"} at ${ob.observed.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</title></rect>`;
        });
      }
      series.forEach(se => {
        s += `<path d="${path(se.v, Y)}" fill="none" stroke="${TIER_COLOR[se.t]}" stroke-width="${se.dash ? 1.4 : 2}" ${se.dash ? 'stroke-dasharray="5 4" opacity="0.75"' : ""}/>`;
        if (!se.dash) {
          const lastI = se.v.map((v, i) => (v == null ? -1 : i)).reduce((a, b) => Math.max(a, b), -1);
          if (lastI >= 0) { let ly = Y(se.v[lastI]) + 4; labels.forEach(o2 => { if (Math.abs(o2 - ly) < 11) ly = o2 + 11; }); labels.push(ly);
            s += `<text x="${L + PW + 6}" y="${ly}" fill="${TIER_COLOR[se.t]}" font-size="10" font-weight="700">${{ base: "Base", mid: "Mid", summit: "Summit" }[se.t]}</text>`; }
        }
      });
    });
    time.forEach((t, i) => {
      const d = new Date(t);
      if (i % (n > 72 ? 12 : 3) === 0) s += `<text x="${X(i)}" y="${axisY + 12}" fill="#94a3b8" font-size="10" text-anchor="middle">${d.toLocaleTimeString([], { hour: "numeric" })}</text>`;
      if (d.getHours() === 0) s += `<text x="${L + i * step + 2}" y="${axisY + 26}" fill="#cbd5e1" font-size="10" font-weight="700">${d.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" })}</text>`;
    });
    s += `<line id="bands-cross" x1="0" x2="0" y1="${panels[0].top}" y2="${axisY}" stroke="#fff" stroke-opacity=".45" visibility="hidden"/>
      <rect id="bands-hit" x="${L}" y="${panels[0].top}" width="${PW}" height="${axisY - panels[0].top}" fill="transparent" style="cursor:crosshair"/></svg>`;
    box.innerHTML = s;
    const sub = $("bands-sub");
    const anyObs = window.Obs && ["base", "mid", "summit"].some(t => Obs.forTier(state.resort, t));
    const pmB = o.profile_model;
    if (sub) sub.textContent = `${(o.primary_model || {}).label || ""}. Solid: 2 m values at each tier (${o.nbm_elevation_adjustment ? "NBM cells moved to the tier height with NBM's own hourly elevation relationship" : "the model's grid-cell value moved to the tier height along the model's own column"}). Dashed: free-air temperature at the same height in the ${pmB ? pmB.label : "model"} column. Where they diverge (inversions, valley cold pools) the station readings show which one matched.${anyObs ? " Diamonds at the left edge: resort station readings now." : ""}`;

    const svg = box.querySelector("svg"), hit = $("bands-hit"), cross = $("bands-cross"), tip = $("bands-tip");
    hit.addEventListener("mousemove", ev => {
      const pt = svg.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY;
      const loc = pt.matrixTransform(svg.getScreenCTM().inverse());
      const i = Math.max(0, Math.min(n - 1, Math.floor((loc.x - L) / step)));
      cross.setAttribute("x1", X(i)); cross.setAttribute("x2", X(i)); cross.setAttribute("visibility", "visible");
      const row = t => { const x = (tls[t] || [])[i] || {}; return `<div class="tt-row"><span class="tt-label" style="color:${TIER_COLOR[t]}">${{ base: "Base", mid: "Mid", summit: "Summit" }[t]} ${(elevs[`${t}_ft`] || 0).toLocaleString()} ft</span>
        <span class="tt-val">${tF(x.temp_f)} (free air ${tF(x.free_air_temp_f)}) · RH ${x.relative_humidity_pct ?? "–"}% · vis ${x.visibility_mi != null ? (x.visibility_mi >= 10 ? "10+" : x.visibility_mi.toFixed(1)) + " mi" : "–"}</span></div>`; };
      tip.innerHTML = `<div class="tt-time">${new Date(time[i]).toLocaleString([], { weekday: "short", month: "short", day: "numeric", hour: "numeric" })}</div>${["summit", "mid", "base"].filter(t => tls[t]).map(row).join("")}`;
      tip.style.display = "block";
      const wrap = $("bands").getBoundingClientRect(), tw = tip.offsetWidth || 300;
      let left = ev.clientX - wrap.left + 16; if (left + tw > wrap.width) left = ev.clientX - wrap.left - tw - 16;
      tip.style.left = `${Math.max(0, left)}px`; tip.style.top = `${ev.clientY - wrap.top - 40}px`;
    });
    hit.addEventListener("mouseleave", () => { tip.style.display = "none"; cross.setAttribute("visibility", "hidden"); });
  }

  // ---------------------------------------------------------------- wiring
  function renderAll() { renderSkewT(); renderHabit(); renderPhase(); renderDGZ(); renderSLW(); renderMoisture(); renderSources(); renderBands(); }

  // ---------------------------------------------------------------- moisture and crest wind (follows the slider)
  const mixingRatio = (tdf, ft) => {
    if (tdf == null || ft == null) return null;
    const td = (tdf - 32) * 5 / 9, p = 1013.25 * Math.pow(1 - 2.25577e-5 * ft * 0.3048, 5.25588), e = esW(td);
    return 621.97 * e / Math.max(1, p - e);
  };
  const flowClass = deg => deg == null ? null : (deg >= 200 && deg <= 290 ? "upslope (within 45° of crest-normal)" : deg >= 160 && deg <= 320 ? "oblique" : "downslope / parallel");
  const moistCat = mr => mr == null ? null : mr >= 5 ? "high (≥ 5 g/kg)" : mr >= 2.5 ? "moderate (2.5–5 g/kg)" : "low (< 2.5 g/kg)";
  const compass16 = deg => ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"][Math.round(deg / 22.5) % 16];
  function renderMoisture() {
    if (!state.resort) return;
    const r = state.resort, o = om(), tls = o.elevation_timelines || {}, el = r.elevations || {}, h = state.hour;
    const set = (id, v, html) => { const e = $(id); if (e) e[html ? "innerHTML" : "textContent"] = v; };
    const b = (tls.base || [])[h] || {}, s = (tls.summit || [])[h] || {};
    const obB = h === 0 && window.Obs ? Obs.forTier(r, "base") : null, obS = h === 0 && window.Obs ? Obs.forTier(r, "summit") : null;
    const mr = obB ? mixingRatio(obB.dew_point_f, obB.elevation_ft || el.base_ft) : (b.mixing_ratio_g_kg ?? mixingRatio(b.dew_point_f, el.base_ft));
    const dirDeg = { N: 0, NNE: 22.5, NE: 45, ENE: 67.5, E: 90, ESE: 112.5, SE: 135, SSE: 157.5, S: 180, SSW: 202.5, SW: 225, WSW: 247.5, W: 270, WNW: 292.5, NW: 315, NNW: 337.5 };
    const wind = obS ? obS.wind_mph : s.wind_mph, wdir = obS ? dirDeg[obS.wind_dir] : s.wind_dir_deg;
    set("mixing-ratio-val", mr != null ? `${mr.toFixed(1)}${obB ? "*" : ""}<small>g/kg mixing ratio</small>` : "--", true);
    set("moisture-cat-val", moistCat(mr) || "--");
    const mk = $("mr-marker"); if (mk && mr != null) mk.style.left = `calc(${Math.min(100, (mr / 8) * 100)}% - 2px)`;
    set("crest-jet-val", wind != null ? `${Math.round(wind)} mph${wdir != null ? ` from ${Math.round(wdir)}° (${compass16(wdir)})` : ""}${obS ? "*" : ""}` : "--");
    const fc = flowClass(wdir);
    set("oro-lift-val", fc || "--");
    set("oro-chip", fc ? fc.split(" (")[0] : "--");
    const next = (tls.base || []).slice(h, h + 24), nextS = (tls.summit || []).slice(h, h + 24);
    const mrs = next.map(x => x.mixing_ratio_g_kg ?? mixingRatio(x.dew_point_f, el.base_ft)).filter(v => v != null);
    const ws = nextS.map(x => x.wind_mph).filter(v => v != null);
    set("moist-24h-val", mrs.length ? `${(mrs.reduce((a, v) => a + v, 0) / mrs.length).toFixed(1)} g/kg · ${ws.length ? Math.round(ws.reduce((a, v) => a + v, 0) / ws.length) : "?"} mph` : "--");
    set("moisture-desc", `Water-vapor mixing ratio at the base for the selected hour${obB ? " (* resort station reading at hour 0)" : ""}. Higher values mean more water available for precipitation and usually denser snow.`);
  }
  window.Panels = {
    onHour(h) { state.hour = h; renderPhase(); renderDGZ(); renderSLW(); renderHabit(); renderMoisture(); if (state.skewSrc === "model") renderSkewT(); },
  };
  document.addEventListener("snow:render", e => { state.resort = e.detail.resort; renderAll(); });
  document.addEventListener("snow:prefs", () => { if (state.resort) renderAll(); });
  let rsz = null;
  window.addEventListener("resize", () => { clearTimeout(rsz); rsz = setTimeout(() => { if (state.resort) { renderPhase(); renderDGZ(); renderSLW(); } }, 180); });
  document.addEventListener("DOMContentLoaded", () => {
    const seg = $("skewt-source");
    seg && seg.addEventListener("click", ev => {
      const b = ev.target.closest(".seg-btn"); if (!b) return;
      seg.querySelectorAll(".seg-btn").forEach(x => x.classList.toggle("active", x === b));
      state.skewSrc = b.dataset.src; renderSkewT();
    });
    const slwSeg = $("slw-model");
    slwSeg && slwSeg.addEventListener("click", ev => {
      const b = ev.target.closest(".seg-btn"); if (!b || b.dataset.model === state.slwModel) return;
      state.slwModel = b.dataset.model;
      try { localStorage.setItem("slwModel", state.slwModel); } catch (e) { /* no storage: choice lasts this visit */ }
      if (state.resort) renderSLW();
    });
  });
})();
