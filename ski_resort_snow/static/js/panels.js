/**
 * Sierra Snow: analysis panels
 *  - Skew-T log-P (model sounding at the selected hour, or observed REV/OAK radiosonde)
 *  - Ice-crystal habit diagram (temperature vs. ice supersaturation) with model levels
 *  - Precipitation type by elevation (vertical) + T / Tw / T-Td table per tier
 *  - Route shields (Interstate, US, California)
 *  - Sources & verification tables
 */
(() => {
  const $ = id => document.getElementById(id);
  const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const FT = 3.28084;
  const state = { resort: null, hour: 0, skewSrc: "model" };

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
    return rec ? { time: rec.time, levels: rec.levels } : null;
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
    hit.addEventListener("mousemove", ev => {
      const pt = svg.createSVGPoint(); pt.x = ev.clientX; pt.y = ev.clientY;
      const loc = pt.matrixTransform(svg.getScreenCTM().inverse());
      const p = pAt(loc.y);
      cross.setAttribute("y1", loc.y); cross.setAttribute("y2", loc.y); cross.setAttribute("visibility", "visible");
      const interp = idx => { for (let i = 0; i < lv.length - 1; i++) { const a = lv[i], b = lv[i + 1]; if (p <= a[0] && p >= b[0] && a[idx] != null && b[idx] != null) { const f = (Math.log(p) - Math.log(a[0])) / (Math.log(b[0]) - Math.log(a[0])); return a[idx] + f * (b[idx] - a[idx]); } } return null; };
      const t = interp(2), td = interp(3), z = interp(1), ws = interp(5), wd = interp(4), w = hasW ? interp(6) : null;
      const rh = t != null && td != null ? rhFrom(t, td) : null;
      out.innerHTML = `<b>${Math.round(p)} hPa</b> · ${z != null ? `${Math.round(z * FT).toLocaleString()} ft` : ""}${groundP && p > groundP ? " (below base)" : ""}<br>
        T ${tC(t)} · Td ${tC(td)} · Tw ${t != null && td != null ? tC(wetBulbP(t, td, p)) : "--"}<br>
        T−Td ${t != null && td != null ? (U.celsius() ? `${(t - td).toFixed(1)} °C` : `${((t - td) * 1.8).toFixed(0)} °F`) : "--"} · RH ${rh != null ? Math.round(rh) : "--"}% (ice ${t != null && td != null ? Math.round(rhIce(t, td)) : "--"}%)<br>
        Wind ${wd != null ? Math.round(wd) + "°" : "--"} ${ws != null ? Math.round(ws) + " mph" : ""}${w != null ? ` · vertical motion ${w > 0 ? "+" : ""}${w.toFixed(0)} cm/s` : ""}`;
    });
    hit.addEventListener("mouseleave", () => cross.setAttribute("visibility", "hidden"));
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
        const [p, , t, td] = l;
        if (td == null || t > 0 || t < -30 || (baseP && p > baseP)) return;
        const si = rhIce(t, td) - 100;
        si >= 0 ? sup++ : sub++;
        s += `<circle cx="${X(si)}" cy="${Y(t)}" r="3.6" fill="none" stroke="#f9a8d4" stroke-width="1.4"/>
          <text x="${X(si) + 6}" y="${Y(t) - 4}" fill="#f9a8d4" font-size="9" font-family="var(--font-mono)">${p}</text>`;
      });
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
      <ul class="habit-tiers">${pts.slice().reverse().map(pt => `<li><i style="background:${COL[pt.t]}">${pt.t[0].toUpperCase()}</i><b>${{ base: "Base", mid: "Mid", summit: "Summit" }[pt.t]}${pt.ft ? ` ${pt.ft.toLocaleString()} ft` : ""}</b>
        ${U.temp(pt.tf)}${pt.obs ? "*" : ""} (${pt.tc.toFixed(1)} °C)${pt.si != null ? `, ${pt.si >= 0 ? "+" : ""}${pt.si.toFixed(1)}% over ice` : ""} → <b>${esc(pt.habit ? pt.habit.name : "–")}</b></li>`).join("")}</ul>
      <p class="habit-status">${m ? `${new Date(m.time).toLocaleString([], { weekday: "short", hour: "numeric" })}. Circles: tiers (2 m values of ${esc(((om().model || {}).label) || "the selected model")}${pts.some(p => p.obs) ? "; * resort station readings at hour 0" : ""}). Rings: ${(om().profile_model || {}).label || "model"} column levels between 0 and −30 °C above the base, labeled in hPa (${sup} ice-supersaturated, ${sub} subsaturated). Snow reaching a tier mostly grew in the cloud layers above it, so the rings show where today's crystals form; the tier circle shows how they change on the way down.` : `No model profile for ${esc(((om().model || {}).label) || "this model")}; tier circles only.`}</p>`;
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
    const H = 300, T = 24, B = 10, PH = H - T - B;
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
    s += cols.map(([lbl], i) => `<text x="${i === 4 ? colX[i] - cols[i][1] + 6 : colX[i]}" y="12" text-anchor="${i === 4 ? "start" : "end"}" fill="#64748b" font-size="10.5" font-weight="600">${lbl}</text>`).join("");
    if (narrow) s += `<text x="${tblX}" y="12" fill="#64748b" font-size="10.5" font-weight="600">Tier</text>`;

    // rows positioned at their elevation, spread so they never overlap
    const tiers = ["summit", "mid", "base"].filter(t => elevs[`${t}_ft`]);
    const rows = tiers.map(t => ({ t, ft: elevs[`${t}_ft`], y: Y(elevs[`${t}_ft`]) }));
    const gapY = 36;
    rows.forEach((rw, i) => { rw.ry = Math.max(rw.y, T + 14, i ? rows[i - 1].ry + gapY : 0); });
    const over = rows.length ? rows[rows.length - 1].ry - (H - 22) : 0;
    if (over > 0) rows.forEach(rw => { rw.ry -= over; });
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
    if (badge) { badge.textContent = { act: "Saturated and rising", sat: "Ice-saturated, weak lift", dry: "Subsaturated", none: "Not found" }[k]; badge.className = "chip " + (k === "act" ? "chip-ice" : ""); }
    set("dgz-height", p.dgz_base_ft != null ? `${(p.dgz_base_ft / 1000).toFixed(1)}–${(p.dgz_top_ft / 1000).toFixed(1)}k ft` : "n/a");
    set("dgz-pres", p.dgz_base_hpa != null ? `${p.dgz_base_hpa}–${p.dgz_top_hpa} hPa · ${(p.dgz_thickness_ft || 0).toLocaleString()} ft thick` : "");
    set("dgz-rhi", p.dgz_rhi_pct != null ? `${p.dgz_rhi_pct}%` : "n/a");
    set("dgz-w", p.dgz_lift_cm_s != null ? `${Math.abs(p.dgz_lift_cm_s).toFixed(0)} cm/s ${p.dgz_lift_cm_s >= 0.5 ? "up" : p.dgz_lift_cm_s <= -0.5 ? "down" : ""}` : "n/a");
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
      const runs = (m.runs || []).map(run).join(" / ");
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
      return sh ? (sh.levels || []).map(l => ({ z: l[1], t: l[2] })).filter(l => l.z != null && l.t != null).sort((a, b) => a.z - b.z) : [];
    })();
    const freeAirF = ft => {
      if (!col0.length || ft == null) return null;
      const z = ft * 0.3048;
      if (z <= col0[0].z) return col0[0].t * 9 / 5 + 32;
      for (let i = 1; i < col0.length; i++) if (z <= col0[i].z) {
        const a = col0[i - 1], b = col0[i];
        return (a.t + (b.t - a.t) * (z - a.z) / Math.max(1e-6, b.z - a.z)) * 9 / 5 + 32;
      }
      return null;
    };
    const colLabel = (o.profile_model || {}).label || ((o.model || {}).label);
    const stRows = ["base", "mid", "summit"].filter(t => st[t]).map(t => {
      const w = st[t], m = tl0(t), diff = (a, b) => (a != null && b != null ? `${a - b > 0 ? "+" : ""}${Math.round(a - b)}` : "–");
      const nm = String(w.name || t).replace(/,?\s*el\.\s*[\d,]+'?\s*$/i, "");
      const at = w.observed_at ? new Date(String(w.observed_at).replace(/([+-]\d{2})(\d{2})$/, "$1:$2")) : null;
      const fa = freeAirF(w.elevation_ft);
      return `<tr><td><b>${esc(nm)}</b><small>${w.elevation_ft ? w.elevation_ft.toLocaleString() + " ft · " : ""}observed ${at && !isNaN(at) ? at.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "n/a"}</small></td>
        <td>${tF(w.temp_f)} <small>model 2 m ${tF(m.temp_f)} (Δ ${diff(w.temp_f, m.temp_f)}°F)</small></td>
        <td>${fa != null ? `${tF(fa)} <small>Δ ${diff(w.temp_f, fa)}°F</small>` : "–"}</td>
        <td>${tF(w.dew_point_f)} <small>model ${tF(m.dew_point_f)}</small></td>
        <td>${w.wind_dir || ""} ${w.wind_mph ?? "–"} g ${w.gust_mph ?? "–"} mph <small>model ${Math.round(m.wind_mph || 0)} g ${Math.round(m.gust_mph || 0)}</small></td>
        <td>${esc(w.skies || "")}<small>model cloud ${m.cloud_cover_pct != null ? Math.round(m.cloud_cover_pct) + "%" : "–"}</small></td></tr>`;
    });
    const stEl = $("stations-table");
    const stSub = $("stations-sub");
    if (stSub) {
      const qp = o.query_points || {};
      const tiers = ["base", "mid", "summit"].filter(t => st[t] && qp[t]).map(t => `${t} ${(qp[t].elevation_ft || 0).toLocaleString()} ft`);
      stSub.textContent = `Measured at the resort's own stations. Model 2 m values are ${(o.model || {}).label || "the selected forecast"}'s first hour at the matching tier${tiers.length ? ` (${tiers.join(", ")})` : ""}. Free air is the ${colLabel || "model"} column's temperature at each station's height, same hour. Δ is station minus model.`;
    }
    if (stEl) stEl.innerHTML = stRows.length ? `<thead><tr><th>Resort station</th><th>Temperature</th><th>Free air</th><th>Dew point</th><th>Wind</th><th>Sky</th></tr></thead><tbody>${stRows.join("")}</tbody>`
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
        const note = a ? `line fit every hour through ${a.neighbors} surrounding 2.5 km cells (terrain ${a.neighbor_elevation_ft[0].toLocaleString()}–${a.neighbor_elevation_ft[1].toLocaleString()} ft, from the NWS grid), evaluated at the tier height; nearest cell ${a.grid_elevation_ft.toLocaleString()} ft at ${gp.grid_lat}, ${gp.grid_lon}${a.extrapolation_ft > 50 ? `, ${a.extrapolation_ft} ft beyond that range` : ""}; median temperature lapse ${a.lapse_f_per_kft ? a.lapse_f_per_kft.median : "?"} °F/1,000 ft`
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
  function renderAll() { renderSkewT(); renderHabit(); renderPhase(); renderDGZ(); renderSources(); renderBands(); }
  window.Panels = {
    onHour(h) { state.hour = h; renderPhase(); renderDGZ(); renderHabit(); if (state.skewSrc === "model") renderSkewT(); },
  };
  document.addEventListener("snow:render", e => { state.resort = e.detail.resort; renderAll(); });
  document.addEventListener("snow:prefs", () => { if (state.resort) renderAll(); });
  let rsz = null;
  window.addEventListener("resize", () => { clearTimeout(rsz); rsz = setTimeout(() => { if (state.resort) { renderPhase(); renderDGZ(); } }, 180); });
  document.addEventListener("DOMContentLoaded", () => {
    const seg = $("skewt-source");
    seg && seg.addEventListener("click", ev => {
      const b = ev.target.closest(".seg-btn"); if (!b) return;
      seg.querySelectorAll(".seg-btn").forEach(x => x.classList.toggle("active", x === b));
      state.skewSrc = b.dataset.src; renderSkewT();
    });
  });
})();
