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
      if (!m) { box.innerHTML = `<p class="mini-label" style="padding:20px">${esc(((om().atmospheric_sounding || {}).reason) || "No model sounding available.")} Observed Reno and Oakland soundings are still available above.</p>`; $("skewt-sub").textContent = ""; return; }
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
    // Thermometer layout: temperature on the vertical axis (0 °C at top, warmer upward),
    // supersaturation over ice on the horizontal axis.
    const W = 760, H = 420, L = 64, R = 20, T = 16, B = 40, PW = W - L - R, PH = H - T - B;
    const Smax = 40, Tmin = -30, Tmax = 0;
    const Y = t => T + PH * (Tmax - t) / (Tmax - Tmin);
    const X = sp => L + PW * Math.min(sp, Smax) / Smax;
    const loX = 5; // low / high supersaturation boundary (% over ice)
    let s = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" font-family="var(--font-sans)">`;
    HABITS.forEach((hb, i) => {
      const y0 = Y(hb.t0), y1 = Y(hb.t1), hgt = y1 - y0, ym = (y0 + y1) / 2;
      s += `<rect x="${X(loX)}" y="${y0}" width="${X(Smax) - X(loX)}" height="${hgt}" fill="rgba(125,211,252,${hb.glyph === "dendrite" ? 0.16 : 0.05 + (i % 2) * 0.03})"/>
        <rect x="${L}" y="${y0}" width="${X(loX) - L}" height="${hgt}" fill="rgba(148,163,184,${0.05 + (i % 2) * 0.03})"/>
        <line x1="${L}" x2="${L + PW}" y1="${y1}" y2="${y1}" stroke="rgba(255,255,255,0.08)"/>
        ${glyph(hb.glyph, X(Smax) - 26, ym, Math.min(11, hgt / 3.2))}
        <text x="${X(Smax) - 46}" y="${ym + 4}" text-anchor="end" fill="#e2e8f0" font-size="11" font-weight="600">${hb.hi}</text>
        <text x="${(L + X(loX)) / 2}" y="${ym + 4}" text-anchor="middle" fill="#94a3b8" font-size="9.5">${hb.lo}</text>`;
    });
    // water saturation (vapor excess over ice when air is saturated for liquid water)
    let d = "";
    for (let t = -0.2; t >= Tmin; t -= 0.5) d += `${d ? "L" : "M"}${X(100 * (esW(t) / esI(t) - 1)).toFixed(1)},${Y(t).toFixed(1)}`;
    s += `<path d="${d}" fill="none" stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="5 4"/>
      <text x="${X(100 * (esW(-27) / esI(-27) - 1)) + 6}" y="${Y(-27) + 4}" fill="#fcd34d" font-size="10">water saturation</text>`;
    for (let t = Tmin; t <= Tmax; t += 5) s += `<text x="${L - 8}" y="${Y(t) + 3.5}" text-anchor="end" fill="#94a3b8" font-size="10" font-family="var(--font-mono)">${t}°C</text>`;
    for (let sp = 0; sp <= Smax; sp += 10) s += `<text x="${X(sp)}" y="${T + PH + 15}" text-anchor="middle" fill="#94a3b8" font-size="10" font-family="var(--font-mono)">${sp}%</text>`;
    s += `<text x="${L + PW / 2}" y="${H - 6}" text-anchor="middle" fill="#64748b" font-size="10">Supersaturation over ice (RH w.r.t. ice − 100%)</text>`;
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
        s += `<circle cx="${X(si)}" cy="${Y(t)}" r="5" fill="#f472b6" stroke="#0b1220" stroke-width="1.5"/>
          <text x="${X(si) + 7}" y="${Y(t) + 3.5}" fill="#f9a8d4" font-size="9.5" font-family="var(--font-mono)">${p}</text>`;
      });
    }
    const status = m ? `${new Date(m.time).toLocaleString([], { weekday: "short", hour: "numeric" })}: ${plotted} model level${plotted === 1 ? "" : "s"} ice-supersaturated, ${sub} subsaturated (levels between 0 and −30 °C above the base).`
      : `No model profile for ${((om().model || {}).label) || "this model"}; select a model with a sounding to plot levels.`;
    box.innerHTML = s + `</svg><p class="habit-status">${status}</p>`;
  }

  // ---------------------------------------------------------------- precip type by elevation
  function renderPhase() {
    const col = $("phase-column"), tbl = $("phase-table");
    if (!col || !state.resort) return;
    const o = om(), tls = o.elevation_timelines || {}, prof = (o.vertical_profile || [])[state.hour] || {};
    const elevs = state.resort.elevations || {};
    const tsum = ((tls.summit || [])[state.hour]) || {};
    const sl = prof.snow_level_ft ?? tsum.snow_level_ft, wbz = prof.wet_bulb_zero_ft, fz = prof.freezing_level_ft;
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
    set("phase-desc", (o.vertical_profile || []).length
      ? `${t0 ? new Date(t0).toLocaleString([], { weekday: "short", hour: "numeric" }) : ""}. Snow fraction: 100% at or above the wet-bulb zero, 0% 1,000 ft below it; overridden by surface wet bulb (≤ 31 °F snow, ≥ 36 °F rain). Sleet/freezing rain risk: layer > +0.5 °C at least 1,000 ft deep above a sub-freezing wet bulb.`
      : `${t0 ? new Date(t0).toLocaleString([], { weekday: "short", hour: "numeric" }) : ""}. ${(o.model || {}).label || "This model"}'s own snow level and precipitation type; wet bulb computed from its temperature and dew point.`);
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
      rows.push(`<tr${m.id === cur ? ' class="row-primary"' : ""}><td><b>${esc(m.label)}</b>${m.id === cur ? "<small>selected</small>" : ""}</td><td>${esc(m.provider)}</td><td>${esc(m.grid)}</td>
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
    $("models-sub").innerHTML = `Summit point ${q.lat ?? "?"}, ${q.lon ?? "?"} at ${(q.elevation_ft || 0).toLocaleString()} ft. Snow uses each model's own snow fraction and SLR from its sounding. NBM and ECMWF HRES are surface-only in Open-Meteo, so their soundings come from GFS and ECMWF IFS 0.25°. <sup>†</sup> run ends before 7 days. Select a model in the bar at the top of the page.`;

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
    const tierUse = "Model surface fields; temperature/humidity lapse-rate adjusted to this elevation";
    const sp = o.sensor_point || {};
    $("points-table").innerHTML = `<thead><tr><th>Point</th><th>Lat, lon</th><th>Elevation used</th><th>Location</th><th>Used for</th></tr></thead><tbody>
      ${prow("Base", pts.base || {}, tierUse)}${prow("Mid", pts.mid || {}, tierUse)}${prow("Summit", pts.summit || {}, tierUse + "; model sounding, model comparison, NWS grid")}
      ${o.nbm_grid_points ? ["base", "mid", "summit"].map(t => prow(`NBM grid point (${t})`, { lat: o.nbm_grid_points[t].grid_lat, lon: o.nbm_grid_points[t].grid_lon, note: "nearest 2.5 km NBM grid point; NBM values are for this point's terrain" }, "NBM values for this tier")).join("") : ""}
      ${prow(`Sensor ${esc(sp.id || cdec.station_id || "")}`, { lat: cdec.latitude ?? sp.lat, lon: cdec.longitude ?? sp.lon, elevation_ft: cdec.elevation_ft, note: "CDEC-listed elevation; published coordinates are rounded" }, "Forecast at the sensor for verification")}
      ${prow(`NWS ${(nws.grid || {}).wfo || ""} base cell`, { lat: (nws.grid || {}).lat, lon: (nws.grid || {}).lon, elevation_ft: (nws.grid || {}).elevation_ft, note: `grid ${(nws.grid || {}).x ?? ""},${(nws.grid || {}).y ?? ""}; 2.5 km cell mean elevation` }, "Alerts, Area Forecast Discussion, base snowfall")}
      ${nws.summit_grid ? prow(`NWS ${nws.summit_grid.wfo} summit cell`, { lat: nws.summit_grid.lat, lon: nws.summit_grid.lon, elevation_ft: nws.summit_grid.grid_elevation_ft, note: `grid ${nws.summit_grid.x},${nws.summit_grid.y}; the crest is the REV/STO office boundary` }, "Summit-cell gridded snowfall, shown beside the model forecast (not blended)") : ""}
      </tbody>`;
    $("points-sub").textContent = "Each tier is queried at its own coordinates. Open-Meteo uses the nearest model grid cell and adjusts temperature and humidity from the cell's terrain height to the elevation given. Precipitation is not elevation-adjusted; wind uses pressure-level data at the tier height (summit) or the 10 m model wind (base).";
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
    if (sub) sub.textContent = `${(o.primary_model || {}).label || ""}. 2 m values are the model's near-surface field adjusted to each elevation with a fixed lapse rate; dashed lines are the model column's free-air temperature at the same height. Where they diverge (inversions, valley cold pools) the station data in Sources shows which one matched.`;

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
  function renderAll() { renderSkewT(); renderHabit(); renderPhase(); renderSources(); renderBands(); }
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
