/**
 * Sierra Snow: interactive layer
 *  - Mountain cross-section hero (snow level paints the slope, freezing
 *    level, DGZ cloud band, per-elevation accumulation pills)
 *  - Particle snowfall whose rate, drift and phase follow the forecast hour
 *    (flakes turn to rain below the snow level)
 *  - 48h scrubber with play/pause
 *  - Verdict card (headline, best window to ride)
 *  - 7-day outlook strip that follows the elevation toggle
 *  - Source popover, scroll-spy nav, keyboard shortcuts, entry motion
 */
(() => {
  const VB_W = 800, VB_H = 400;
  const TX = { base: 150, mid: 390, summit: 575 };
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let state = { resort: null, hour: 0, playing: null, tl: {}, profile: [] };

  // ---------------------------------------------------------------- helpers
  const $ = id => document.getElementById(id);
  const fmtIn = v => U.snow(v ?? 0);
  const fmtFt = v => (v == null ? "n/a" : `${Math.round(v).toLocaleString()} ft`);
  const dayName = d => d.toLocaleDateString([], { weekday: "short" });
  const hourName = d => d.toLocaleTimeString([], { hour: "numeric" });
  const compass = deg => ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"][Math.round(deg / 22.5) % 16];

  // Elevation (ft) -> viewBox y. Two linear segments: 4k-10k gets most of
  // the height so the mountain reads; 10k-18k is compressed for the DGZ.
  function yOf(ft) {
    if (ft == null) return null;
    if (ft <= 10000) return 380 - (Math.max(3000, ft) - 4000) / 6000 * 250;
    return 130 - (Math.min(19000, ft) - 10000) / 8000 * 112;
  }

  function seeded(i) { const x = Math.sin(i * 12.9898) * 43758.5453; return x - Math.floor(x); }

  // ---------------------------------------------------------------- conditions text
  /* Builds a factual description of one forecast hour. Criteria:
     snow rate (in/hr): light < 0.5, moderate 0.5-1, heavy >= 1
     rain/mix liquid rate (in/hr): light < 0.10, moderate 0.10-0.30, heavy > 0.30 (AMS glossary)
     no precipitation: < 0.005 in/hr liquid; sky from cloud cover (NWS): clear < 6%,
       mostly clear < 31%, partly cloudy < 56%, mostly cloudy < 94%, overcast >= 94%
     high wind: sustained >= 40 mph or gust >= 58 mph (NWS High Wind Warning thresholds) */
  const Conditions = {
    precip(st) {
      const liq = st.precip_in || 0, snow = st.snowfall_rate_in_hr || 0, ph = st.precip_phase;
      if (liq < 0.005 || ph === "dry") {
        const cc = st.cloud_cover_pct;
        const sky = cc == null ? "" : cc < 6 ? "clear" : cc < 31 ? "mostly clear" : cc < 56 ? "partly cloudy" : cc < 94 ? "mostly cloudy" : "overcast";
        return { kind: "none", text: `No precipitation${sky ? `, ${sky} (${Math.round(cc)}% cloud)` : ""}`, pop: st.precip_probability };
      }
      if (ph === "ice") return { kind: "ice", text: `Sleet/freezing rain risk, ${U.liquid(liq)}/hr liquid` };
      if (ph === "snow") {
        const cat = snow >= 1 ? "Heavy" : snow >= 0.5 ? "Moderate" : "Light";
        return { kind: "snow", text: `${cat} snow ${U.snow(snow, snow >= 1 ? 1 : 2)}/hr, SLR ${st.slr}:1` };
      }
      const cat = liq > 0.30 ? "Heavy" : liq >= 0.10 ? "Moderate" : "Light";
      return { kind: ph, text: `${cat} ${ph === "mix" ? "rain/snow" : "rain"} ${U.liquid(liq)}/hr liquid${ph === "mix" ? `, ${Math.round((st.snow_fraction || 0) * 100)}% as snow` : ""}` };
    },
    wind(st) {
      const hw = (st.wind_mph || 0) >= 40 || (st.gust_mph || 0) >= 58;
      return `${st.wind_dir_deg != null ? compass(st.wind_dir_deg) + " " : ""}${Math.round(st.wind_mph || 0)} mph, gusts ${Math.round(st.gust_mph || 0)}${hw ? " (high-wind criteria)" : ""}`;
    },
  };
  window.Conditions = Conditions;

  // ---------------------------------------------------------------- mountain
  function ridgePath(el) {
    const b = el.base_ft, m = el.mid_ft, s = el.summit_ft;
    const lerp = (a, c, t) => a + (c - a) * t;
    const pts = [
      [0, yOf(b) + 8], [70, yOf(b) + 3], [TX.base, yOf(b)],
      [215, yOf(lerp(b, m, 0.32)) - 6], [265, yOf(lerp(b, m, 0.55)) + 5], [330, yOf(lerp(b, m, 0.86)) - 5],
      [TX.mid, yOf(m)],
      [440, yOf(lerp(m, s, 0.35)) + 6], [490, yOf(lerp(m, s, 0.62)) - 6], [535, yOf(lerp(m, s, 0.86)) + 2],
      [TX.summit, yOf(s)],
      [612, yOf(s - 260)], [645, yOf(s - 600) + 6], [690, yOf(lerp(b, s, 0.5))], [745, yOf(lerp(b, s, 0.36)) + 4], [800, yOf(lerp(b, s, 0.3))]
    ];
    // add small jaggies between points
    const out = [];
    pts.forEach((p, i) => {
      out.push(p);
      const q = pts[i + 1];
      if (!q) return;
      for (let k = 1; k < 3; k++) {
        const t = k / 3;
        out.push([lerp(p[0], q[0], t), lerp(p[1], q[1], t) + (seeded(i * 7 + k) - 0.5) * 7]);
      }
    });
    return "M" + out.map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" L") + ` L800,${VB_H} L0,${VB_H} Z`;
  }



  // Faint couloir/gully strokes running down-slope from the ridge for texture
  function gullies(el) {
    let g = "";
    [[230, 0.35], [300, 0.6], [350, 0.85], [455, 0.4], [515, 0.7], [600, 0.95], [640, 0.8]].forEach(([x, k], i) => {
      const top = yOf(el.base_ft + (el.summit_ft - el.base_ft) * k) + 6;
      const len = 40 + seeded(i + 3) * 60;
      const dx = (x < TX.summit ? -1 : 1) * (8 + seeded(i) * 14);
      g += `<path d="M${x},${top} q${dx / 2},${len / 2} ${dx},${len}" stroke="rgba(15,23,42,0.28)" stroke-width="${1.5 + seeded(i + 9) * 2}" fill="none" stroke-linecap="round"/>`;
    });
    return g;
  }

  function buildScene(resort) {
    const svg = $("mountain-svg");
    if (!svg) return;
    const el = resort.elevations || { base_ft: 6200, mid_ft: 8000, summit_ft: 9000 };
    const ticks = [5000, 6000, 7000, 8000, 9000, 10000, 12000, 14000, 16000, 18000];
    const pill = (tier, label) => `
      <g class="mtn-pill" id="pill-${tier}" transform="translate(${TX[tier]},${yOf(el[`${tier}_ft`]) - 30})">
        <rect x="-46" y="-22" width="92" height="38" rx="10"/>
        <text text-anchor="middle" y="-3" fill="#fff" font-size="16" font-weight="700" id="pill-${tier}-val">--</text>
        <text text-anchor="middle" y="11" fill="#94a3b8" font-size="9.5" font-weight="600">${label} ${el[`${tier}_ft`].toLocaleString()}'</text>
        <path d="M-5,16 L0,22 L5,16 Z" fill="rgba(7,11,20,.82)"/>
      </g>
      <circle cx="${TX[tier]}" cy="${yOf(el[`${tier}_ft`])}" r="5" fill="#0b1220" stroke="#fff" stroke-width="2"/>
      <circle cx="${TX[tier]}" cy="${yOf(el[`${tier}_ft`])}" r="2.5" id="dot-${tier}" fill="#7dd3fc"/>`;

    svg.innerHTML = `
      <defs>
        <linearGradient id="mtnFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#26364f"/><stop offset="1" stop-color="#0d1626"/></linearGradient>
        <linearGradient id="backFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1b2a42"/><stop offset="1" stop-color="#101b2e"/></linearGradient>
        <linearGradient id="snowFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f8fbff" stop-opacity=".92"/><stop offset=".55" stop-color="#d6ecfb" stop-opacity=".62"/><stop offset="1" stop-color="#a9d3f0" stop-opacity=".4"/></linearGradient>
        <linearGradient id="snowFillBack" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#dbeafe" stop-opacity=".42"/><stop offset="1" stop-color="#93c5fd" stop-opacity=".16"/></linearGradient>
        <linearGradient id="shade" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#000" stop-opacity="0"/><stop offset=".72" stop-color="#000" stop-opacity="0"/><stop offset=".73" stop-color="#020617" stop-opacity=".28"/><stop offset="1" stop-color="#020617" stop-opacity=".38"/></linearGradient>
        <clipPath id="clipFront"><path d="${ridgePath(el)}"/></clipPath>
        <filter id="soft" x="-10%" y="-60%" width="120%" height="220%"><feGaussianBlur stdDeviation="7"/></filter>
        <pattern id="dgzHatch" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="7" stroke="#e0f2fe" stroke-width="1.4" stroke-opacity=".35"/></pattern>
      </defs>

      <g opacity=".9">${ticks.map(t => `<line x1="34" x2="800" y1="${yOf(t)}" y2="${yOf(t)}" stroke="rgba(255,255,255,0.035)"/>
        <text x="8" y="${yOf(t) + 3}" fill="#52627a" font-size="9" font-family="JetBrains Mono, monospace">${t / 1000}k</text>`).join("")}
        <path d="M24,${yOf(10000) + 3} l6,-3 M24,${yOf(10000) + 7} l6,-3" stroke="#52627a"/>
      </g>

      <g id="dgz-band">
        <rect id="dgz-cloud" x="20" width="760" rx="30" fill="#7dd3fc" filter="url(#soft)"/>
        <rect id="dgz-hatch" x="40" width="720" fill="url(#dgzHatch)"/>
      </g>

      <path d="${ridgePath(el)}" fill="url(#mtnFill)" stroke="rgba(255,255,255,0.08)"/>
      <g clip-path="url(#clipFront)">
        <rect class="mtn-snowcap" id="snowcap" x="0" y="-${VB_H}" width="800" height="${VB_H}" fill="url(#snowFill)"/>
        <rect x="0" y="0" width="800" height="${VB_H}" fill="url(#shade)"/>
        ${gullies(el)}
      </g>
      <path d="${ridgePath(el).split(" L800," + VB_H)[0]}" fill="none" stroke="rgba(255,255,255,0.35)" stroke-width="1.2"/>

    `;
    const ov = $("mountain-overlay");
    if (ov) ov.innerHTML = `
      <text id="dgz-label" x="96" fill="#bae6fd" font-size="11" font-weight="700" style="paint-order:stroke" stroke="#0a1426" stroke-width="3">Dendrite zone</text>
      <g class="mtn-line" id="fz-line">
        <line x1="34" x2="800" y1="0" y2="0" stroke="#fbbf24" stroke-width="1.5" stroke-dasharray="6 5" opacity=".9"/>
        <text x="712" y="-6" text-anchor="end" fill="#fcd34d" font-size="10.5" font-weight="700" id="fz-text">Freezing</text>
      </g>
      <g class="mtn-line" id="sl-line">
        <line x1="34" x2="800" y1="0" y2="0" stroke="#fff" stroke-width="2"/>
        <text x="712" y="14" text-anchor="end" fill="#fff" font-size="10.5" font-weight="700" id="sl-text">Snow level</text>
      </g>

      ${pill("base", "Base")}${pill("mid", "Mid")}${pill("summit", "Summit")}
    `;
  }

  function updateScene(h) {
    const r = state.resort;
    if (!r) return;
    const tl = state.tl, prof = state.profile[h] || {};
    const el = r.elevations || {};

    // snow level paints the mountain
    const sl = prof.snow_level_ft ?? (tl.summit[h] || {}).snow_level_ft;
    const fz = prof.freezing_level_ft;
    const ySl = Math.min(VB_H + 10, yOf(sl ?? 3000));
    ["snowcap"].forEach(id => { const e = $(id); if (e) e.style.transform = `translateY(${ySl}px)`; });
    const slg = $("sl-line"); if (slg) { slg.style.transform = `translateY(${ySl}px)`; slg.style.opacity = ySl > VB_H ? 0 : 1; }
    $("sl-text") && ($("sl-text").textContent = `Snow level ${fmtFt(sl)}`);
    const fzg = $("fz-line"); if (fzg) { fzg.style.transform = `translateY(${yOf(fz ?? 3000)}px)`; fzg.style.opacity = fz ? 1 : 0; }
    $("fz-text") && ($("fz-text").textContent = `Freezing ${fmtFt(fz)}`);

    // DGZ
    const cloud = $("dgz-cloud"), hatch = $("dgz-hatch"), lbl = $("dgz-label");
    if (prof.dgz_base_ft != null && prof.dgz_top_ft != null && cloud) {
      const y1 = yOf(prof.dgz_top_ft), y2 = yOf(prof.dgz_base_ft);
      const rh = (prof.dgz_rh_pct ?? 50) / 100;
      const cross = (prof.dgz_rh_pct ?? 0) >= 85 && (prof.dgz_lift_cm_s ?? 0) >= 10;
      cloud.setAttribute("y", y1); cloud.setAttribute("height", Math.max(6, y2 - y1));
      cloud.setAttribute("opacity", Math.max(0.08, (rh - 0.45) * 0.8).toFixed(2));
      hatch.setAttribute("y", y1 + 3); hatch.setAttribute("height", Math.max(2, y2 - y1 - 6));
      hatch.setAttribute("opacity", cross ? 1 : 0);
      lbl.setAttribute("y", (y1 + y2) / 2 + 4);
      lbl.textContent = `Dendrite zone · ${prof.dgz_rh_pct ?? "?"}% RH · ${cross ? "rising, flakes growing fast ✦" : (prof.dgz_lift_cm_s ?? 0) >= 0 ? "weak lift" : "sinking"}`;
      $("dgz-band").style.opacity = 1; lbl.style.opacity = 1;
    } else if ($("dgz-band")) { $("dgz-band").style.opacity = 0; if (lbl) lbl.style.opacity = 0; }

    // pills
    ["base", "mid", "summit"].forEach(t => {
      const st = (tl[t] || [])[h] || {};
      const v = $(`pill-${t}-val`); if (v) v.textContent = fmtIn(st.cumulative_snow_inches);
      const d = $(`dot-${t}`); if (d) d.setAttribute("fill", { snow: "#7dd3fc", mix: "#c084fc", rain: "#4ade80", ice: "#fb7185" }[st.precip_phase] || "#475569");
      const pillEl = $(`pill-${t}`); if (pillEl) pillEl.style.opacity = t === window.__snowTier ? 1 : 0.88;
    });

    // readout chips + dynamic title
    const sm = (tl.summit || [])[h] || {}, bs = (tl.base || [])[h] || {};
    const d = new Date(sm.time || Date.now());
    const rate = sm.snowfall_rate_in_hr || 0;
    const tier = window.__snowTier || "summit";
    const ts = (tl[tier] || [])[h] || sm;
    const pc = Conditions.precip(ts);
    const tierName = { base: "Base", mid: "Mid", summit: "Summit" }[tier];
    $("scene-title").textContent = `${tierName} ${(el[`${tier}_ft`] || 0).toLocaleString()} ft: ${pc.text}${pc.kind === "none" && pc.pop != null ? ` · ${pc.pop}% chance of precipitation` : ""}`;
    $("scene-eyebrow").textContent = `${r.short_name || r.name} · ${dayName(d)} ${d.toLocaleDateString([], { month: "short", day: "numeric" })} ${hourName(d)} · +${h} h · ${h < 47 ? "HRRR 3 km" : "GFS"}`;

    const ro = $("scene-readout");
    if (ro) ro.innerHTML = `
      <span class="chip"><svg><use href="#i-wind"/></svg>${tierName} wind ${Conditions.wind(ts)}</span>
      <span class="chip">T ${U.temp(ts.temp_f)} · Tw ${U.temp(ts.wet_bulb_f)}</span>
      <span class="chip">Snow level ${fmtFt(sl)}</span>`;

    // scrubber UI
    const rng = $("time-scrubber");
    if (rng) { rng.value = h; rng.style.setProperty("--p", `${(h / Math.max(1, rng.max)) * 100}%`); }
    $("scrub-time").textContent = h === 0 ? `Now · ${hourName(d)}` : `${dayName(d)} ${hourName(d)} · +${h}h`;

    if (window.Panels) window.Panels.onHour(h);

    // particles follow this hour
    snowFx.setConditions({
      liquid: sm.precip_in || 0,
      windMph: sm.wind_mph || 0,
      windDir: sm.wind_dir_deg ?? 225,
      snowLevelY: ySl,
      rainLevelY: yOf((sl ?? 3000) - 500)
    });
  }

  function buildScrubDays() {
    const box = $("scrub-days"), tl = state.tl.summit || [];
    if (!box || !tl.length) return;
    const n = tl.length - 1;
    box.innerHTML = tl.map((x, i) => {
      const d = new Date(x.time);
      return d.getHours() === 0 ? `<span style="left:${(i / n) * 100}%">${dayName(d)}</span>` : "";
    }).join("");
    $("time-scrubber").max = n;
  }

  // ---------------------------------------------------------------- particles
  const snowFx = (() => {
    const canvas = $("snow-canvas");
    const ctx = canvas ? canvas.getContext("2d") : null;
    let W = 0, H = 0, dpr = 1, scale = 1, offY = 0, flakes = [], cond = { liquid: 0, windMph: 0, windDir: 225, snowLevelY: 999, rainLevelY: 999 };
    let enabled = true, visible = true, raf = null, last = 0;

    function resize() {
      if (!canvas) return;
      const r = canvas.getBoundingClientRect();
      dpr = Math.min(2, window.devicePixelRatio || 1);
      W = r.width; H = r.height;
      canvas.width = W * dpr; canvas.height = H * dpr;
      scale = Math.max(W / VB_W, H / VB_H);
      offY = (H - VB_H * scale) / 2;
    }
    const target = () => Math.round(Math.min(340, cond.liquid * 1400 + (cond.liquid > 0.004 ? 25 : 0)));
    function spawn(top) {
      return { x: Math.random() * W, y: top ? -10 : Math.random() * H, r: 0.8 + Math.random() * 2.2, v: 0.6 + Math.random() * 0.8, ph: Math.random() * 6.28 };
    }
    function frame(t) {
      raf = null;
      if (!ctx || !enabled || !visible) return;
      const dt = Math.min(0.05, (t - last) / 1000 || 0.016); last = t;
      const want = target();
      while (flakes.length < want) flakes.push(spawn(false));
      if (flakes.length > want) flakes.length = want;
      const drift = -Math.sin(cond.windDir * Math.PI / 180) * cond.windMph * 0.9;
      const ySnow = offY + cond.snowLevelY * scale, yRain = offY + cond.rainLevelY * scale;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      for (const f of flakes) {
        const isRain = f.y > yRain || (f.y > ySnow && f.r > 1.8);
        f.ph += dt * 2;
        f.y += (isRain ? 420 : 42) * f.v * dt;
        f.x += (drift * (isRain ? 0.5 : 1) + Math.sin(f.ph) * 10) * dt;
        if (f.y > H + 10 || f.x < -20 || f.x > W + 20) { Object.assign(f, spawn(true)); f.x = drift > 0 ? Math.random() * W - 40 : Math.random() * W + 40; }
        if (isRain) {
          ctx.strokeStyle = "rgba(125, 211, 252, 0.55)"; ctx.lineWidth = 1;
          ctx.beginPath(); ctx.moveTo(f.x, f.y); ctx.lineTo(f.x - drift * 0.02, f.y - 9); ctx.stroke();
        } else {
          ctx.fillStyle = `rgba(255,255,255,${0.45 + f.r * 0.18})`;
          ctx.beginPath(); ctx.arc(f.x, f.y, f.r, 0, 6.283); ctx.fill();
        }
      }
      raf = requestAnimationFrame(frame);
    }
    function kick() { if (!raf && enabled && visible && ctx) { last = performance.now(); raf = requestAnimationFrame(frame); } }
    window.addEventListener("resize", resize);
    if (canvas && "IntersectionObserver" in window) {
      new IntersectionObserver(e => { visible = e[0].isIntersecting; kick(); }).observe(canvas);
    }
    document.addEventListener("visibilitychange", () => { visible = !document.hidden; kick(); });
    return {
      init() { resize(); kick(); },
      setConditions(c) { cond = { ...cond, ...c }; kick(); },
      setEnabled(on) { enabled = on; if (!on && ctx) { ctx.clearRect(0, 0, canvas.width, canvas.height); } kick(); }
    };
  })();

  // ---------------------------------------------------------------- verdict
  function renderVerdict(resort) {
    const om = (resort.sources || {}).open_meteo || {};
    const tls = om.elevation_timelines || {};
    const summit = om.summit || {}, base = om.base || {};
    const s48 = summit.snow_48h_inches ?? 0, b48 = base.snow_48h_inches ?? 0, s7 = summit.snow_7d_total_inches ?? 0;
    const big = v => (U.metricSnow() ? U.snow(v, 0) : v >= 24 ? `${(v / 12).toFixed(v >= 36 ? 0 : 1)} ft` : U.snow(v, 0));

    const e = summit.ensemble || null;
    const rng = st => (st ? ` (${U.snowBare(st.p10, 0)}–${U.snow(st.p90, 0)}, p10–p90)` : "");
    $("verdict-headline").textContent = s48 >= 0.5 || s7 < 1
      ? `${U.snow(s48, 0)} in 48 h${rng(e && e.snow_48h)}`
      : `${U.snow(s48, 0)} in 48 h · ${U.snow(s7, 0)} in 7 days${rng(e && e.snow_7d)}`;
    const se = $("summary-eyebrow");
    if (se) se.textContent = `Summit ${((resort.elevations || {}).summit_ft || 0).toLocaleString()} ft · model + ensemble`;

    const facts = [];
    const st = tls.summit || [];
    const liq48 = summit.liquid_48h_inches ?? st.reduce((a, x) => a + (x.precip_in || 0), 0);
    const bt = (tls.base || []).filter(x => (x.precip_in || 0) >= 0.01);
    const bliq = bt.reduce((a, x) => a + x.precip_in, 0);
    const bshare = bliq > 0 ? bt.reduce((a, x) => a + x.precip_in * (x.snow_fraction ?? 1), 0) / bliq : null;
    facts.push(`Liquid, summit: ${U.liquid(liq48)}${bshare != null ? ` · base: ${Math.round(bshare * 100)}% of ${U.liquid(bliq)} as snow (${fmtIn(b48)})` : ""}`);
    const sls = (om.vertical_profile || []).map(p => p.snow_level_ft).filter(v => v != null);
    if (sls.length) facts.push(`Snow level range: ${fmtFt(Math.min(...sls))} – ${fmtFt(Math.max(...sls))}`);
    const pk = st.reduce((m, x) => ((x.gust_mph || 0) > (m.gust_mph || 0) ? x : m), {});
    if (pk.time) facts.push(`Peak summit gust: ${Math.round(pk.gust_mph)} mph, ${dayName(new Date(pk.time))} ${hourName(new Date(pk.time))} · ${st.filter(x => (x.gust_mph || 0) >= 45).length} h ≥ 45 mph`);
    const heavy = st.find(x => (x.snowfall_rate_in_hr || 0) >= 1);
    if (heavy) facts.push(`First hour ≥ ${U.snow(1, 0)}/hr: ${dayName(new Date(heavy.time))} ${hourName(new Date(heavy.time))}`);
    const ice = st.filter(x => x.precip_phase === "ice").length;
    if (ice) facts.push(`${ice} h with sleet/freezing-rain risk at the summit`);
    const rr = (resort.sources || {}).resort_official || {};
    const rmid = (rr.snow_areas || {}).mid || {};
    if (["success", "stale"].includes(rr.status) && rmid.new_7d_in != null)
      facts.push(`Resort report (mid ${rmid.elevation_ft ? rmid.elevation_ft.toLocaleString() + " ft" : ""}): ${U.snow(rmid.new_24h_in ?? 0)} 24 h · ${U.snow(rmid.new_7d_in)} 7 d · depth ${U.snow(rmid.base_depth_in)} · ${rr.lifts_open}/${rr.lifts_total} lifts`);
    const hz = (((resort.sources || {}).noaa_nws || {}).active_hazards || []).map(x => x.event).filter(Boolean);
    if (hz.length) facts.push(`NWS: ${[...new Set(hz)].join(", ")}`);
    const fl = $("verdict-facts");
    if (fl) fl.innerHTML = facts.map(f => `<li>${f}</li>`).join("");

    // best window: 9am-1pm hour maximizing new snow in prior 18h, penalising wind
    const mt = tls.mid || [];
    let best = null;
    st.forEach((x, i) => {
      const d = new Date(x.time), hr = d.getHours();
      if (hr < 9 || hr > 13) return;
      const fresh = st.slice(Math.max(0, i - 18), i + 1).reduce((a, y) => a + (y.snowfall_rate_in_hr || 0), 0);
      const midFresh = mt.slice(Math.max(0, i - 18), i + 1).reduce((a, y) => a + (y.snowfall_rate_in_hr || 0), 0);
      const gust = (mt[i] || x).gust_mph || 0;
      const score = midFresh + fresh * 0.4 - Math.max(0, gust - 40) * 0.35 - (x.snowfall_rate_in_hr > 2 ? 3 : 0);
      if (!best || score > best.score) best = { i, d, fresh, midFresh, gust, summitGust: x.gust_mph || 0, score };
    });
    if (best && best.midFresh >= 2) {
      $("best-when").textContent = `${dayName(best.d)} ${hourName(best.d)}`;
      $("best-why").textContent = `${U.snow(best.midFresh, 0)} new at mid in prior 18 h · mid gust ${Math.round(best.gust)} mph · summit gust ${Math.round(best.summitGust)} mph`;
      $("best-when").dataset.hour = best.i;
    } else {
      $("best-when").textContent = "None";
      $("best-why").textContent = `Less than ${U.snow(2, 0)} new at mid in any 18 h window`;
      delete $("best-when").dataset.hour;
    }
  }

  // ---------------------------------------------------------------- 7-day
  function outlookDays(resort) {
    const om = (resort.sources || {}).open_meteo || {};
    const tier = window.__snowTier || "summit";
    const t = om[tier] || {};
    let days = (t.daily_forecast || []).slice();
    // Drop a short "rest of tonight" stub when we have more than 7 days
    if (days.length > 7 && (days[0].hours ?? 24) < 12) days = days.slice(1);
    return { tier, t, days: days.slice(0, 7), all: t.daily_forecast || [], ens: t.ensemble };
  }

  function renderOutlook(resort) {
    const { tier, days, all, ens } = outlookDays(resort);
    const sub = $("outlook-sub");
    const elev = (resort.elevations || {})[`${tier}_ft`];
    if (sub) sub.textContent = `${TIER_LABEL[tier]}${elev ? ` (${elev.toLocaleString()}')` : ""} · ` +
      (ens ? `ranges from ${ens.members} runs of the GEFS, ECMWF and ICON ensembles` : "ensemble spread unavailable, showing the single high-res forecast");
    renderFan(days, all, ens);
    renderDayTiles(days, ens);
  }

  function renderFan(days, all, ens) {
    const box = $("fan-chart");
    if (!box) return;
    if (!days.length) { box.innerHTML = `<div class="mini-label">No outlook available.</div>`; return; }
    const W = 1000, H = 190, padL = 46, padR = 150, padT = 10, padB = 26;
    const pw = W - padL - padR, ph = H - padT - padB;
    const cumByDate = {};
    (ens ? ens.cumulative_daily : []).forEach(c => { cumByDate[c.date] = c; });
    let det = 0; const detByDate = {};
    all.forEach(d => { det += d.snowfall_inches || 0; detByDate[d.date] = det; });
    const pts = [{ x: 0, p10: 0, p25: 0, p50: 0, p75: 0, p90: 0, det: 0, label: "Now" }];
    days.forEach((d, i) => {
      const c = cumByDate[d.date] || {};
      pts.push({ x: i + 1, date: d.date, det: detByDate[d.date] ?? 0, ...c });
    });
    const cv = v => U.snowNum(v ?? 0);
    const maxV = Math.max(U.snowNum(6), ...pts.map(p => Math.max(cv(p.p90), cv(p.det))));
    const step = niceStep(maxV * 1.1, 4), top = Math.ceil((maxV * 1.1) / step) * step;
    const X = i => padL + (i / days.length) * pw;
    const Y = v => padT + ph * (1 - Math.min(v, top) / top);
    let svg = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" font-family="var(--font-sans)">`;
    for (let v = 0; v <= top + 1e-6; v += step) {
      svg += `<line x1="${padL}" x2="${padL + pw}" y1="${Y(v)}" y2="${Y(v)}" stroke="rgba(255,255,255,${v === 0 ? 0.16 : 0.05})"/>
        <text x="${padL - 8}" y="${Y(v) + 3.5}" fill="#6b7a90" font-size="10.5" text-anchor="end" font-family="var(--font-mono)">${+v.toFixed(1)}${U.metricSnow() ? "" : '"'}</text>`;
    }
    pts.forEach((p, i) => {
      if (i === 0) return;
      const d = new Date(p.date + "T12:00");
      svg += `<line x1="${X(i)}" x2="${X(i)}" y1="${padT}" y2="${padT + ph}" stroke="rgba(255,255,255,0.04)"/>
        <text x="${X(i - 0.5)}" y="${H - 8}" fill="#a3afc2" font-size="11" text-anchor="middle" font-weight="600">${dayName(d)}</text>`;
    });
    const line = (key, f = cv) => pts.map((p, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(f(p[key])).toFixed(1)}`).join(" ");
    const band = (lo, hi) => line(hi) + " " + pts.slice().reverse().map((p, k) => `L${X(pts.length - 1 - k).toFixed(1)},${Y(cv(p[lo])).toFixed(1)}`).join(" ") + " Z";
    if (ens) {
      svg += `<path d="${band("p10", "p90")}" fill="rgba(125,211,252,0.16)"/>`;
      svg += `<path d="${band("p25", "p75")}" fill="rgba(125,211,252,0.32)"/>`;
      svg += `<path d="${line("p50")}" fill="none" stroke="#f8fafc" stroke-width="2.5" stroke-linejoin="round"/>`;
    }
    svg += `<path d="${line("det")}" fill="none" stroke="#f9a8d4" stroke-width="1.5" stroke-dasharray="4 4"/>`;
    pts.forEach((p, i) => { if (i) svg += `<circle cx="${X(i)}" cy="${Y(cv(p.det))}" r="3.5" fill="#0b1220" stroke="#f9a8d4" stroke-width="2"/>`; });
    const last = pts[pts.length - 1];
    const lx = padL + pw + 12;
    if (ens) {
      svg += `<text x="${lx}" y="${Y(cv(last.p50)) - 4}" fill="#f8fafc" font-size="18" font-weight="700">${U.snow(last.p50)}</text>
        <text x="${lx}" y="${Y(cv(last.p50)) + 12}" fill="#a3afc2" font-size="11">likely by ${dayName(new Date(last.date + "T12:00"))}</text>
        <text x="${lx}" y="${Y(cv(last.p50)) + 27}" fill="#7dd3fc" font-size="11" font-family="var(--font-mono)">${U.snowBare(last.p10, 0)}–${U.snow(last.p90, 0)}</text>`;
    } else {
      svg += `<text x="${lx}" y="${Y(cv(last.det)) + 4}" fill="#f9a8d4" font-size="16" font-weight="700">${U.snow(last.det)}</text>`;
    }
    pts.forEach((p, i) => { if (i) svg += `<rect class="fan-hit" data-i="${i}" x="${X(i - 1)}" y="${padT}" width="${X(i) - X(i - 1)}" height="${ph}" fill="transparent"/>`; });
    svg += `</svg>`;
    box.innerHTML = svg;

    const tip = $("floating-tip");
    box.querySelectorAll(".fan-hit").forEach(r => {
      r.addEventListener("mouseenter", () => {
        const p = pts[+r.dataset.i], d = days[+r.dataset.i - 1];
        tip.innerHTML = `<div class="tt-time">By end of ${new Date(p.date + "T12:00").toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" })}</div>` +
          (ens ? `<div class="tt-row"><span class="tt-label">Most likely total</span><span class="tt-val">${U.snow(p.p50)}</span></div>
           <div class="tt-row"><span class="tt-label">80% of runs</span><span class="tt-val">${U.snowBare(p.p10)}–${U.snow(p.p90)}</span></div>
           <div class="tt-row"><span class="tt-label">That day alone</span><span class="tt-val">${U.snow(d.snow_p50 ?? 0)} (${U.snowBare(d.snow_p10 ?? 0)}–${U.snow(d.snow_p90 ?? 0)})</span></div>` : "") +
          `<div class="tt-row"><span class="tt-label">High-res forecast</span><span class="tt-val" style="color:#f9a8d4">${U.snow(p.det)}</span></div>`;
        tip.style.display = "block";
      });
      r.addEventListener("mousemove", ev => {
        const w = tip.offsetWidth || 220;
        tip.style.left = `${Math.min(window.innerWidth - w - 12, ev.clientX + 14)}px`;
        tip.style.top = `${ev.clientY - 20}px`;
      });
      r.addEventListener("mouseleave", () => { tip.style.display = "none"; });
    });
  }

  function renderDayTiles(days, ens) {
    const box = $("day-strip");
    if (!box) return;
    const scale = Math.max(6, ...days.map(d => d.snow_p90 ?? d.snowfall_inches ?? 0));
    const pct = v => `${Math.min(100, ((v ?? 0) / scale) * 100)}%`;
    const todayKey = new Date().toLocaleDateString("en-CA");
    const thr = U.metricSnow() ? "15 cm" : '6"';
    box.innerHTML = days.map(d => {
      const dt = new Date(d.date + "T12:00");
      const likely = d.snow_p50 ?? d.snowfall_inches ?? 0;
      const hasRange = d.snow_p10 != null;
      const g = d.max_gust_mph || 0;
      const gc = g >= 65 ? "var(--bad)" : g >= 45 ? "var(--warn)" : "var(--good)";
      const share = d.snow_share;
      const phase = share == null ? "" : (d.ice_hours || 0) >= 2 ? `<span class="phase-tag ice">ice risk</span>` : share >= 0.9 ? `<span class="phase-tag snow">snow</span>` : share >= 0.4 ? `<span class="phase-tag mix">mix</span>` : `<span class="phase-tag rain">rain</span>`;
      const name = d.date === todayKey ? ((d.hours ?? 24) < 24 ? "Rest of today" : "Today") : dayName(dt);
      return `<div class="day${d.date === todayKey ? " today" : ""}${likely >= 12 ? " big" : ""}" data-date="${d.date}" title="Click to show this day on the mountain">
        <div class="day-name">${name} <span>${dt.getDate()}</span></div>
        <div class="day-likely">${U.snowBare(likely)}<small>${U.snowSuffix().trim()}</small></div>
        <div class="day-range">${hasRange ? `${U.snowBare(d.snow_p10)}–${U.snow(d.snow_p90)}` : "single forecast"}</div>
        <div class="whisker" aria-hidden="true">
          ${hasRange ? `<span class="w90" style="left:${pct(d.snow_p10)};width:calc(${pct(d.snow_p90)} - ${pct(d.snow_p10)})"></span>
          <span class="w50" style="left:${pct(d.snow_p25)};width:calc(${pct(d.snow_p75)} - ${pct(d.snow_p25)})"></span>
          <span class="wmed" style="left:${pct(d.snow_p50)}"></span>` : ""}
          <span class="wdet" style="left:${pct(d.snowfall_inches)}" title="High-res forecast: ${U.snow(d.snowfall_inches)}"></span>
        </div>
        <div class="day-prob">${d.prob_6in != null ? `P(≥ ${thr}) <b>${d.prob_6in}%</b>` : "&nbsp;"}</div>
        <div class="day-meta"><span>${U.tempShort(d.temp_high_f)}/${U.tempShort(d.temp_low_f)}</span>${phase}<span class="day-gust"><i style="background:${gc}"></i>${Math.round(g)}</span></div>
      </div>`;
    }).join("");
    box.querySelectorAll(".day").forEach(el => el.addEventListener("click", () => {
      const tl = state.tl.summit || [];
      const idx = tl.findIndex(x => { const t = new Date(x.time); return t.toLocaleDateString("en-CA") === el.dataset.date && t.getHours() >= 9; });
      if (idx >= 0) { setHour(idx); $("overview").scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" }); }
      else { const tip = $("floating-tip"); if (tip) tip.style.display = "none"; }
    }));
  }

  // ---------------------------------------------------------------- powder banner
  function renderPowderBanner() {
    const el = $("powder-banner");
    if (!el || !snowData) return;
    const fav = Prefs.get("favResort"), thr = +Prefs.get("alertThreshold");
    const resort = snowData.resorts[fav];
    if (!resort || !thr) { el.hidden = true; return; }
    const summit = ((resort.sources || {}).open_meteo || {}).summit || {};
    const hit = (summit.daily_forecast || []).slice(0, 8).find(d => (d.snow_p50 ?? d.snowfall_inches ?? 0) >= thr);
    const key = hit ? `dismissed:${fav}:${hit.date}:${thr}` : null;
    let dismissed = false;
    try { dismissed = key && localStorage.getItem(key) === "1"; } catch (e) {}
    if (!hit || dismissed) { el.hidden = true; return; }
    const d = new Date(hit.date + "T12:00");
    const today = hit.date === new Date().toLocaleDateString("en-CA");
    const range = hit.snow_p10 != null ? ` <span>(${U.snowBare(hit.snow_p10)}–${U.snow(hit.snow_p90)}, p10–p90)</span>` : "";
    el.innerHTML = `<svg class="lead"><use href="#i-sparkle"/></svg>
      <div class="msg"><b>Snowfall alert (${U.snow(thr, 0)}+) · ${resort.short_name || resort.name} summit, ${today ? "today" : dayName(d) + " " + d.toLocaleDateString([], { month: "short", day: "numeric" })}:</b> median ${U.snow(hit.snow_p50 ?? hit.snowfall_inches)}${range}</div>
      <button class="go" type="button">See outlook</button>
      <button class="x" type="button" title="Dismiss for this storm"><svg><use href="#i-close"/></svg></button>`;
    el.hidden = false;
    el.querySelector(".go").onclick = () => { setResort(fav); $("outlook").scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" }); };
    el.querySelector(".x").onclick = () => { try { localStorage.setItem(key, "1"); } catch (e) {} el.hidden = true; };
  }

  // ---------------------------------------------------------------- settings
  function syncSettingsUI() {
    document.querySelectorAll("#settings-pop .seg").forEach(seg => {
      const cur = String(Prefs.get(seg.dataset.pref));
      seg.querySelectorAll(".seg-btn").forEach(b => b.classList.toggle("active", b.dataset.val === cur));
    });
    const fav = Prefs.get("favResort");
    document.querySelectorAll(".tab-btn").forEach(b => {
      b.classList.toggle("is-fav", b.dataset.resort === fav);
      b.title = b.dataset.resort === fav ? "Home resort" : "";
    });
    // snow threshold labels follow units
    document.querySelectorAll('#settings-pop [data-pref="alertThreshold"] .seg-btn').forEach(b => {
      const v = +b.dataset.val; if (v) b.textContent = U.metricSnow() ? `${Math.round(v * 2.54 / 5) * 5}cm+` : `${v}"+`;
    });
  }

  // ---------------------------------------------------------------- count-up
  function countUp() {
    document.querySelectorAll("[data-count]").forEach(el => {
      const target = parseFloat(el.dataset.target);
      if (isNaN(target)) return;
      const from = parseFloat(el.dataset.shown || "0");
      el.dataset.shown = target;
      if (reduceMotion) { el.textContent = Math.round(target); return; }
      const t0 = performance.now(), dur = 900;
      const step = t => {
        const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3);
        el.textContent = Math.round(from + (target - from) * e);
        if (k < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    });
  }

  // ---------------------------------------------------------------- control
  function setHour(h) {
    const n = (state.tl.summit || []).length;
    state.hour = Math.max(0, Math.min(n - 1, h));
    updateScene(state.hour);
  }

  function togglePlay(force) {
    const btn = $("btn-play");
    const play = force ?? !state.playing;
    if (state.playing) { clearInterval(state.playing); state.playing = null; }
    if (play) {
      if (state.hour >= (state.tl.summit || []).length - 1) setHour(0);
      state.playing = setInterval(() => {
        if (state.hour >= (state.tl.summit || []).length - 1) return togglePlay(false);
        setHour(state.hour + 1);
      }, 260);
    }
    if (btn) btn.innerHTML = `<svg><use href="#i-${state.playing ? "pause" : "play"}"/></svg>`;
  }

  function onRender(e) {
    const resort = e.detail.resort;
    const resortChanged = !state.resort || state.resort.id !== resort.id;
    state.resort = resort;
    const om = (resort.sources || {}).open_meteo || {};
    state.tl = om.elevation_timelines && om.elevation_timelines.summit ? om.elevation_timelines : { summit: om.hourly_timeline || [], mid: [], base: [] };
    state.profile = om.vertical_profile || [];
    window.__snowTier = window.__snowTier || "summit";
    if (resortChanged) buildScene(resort);
    buildScrubDays();
    setHour(resortChanged ? 0 : state.hour);
    renderVerdict(resort);
    renderOutlook(resort);
    renderPowderBanner();
    syncSettingsUI();
    countUp();
  }

  function setupChrome() {
    // scrubber
    const rng = $("time-scrubber");
    rng && rng.addEventListener("input", () => { togglePlay(false); setHour(+rng.value); });
    $("btn-play") && $("btn-play").addEventListener("click", () => togglePlay());
    $("best-when") && $("best-when").addEventListener("click", e => { const h = e.currentTarget.dataset.hour; if (h != null) setHour(+h); });

    // snow toggle (persisted per viewer)
    const tog = $("toggle-snowfx");
    let pref = null;
    try { pref = localStorage.getItem("snowfx"); } catch (e) {}
    const on = pref == null ? !reduceMotion : pref === "1";
    if (tog) {
      tog.checked = on; snowFx.setEnabled(on);
      tog.addEventListener("change", () => { snowFx.setEnabled(tog.checked); try { localStorage.setItem("snowfx", tog.checked ? "1" : "0"); } catch (e) {} });
    }

    // sources popover
    const pill = $("source-pill"), pop = $("source-pop");
    if (pill && pop) {
      pill.addEventListener("click", ev => { ev.stopPropagation(); pop.hidden = !pop.hidden; pill.setAttribute("aria-expanded", String(!pop.hidden)); });
      document.addEventListener("click", ev => { if (!pop.hidden && !pop.contains(ev.target)) { pop.hidden = true; pill.setAttribute("aria-expanded", "false"); } });
    }

    // settings popover
    const sBtn = $("btn-settings"), sPop = $("settings-pop");
    if (sBtn && sPop) {
      sBtn.addEventListener("click", ev => { ev.stopPropagation(); sPop.hidden = !sPop.hidden; sBtn.setAttribute("aria-expanded", String(!sPop.hidden)); syncSettingsUI(); });
      document.addEventListener("click", ev => { if (!sPop.hidden && !sPop.contains(ev.target) && ev.target !== sBtn) { sPop.hidden = true; sBtn.setAttribute("aria-expanded", "false"); } });
      sPop.querySelectorAll(".seg").forEach(seg => seg.addEventListener("click", ev => {
        const b = ev.target.closest(".seg-btn"); if (!b) return;
        const key = seg.dataset.pref;
        Prefs.set(key, key === "alertThreshold" ? +b.dataset.val : b.dataset.val);
        syncSettingsUI();
        if (key === "favResort" || key === "alertThreshold") renderPowderBanner();
      }));
    }
    document.addEventListener("keydown", e => { if (e.key === "Escape" && sPop && !sPop.hidden) sPop.hidden = true; });

    // explainer
    const exBtn = $("btn-explainer"), ex = $("explainer");
    exBtn && exBtn.addEventListener("click", () => { ex.hidden = !ex.hidden; exBtn.setAttribute("aria-expanded", String(!ex.hidden)); exBtn.textContent = ex.hidden ? "How to read this" : "Hide explainer"; });

    // shortcuts
    const dlg = $("shortcuts-dialog");
    $("btn-shortcuts") && $("btn-shortcuts").addEventListener("click", () => dlg.showModal());
    document.addEventListener("keydown", e => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const tag = (e.target.tagName || "").toLowerCase();
      if (tag === "input" && e.target.type !== "range" && e.target.type !== "checkbox") return;
      if (tag === "textarea" || e.target.isContentEditable) return;
      const k = e.key.toLowerCase();
      if (k === "1") setResort("palisades_tahoe");
      else if (k === "2") setResort("alpine_meadows");
      else if (k === "b" || k === "m" || k === "s") setTier({ b: "base", m: "mid", s: "summit" }[k]);
      else if (k === " ") { e.preventDefault(); togglePlay(); }
      else if ((k === "arrowright" || k === "arrowleft") && e.target.type !== "range") { e.preventDefault(); togglePlay(false); setHour(state.hour + (k === "arrowright" ? 1 : -1)); }
      else if (k === "f" && tog) { tog.checked = !tog.checked; tog.dispatchEvent(new Event("change")); }
      else if (k === "r") $("btn-refresh") && $("btn-refresh").click();
      else if (k === "?") dlg.open ? dlg.close() : dlg.showModal();
    });

    // scroll-spy
    const links = [...document.querySelectorAll(".section-nav a")];
    if ("IntersectionObserver" in window) {
      const io = new IntersectionObserver(entries => {
        entries.forEach(en => {
          if (!en.isIntersecting) return;
          links.forEach(a => a.classList.toggle("active", a.getAttribute("href") === `#${en.target.id}`));
        });
      }, { rootMargin: "-45% 0px -50% 0px" });
      links.forEach(a => { const s = document.querySelector(a.getAttribute("href")); s && io.observe(s); });

      // entry motion
      const blocks = document.querySelectorAll(".block"); // hero stays static: above-the-fold content never waits on motion
      if (!reduceMotion) {
        blocks.forEach(b => b.classList.add("reveal"));
        const rv = new IntersectionObserver(es => es.forEach(en => { if (en.isIntersecting) { en.target.classList.add("in"); rv.unobserve(en.target); } }), { threshold: 0.08 });
        blocks.forEach(b => rv.observe(b));
        setTimeout(() => blocks.forEach(b => b.classList.add("in")), 2500); // never leave content hidden
      }
    }
  }

  document.addEventListener("snow:render", onRender);
  document.addEventListener("snow:tier", e => {
    window.__snowTier = e.detail.tier;
    if (state.resort) { renderOutlook(state.resort); updateScene(state.hour); }
  });
  document.addEventListener("DOMContentLoaded", () => { setupChrome(); snowFx.init(); });
})();
