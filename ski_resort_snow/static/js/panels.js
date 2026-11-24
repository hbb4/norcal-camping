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
  function routeShield(route, size = 22) {
    const r = String(route || "").toUpperCase();
    const num = (r.match(/\d+/) || [""])[0];
    if (!num) return "";
    const fs = num.length >= 3 ? 7.5 : 9;
    if (r === "80" || r.startsWith("I")) {
      return `<svg class="shield" width="${size}" height="${size}" viewBox="0 0 24 24" aria-label="Interstate ${num}">
        <path d="M2 4.5 Q12 0.5 22 4.5 L22 11 Q22 19.5 12 23 Q2 19.5 2 11 Z" fill="#1d4ed8" stroke="#fff" stroke-width="1.2"/>
        <path d="M2.6 4.9 Q12 1.2 21.4 4.9 L21.4 8 L2.6 8 Z" fill="#dc2626"/>
        <text x="12" y="17.2" text-anchor="middle" font-size="${fs}" font-weight="800" fill="#fff" font-family="Inter, sans-serif">${num}</text></svg>`;
    }
    if (r === "50" || r.startsWith("US")) {
      return `<svg class="shield" width="${size}" height="${size}" viewBox="0 0 24 24" aria-label="US Route ${num}">
        <path d="M3 2.5 H21 V5 Q22.5 7 21 9 V14 Q21 20.5 12 23 Q3 20.5 3 14 V9 Q1.5 7 3 5 Z" fill="#fff" stroke="#111" stroke-width="1.3"/>
        <text x="12" y="16" text-anchor="middle" font-size="${fs}" font-weight="800" fill="#111" font-family="Inter, sans-serif">${num}</text></svg>`;
    }
    // California state route: green "miner's spade"
    return `<svg class="shield" width="${size}" height="${size}" viewBox="0 0 24 24" aria-label="California State Route ${num}">
      <path d="M12 1.2 Q19.5 5 21.5 11.5 Q21.5 18.5 14.2 20.4 L14.2 23 H9.8 V20.4 Q2.5 18.5 2.5 11.5 Q4.5 5 12 1.2 Z" fill="#0b6b3a" stroke="#fff" stroke-width="1.2"/>
      <text x="12" y="14.8" text-anchor="middle" font-size="${fs}" font-weight="800" fill="#fff" font-family="Inter, sans-serif">${num}</text></svg>`;
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
      if (!m) { box.innerHTML = `<p class="mini-label">No model sounding available.</p>`; return; }
      levels = m.levels; hasW = true;
      const q = (om().query_points || {}).summit || {};
      title = `Model: ${(om().primary_model || {}).label || "primary model"} at ${q.lat?.toFixed(3)}, ${q.lon?.toFixed(3)} · valid ${new Date(m.time).toLocaleString([], { weekday: "short", hour: "numeric" })} (${utc(m.time)}). Levels below the base are shaded (model extrapolation below terrain).`;
      groundP = pressureAtHeight(levels, (elevs.base_ft || 6200) / FT);
    } else {
      const o = observed(src);
      if (!o || !o.levels) { box.innerHTML = `<p class="mini-label">${esc(src)} sounding unavailable${o && o.error_message ? `: ${esc(o.error_message)}` : ""}.</p>`; return; }
      levels = o.levels;
      title = `Observed: ${esc(o.name)} radiosonde, ${utc(o.valid_utc)} (${pst(o.valid_utc)} local) · ${esc(o.position)} · station elevation ${Math.round(o.elevation_m * FT).toLocaleString()} ft · ${o.status === "stale" ? "stale, " : ""}fetched ${ago(o.fetched_at_utc)}`;
      groundP = levels[0] ? levels[0][0] : null;
    }
    $("skewt-sub").textContent = title;

    const W = 760, H = 560, L = 52, R = 92, T = 12, B = 30, PW = W - L - R, PH = H - T - B;
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
      s += `<line x1="${X(t, pBot)}" y1="${Y(pBot)}" x2="${X(t, pTop)}" y2="${Y(pTop)}" stroke="${zero ? "#fbbf24" : "rgba(255,255,255,0.08)"}" stroke-width="${zero ? 1.3 : 1}" ${zero ? 'stroke-dasharray="5 4"' : ""}/>`;
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
      s += `<line x1="${L}" x2="${L + PW}" y1="${Y(p)}" y2="${Y(p)}" stroke="#f472b6" stroke-dasharray="3 4" opacity="0.7"/>
        <text x="${L + PW - 4}" y="${Y(p) - 3}" text-anchor="end" fill="#f9a8d4" font-size="10" font-weight="600">${lbl} ${ft.toLocaleString()} ft · ${Math.round(p)} hPa</text>`;
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
  const HABITS = [
    { t0: 0, t1: -4, lo: "Thick plates", hi: "Thin plates", glyph: "plate" },
    { t0: -4, t1: -6, lo: "Columns", hi: "Needles", glyph: "needle" },
    { t0: -6, t1: -10, lo: "Columns", hi: "Hollow col.", glyph: "column" },
    { t0: -10, t1: -12, lo: "Plates", hi: "Sectored", glyph: "sector" },
    { t0: -12, t1: -18, lo: "Plates", hi: "Dendrites", glyph: "dendrite" },
    { t0: -18, t1: -22, lo: "Plates", hi: "Sectored plates", glyph: "sector" },
    { t0: -22, t1: -30, lo: "Plates, columns", hi: "Polycrystals", glyph: "column" },
  ];
  function glyph(kind, cx, cy, r) {
    const hex = Array.from({ length: 6 }, (_, i) => `${(cx + r * Math.cos(Math.PI / 3 * i)).toFixed(1)},${(cy + r * Math.sin(Math.PI / 3 * i)).toFixed(1)}`).join(" ");
    const st = `stroke="#e0f2fe" stroke-width="1.2" fill="none"`;
    if (kind === "plate") return `<polygon points="${hex}" ${st} fill="rgba(224,242,254,0.15)"/>`;
    if (kind === "needle") return `<line x1="${cx}" y1="${cy - r}" x2="${cx}" y2="${cy + r}" ${st} stroke-width="1.6"/>`;
    if (kind === "column") return `<rect x="${cx - r * 0.35}" y="${cy - r}" width="${r * 0.7}" height="${r * 2}" ${st}/>`;
    if (kind === "sector") return `<polygon points="${hex}" ${st}/>` + Array.from({ length: 3 }, (_, i) => `<line x1="${cx + r * Math.cos(Math.PI / 3 * i)}" y1="${cy + r * Math.sin(Math.PI / 3 * i)}" x2="${cx - r * Math.cos(Math.PI / 3 * i)}" y2="${cy - r * Math.sin(Math.PI / 3 * i)}" ${st}/>`).join("");
    // dendrite
    let g = "";
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

  function renderHabit() {
    const box = $("habit-diagram");
    if (!box || !state.resort) return;
    const W = 760, H = 250, L = 46, R = 16, T = 14, B = 34, PW = W - L - R, PH = H - T - B;
    const Smax = 40, X = t => L + (-t / 30) * PW, Y = sp => T + PH * (1 - Math.min(sp, Smax) / Smax);
    const loY = 5; // boundary between low / high supersaturation habits (% over ice)
    let s = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" font-family="var(--font-sans)">`;
    HABITS.forEach((hb, i) => {
      const x0 = X(hb.t0), x1 = X(hb.t1);
      s += `<rect x="${x0}" y="${T}" width="${x1 - x0}" height="${Y(loY) - T}" fill="rgba(125,211,252,${hb.glyph === "dendrite" ? 0.16 : 0.05 + (i % 2) * 0.03})"/>
        <rect x="${x0}" y="${Y(loY)}" width="${x1 - x0}" height="${T + PH - Y(loY)}" fill="rgba(148,163,184,${0.04 + (i % 2) * 0.03})"/>
        <line x1="${x1}" x2="${x1}" y1="${T}" y2="${T + PH}" stroke="rgba(255,255,255,0.08)"/>
        ${glyph(hb.glyph, (x0 + x1) / 2, T + 18 + (x1 - x0 < 50 ? (i % 2) * 34 : 0), Math.min(10, (x1 - x0) / 3.2))}
        <text x="${(x0 + x1) / 2}" y="${T + 42 + (x1 - x0 < 50 ? (i % 2) * 34 : 0)}" text-anchor="middle" fill="#e2e8f0" font-size="9.5" font-weight="600">${hb.hi}</text>
        <text x="${(x0 + x1) / 2}" y="${Y(loY) + 13}" text-anchor="middle" fill="#94a3b8" font-size="9">${hb.lo}</text>`;
    });
    // water saturation curve
    let d = "";
    for (let t = -0.2; t >= -30; t -= 0.5) d += `${d ? "L" : "M"}${X(t).toFixed(1)},${Y(100 * (esW(t) / esI(t) - 1)).toFixed(1)}`;
    s += `<path d="${d}" fill="none" stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="5 4"/>
      <text x="${X(-21)}" y="${Y(100 * (esW(-21) / esI(-21) - 1)) + 14}" fill="#fcd34d" font-size="10" text-anchor="middle">water saturation</text>`;
    for (let t = 0; t >= -30; t -= 5) s += `<text x="${X(t)}" y="${T + PH + 14}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="var(--font-mono)">${t}°</text>`;
    for (let sp = 0; sp <= Smax; sp += 10) s += `<text x="${L - 6}" y="${Y(sp) + 3}" text-anchor="end" fill="#94a3b8" font-size="10" font-family="var(--font-mono)">${sp}%</text>`;
    s += `<text x="${L + PW / 2}" y="${H - 4}" text-anchor="middle" fill="#64748b" font-size="10">Temperature (°C) · vertical: supersaturation over ice (RH w.r.t. ice − 100%)</text>`;
    // model levels
    const m = modelLevels(state.hour);
    const baseP = m ? pressureAtHeight(m.levels, ((state.resort.elevations || {}).base_ft || 6200) / FT) : null;
    let sub = 0, plotted = 0;
    if (m) {
      m.levels.forEach(l => {
        const [p, , t, td] = l;
        if (td == null || t > 0 || t < -30 || (baseP && p > baseP)) return;
        const si = rhIce(t, td) - 100;
        if (si < 0) { sub++; return; }
        plotted++;
        s += `<circle cx="${X(t)}" cy="${Y(si)}" r="5" fill="#f472b6" stroke="#0b1220" stroke-width="1.5"/>
          <text x="${X(t) + 7}" y="${Y(si) + 3.5}" fill="#f9a8d4" font-size="9.5" font-family="var(--font-mono)">${p}</text>`;
      });
    }
    box.innerHTML = s + `</svg><p class="habit-status">${m ? `${new Date(m.time).toLocaleString([], { weekday: "short", hour: "numeric" })}: ${plotted} model level${plotted === 1 ? "" : "s"} ice-supersaturated, ${sub} subsaturated (levels between 0 and −30 °C above the base).` : "No model sounding."}</p>`;
  }

  // ---------------------------------------------------------------- precip type by elevation
  function renderPhase() {
    const col = $("phase-column"), tbl = $("phase-table");
    if (!col || !state.resort) return;
    const o = om(), tls = o.elevation_timelines || {}, prof = (o.vertical_profile || [])[state.hour] || {};
    const elevs = state.resort.elevations || {};
    const sl = prof.snow_level_ft, wbz = prof.wet_bulb_zero_ft, fz = prof.freezing_level_ft;
    const lo = Math.min(4000, (sl ?? 6000) - 1500), hi = Math.max((elevs.summit_ft || 9000) + 800, Math.min(14000, (fz ?? 0) + 600));
    const W = 130, H = 280, T = 8, B = 8;
    const Y = ft => T + (H - T - B) * (1 - (Math.max(lo, Math.min(hi, ft)) - lo) / (hi - lo));
    let s = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" font-family="var(--font-sans)">
      <defs><linearGradient id="phgrad" x1="0" y1="1" x2="0" y2="0">`;
    if (wbz != null) {
      const f = ft => ((Math.max(lo, Math.min(hi, ft)) - lo) / (hi - lo)).toFixed(3);
      s += `<stop offset="0" stop-color="#4ade80" stop-opacity=".35"/><stop offset="${f(wbz - 1000)}" stop-color="#4ade80" stop-opacity=".35"/>
        <stop offset="${f(wbz - 500)}" stop-color="#c084fc" stop-opacity=".4"/><stop offset="${f(wbz)}" stop-color="#7dd3fc" stop-opacity=".4"/><stop offset="1" stop-color="#7dd3fc" stop-opacity=".4"/>`;
    } else s += `<stop offset="0" stop-color="#7dd3fc" stop-opacity=".4"/><stop offset="1" stop-color="#7dd3fc" stop-opacity=".4"/>`;
    s += `</linearGradient></defs><rect x="40" y="${T}" width="34" height="${H - T - B}" rx="6" fill="url(#phgrad)" stroke="rgba(255,255,255,0.12)"/>`;
    for (let ft = Math.ceil(lo / 1000) * 1000; ft <= hi; ft += 1000) s += `<text x="34" y="${Y(ft) + 4}" text-anchor="end" fill="#64748b" font-size="10.5" font-family="var(--font-mono)">${ft / 1000}k</text>`;
    const line = (ft, color, dash, lbl) => ft == null ? "" : `<line x1="36" x2="78" y1="${Y(ft)}" y2="${Y(ft)}" stroke="${color}" stroke-width="2" ${dash ? `stroke-dasharray="${dash}"` : ""}/><text x="82" y="${Y(ft) + 4}" fill="${color}" font-size="11" font-weight="600">${lbl}</text>`;
    s += line(fz, "#fbbf24", "4 3", "Freezing") + line(wbz, "#60a5fa", "", "WBZ") + line(sl, "#f8fafc", "", "Snow");
    ["base", "mid", "summit"].forEach(t => {
      const ft = elevs[`${t}_ft`]; if (!ft) return;
      s += `<circle cx="57" cy="${Y(ft)}" r="4" fill="#0b1220" stroke="#f472b6" stroke-width="2"/>`;
    });
    col.innerHTML = s + `</svg>`;

    const row = t => {
      const x = (tls[t] || [])[state.hour] || {};
      return `<tr><th>${{ base: "Base", mid: "Mid", summit: "Summit" }[t]}<small>${(elevs[`${t}_ft`] || 0).toLocaleString()} ft</small></th>
        <td>${tF(x.temp_f)}</td><td>${tF(x.wet_bulb_f)}</td><td>${dDiff(x.dew_point_depression_f ?? (x.temp_f - x.dew_point_f))}</td><td>${x.relative_humidity_pct ?? "--"}%</td>
        <td><span class="phase-tag ${x.precip_phase || ""}">${x.precip_phase === "dry" ? "none" : (x.precip_phase_label || "--").toLowerCase()}</span></td></tr>`;
    };
    tbl.innerHTML = `<thead><tr><th></th><th>Dry bulb</th><th>Wet bulb</th><th>T − Td</th><th>RH</th><th>Precip</th></tr></thead>
      <tbody>${row("summit")}${row("mid")}${row("base")}</tbody>`;
    const set = (id, v) => { const e = $(id); if (e) e.textContent = v; };
    set("eff-snow-level-val", fmtFt(sl)); set("wbz-val", fmtFt(wbz)); set("freezing-level-val", fmtFt(fz));
    const t0 = ((tls.summit || [])[state.hour] || {}).time;
    set("phase-desc", `${t0 ? new Date(t0).toLocaleString([], { weekday: "short", hour: "numeric" }) : ""}. Snow fraction: 100% at or above the wet-bulb zero, 0% 1,000 ft below it; overridden by surface wet bulb (≤ 31 °F snow, ≥ 36 °F rain). Sleet/freezing rain risk: layer > +0.5 °C at least 1,000 ft deep above a sub-freezing wet bulb.`);
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
    const prim = o.primary_model || {};
    const rows = [];
    rows.push(`<tr class="row-primary"><td><b>HRRR → GFS</b><small>primary (gfs_seamless)</small></td><td>NOAA/NCEP</td><td>3 km → 0.25°</td>
      <td>${(prim.runs || []).map(run).join(" / ")}</td><td>168 h</td><td>${L(summit.liquid_48h_inches)}</td><td>${L(summit.liquid_7d_inches)}</td>
      <td>${S(summit.snow_48h_inches)}</td><td>${S(summit.snow_7d_total_inches)}</td></tr>`);
    (o.model_comparison || []).forEach(m => {
      if (m.error && !m.hours_available) { rows.push(`<tr><td><b>${esc(m.label)}</b></td><td>${esc(m.provider || "")}</td><td>${esc(m.grid || "")}</td><td colspan="6" class="muted">${esc(m.error)}</td></tr>`); return; }
      rows.push(`<tr><td><b>${esc(m.label)}</b></td><td>${esc(m.provider)}</td><td>${esc(m.grid)}</td><td>${run(m)}</td><td>${m.hours_available} h</td>
        <td>${L(m.liquid_48h)}${m.covers_48h ? "" : "<sup>†</sup>"}</td><td>${m.covers_7d ? L(m.liquid_7d) : "–"}</td>
        <td>${S(m.snow_48h)}${m.covers_48h ? "" : "<sup>†</sup>"}</td><td>${m.covers_7d ? S(m.snow_7d) : "–"}</td></tr>`);
    });
    const nwsRow = (g, label, used) => g ? rows.push(`<tr${used ? ' class="row-primary"' : ""}><td><b>NWS ${esc(g.wfo || "")} gridded forecast</b><small>${label}${used ? " · used in blend" : ""}</small></td><td>NWS ${esc(g.wfo || "")} (forecaster-edited)</td>
      <td>2.5 km${g.grid_elevation_ft || g.elevation_ft ? ` · cell ${(g.grid_elevation_ft || g.elevation_ft).toLocaleString()} ft` : ""}</td>
      <td>fetched ${ago(nws.fetched_at_utc)}</td><td>~7 d</td><td>–</td><td>–</td><td>${S(g.next_48h_inches)}</td><td>${S(g.total_snow_inches)}</td></tr>`) : null;
    nwsRow(nws.summit_grid, "cell at the summit point", nws.snowfall_grid_used === "summit");
    nwsRow(nws.grid, "cell at the base point", nws.snowfall_grid_used !== "summit");
    if (ens.members) rows.push(`<tr><td><b>Ensembles</b><small>${ens.members} members</small></td><td>NOAA · ECMWF · DWD</td><td>GEFS 0.25° · ENS 0.25° · ICON-EPS</td><td>latest</td><td>168 h</td>
      <td>${L(ens.liquid_48h && ens.liquid_48h.p10)}–${L(ens.liquid_48h && ens.liquid_48h.p90)}</td><td>–</td>
      <td>${S(ens.snow_48h.p10)}–${S(ens.snow_48h.p90)} <small>median ${S(ens.snow_48h.p50)}</small></td><td>${S(ens.snow_7d.p10)}–${S(ens.snow_7d.p90)}</td></tr>`);
    $("models-table").innerHTML = `<thead><tr><th>Model</th><th>Provider</th><th>Grid</th><th>Run (UTC)</th><th>Length</th><th>Liquid 48 h</th><th>Liquid 7 d</th><th>Snow 48 h</th><th>Snow 7 d</th></tr></thead><tbody>${rows.join("")}</tbody>`;
    const q = (o.query_points || {}).summit || {};
    $("models-sub").innerHTML = `Point ${q.lat ?? "?"}, ${q.lon ?? "?"} at ${(q.elevation_ft || 0).toLocaleString()} ft. Liquid = precipitation water equivalent. Snow for every model uses the primary forecast's hourly snow fraction × SLR, so differences come from precipitation only. <sup>†</sup> run ends before 48 h. Fetched ${ago(o.fetched_at_utc)}${o.status === "stale" ? ` (stale: ${esc(o.stale_reason)})` : ""}.`;

    // SLR methods
    const sm = summit.slr_methods || {};
    const slrRow = (key, name, when) => {
      const m = sm[key] || {};
      return `<tr${key === "cobb_adjusted" ? ' class="row-primary"' : ""}><td><b>${name}</b><small>${when}</small></td><td>${m.slr_48h != null ? m.slr_48h + ":1" : "–"}</td><td>${m.slr_7d != null ? m.slr_7d + ":1" : "–"}</td><td>${S(m.snow_48h)}</td><td>${S(m.snow_7d)}</td></tr>`;
    };
    $("slr-table").innerHTML = `<thead><tr><th>Method</th><th>SLR 48 h</th><th>SLR 7 d</th><th>Snow 48 h</th><th>Snow 7 d</th></tr></thead><tbody>
      ${slrRow("cobb_adjusted", "Cobb-style, adjusted (used)", "habit SLR of ice-saturated rising layers, × wind factor, near-freezing caps")}
      ${slrRow("cobb_unadjusted", "Cobb-style, unadjusted", "habit × lift only; no wind or melting adjustment")}
      ${slrRow("kuchera", "Kuchera", "from the warmest temperature below 500 hPa; common on model snowfall maps")}
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
    ["KREV", "KOAK"].forEach(st => {
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
    const stRows = ["base", "mid", "summit"].filter(t => st[t]).map(t => {
      const w = st[t], m = tl0(t), diff = (a, b) => (a != null && b != null ? `${a - b > 0 ? "+" : ""}${Math.round(a - b)}` : "–");
      return `<tr><td><b>${esc(w.name || t)}</b><small>observed ${w.observed_at ? new Date(w.observed_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "n/a"}</small></td>
        <td>${tF(w.temp_f)} <small>model ${tF(m.temp_f)} (Δ ${diff(w.temp_f, m.temp_f)}°F)</small></td>
        <td>${tF(w.dew_point_f)} <small>model ${tF(m.dew_point_f)}</small></td>
        <td>${w.wind_dir || ""} ${w.wind_mph ?? "–"} g ${w.gust_mph ?? "–"} mph <small>model ${Math.round(m.wind_mph || 0)} g ${Math.round(m.gust_mph || 0)} (${(o.query_points || {})[t] ? ((o.query_points || {})[t].elevation_ft || 0).toLocaleString() + " ft" : ""})</small></td>
        <td>${esc(w.skies || "")}<small>model cloud ${m.cloud_cover_pct != null ? Math.round(m.cloud_cover_pct) + "%" : "–"}</small></td></tr>`;
    });
    const stEl = $("stations-table");
    if (stEl) stEl.innerHTML = stRows.length ? `<thead><tr><th>Resort station</th><th>Temperature</th><th>Dew point</th><th>Wind</th><th>Sky</th></tr></thead><tbody>${stRows.join("")}</tbody>`
      : `<tbody><tr><td class="muted">Resort weather stations unavailable.</td></tr></tbody>`;

    // verification
    const hist = (((typeof snowData !== "undefined" && snowData) || {}).verification || {}).history || [];
    const mine = hist.filter(h => h.resort_id === state.resort.id);
    $("verify-table").innerHTML = mine.length ? `<thead><tr><th>Forecast issued</th><th>Sensor</th><th>Liquid fcst / measured</th><th>Error</th><th>Snow fcst (used)</th><th>Kuchera</th><th>10:1</th><th>Depth change</th><th>Resort reported</th><th>Notes</th></tr></thead><tbody>` +
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
    const tierUse = "Model surface fields; temperature/humidity lapse-rate adjusted to this elevation";
    const sp = o.sensor_point || {};
    $("points-table").innerHTML = `<thead><tr><th>Point</th><th>Lat, lon</th><th>Elevation used</th><th>Location</th><th>Used for</th></tr></thead><tbody>
      ${prow("Base", pts.base || {}, tierUse)}${prow("Mid", pts.mid || {}, tierUse)}${prow("Summit", pts.summit || {}, tierUse + "; model sounding, model comparison, NWS grid")}
      ${prow(`Sensor ${esc(sp.id || cdec.station_id || "")}`, { lat: cdec.latitude ?? sp.lat, lon: cdec.longitude ?? sp.lon, elevation_ft: cdec.elevation_ft, note: "CDEC-listed elevation; published coordinates are rounded" }, "Forecast at the sensor for verification")}
      ${prow(`NWS ${(nws.grid || {}).wfo || ""} base cell`, { lat: (nws.grid || {}).lat, lon: (nws.grid || {}).lon, elevation_ft: (nws.grid || {}).elevation_ft, note: `grid ${(nws.grid || {}).x ?? ""},${(nws.grid || {}).y ?? ""}; 2.5 km cell mean elevation` }, "Alerts, Area Forecast Discussion, base snowfall")}
      ${nws.summit_grid ? prow(`NWS ${nws.summit_grid.wfo} summit cell`, { lat: nws.summit_grid.lat, lon: nws.summit_grid.lon, elevation_ft: nws.summit_grid.grid_elevation_ft, note: `grid ${nws.summit_grid.x},${nws.summit_grid.y}; the crest is the REV/STO office boundary` }, "Summit snowfall used in the 24/48 h blend") : ""}
      </tbody>`;
    $("points-sub").textContent = "Each tier is queried at its own coordinates. Open-Meteo uses the nearest model grid cell and adjusts temperature and humidity from the cell's terrain height to the elevation given. Precipitation is not elevation-adjusted; wind uses pressure-level data at the tier height (summit) or the 10 m model wind (base).";
  }

  // ---------------------------------------------------------------- wiring
  function renderAll() { renderSkewT(); renderHabit(); renderPhase(); renderSources(); }
  window.Panels = {
    onHour(h) { state.hour = h; renderPhase(); renderHabit(); if (state.skewSrc === "model") renderSkewT(); },
  };
  document.addEventListener("snow:render", e => { state.resort = e.detail.resort; renderAll(); });
  document.addEventListener("snow:prefs", () => { if (state.resort) renderAll(); });
  document.addEventListener("DOMContentLoaded", () => {
    const seg = $("skewt-source");
    seg && seg.addEventListener("click", ev => {
      const b = ev.target.closest(".seg-btn"); if (!b) return;
      seg.querySelectorAll(".seg-btn").forEach(x => x.classList.toggle("active", x === b));
      state.skewSrc = b.dataset.src; renderSkewT();
    });
  });
})();
