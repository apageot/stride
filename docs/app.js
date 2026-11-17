(() => {
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  document.documentElement.setAttribute("data-theme", "techy"); // style unique
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch {} },
  };
  const pace = (s) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, "0")}`;
  const km = (x) => String(x).replace(".", ",");
  const D = (iso) => new Date(iso + "T12:00:00");
  const fmt = (iso, o) => new Intl.DateTimeFormat("fr-FR", o).format(D(iso));
  const addDays = (iso, n) => { const d = D(iso); d.setDate(d.getDate() + n); return d.toISOString().slice(0, 10); };

  const ZONES = { ef: "Endurance", seuil: "Seuil", specifique: "Allure 10 km", vma: "VMA" };
  const HEIGHT = { ef: 0.42, recup: 0.24, seuil: 0.7, specifique: 0.82, vma: 1, test: 1, libre: 0.9 };
  const VCOL = { reussie: "var(--sauge-bar)", correcte: "var(--abricot-bar)", a_revoir: "var(--framboise-bar)", incomplete: "var(--framboise-bar)" };
  const VICON = { reussie: "✓", correcte: "✓", a_revoir: "!", incomplete: "!" };
  const KIND = { bonus: "Footing bonus", vma: "VMA", seuil: "Seuil", specifique: "Allure 10 km", test: "Test", course: "Course", petite: "Footing", longue: "Sortie longue" };

  let data, wi = 0;

  // ---------- séances : type, couleurs, titres ----------
  const kindOf = (s) => (s.sous_type === "ef" ? s.type : s.sous_type);
  const colorKind = (s) => { const k = kindOf(s); return k === "course" ? "test" : k === "bonus" ? "petite" : k; };
  const theme = (s) => { const k = colorKind(s); return `--tbg:var(--c-${k});--tfg:var(--f-${k});--ik:var(--i-${k})`; };
  function titleParts(s) {
    const [a, b] = s.titre.split(" · ");
    if (b) return [a, b];
    if (s.titre.startsWith("Footing + ")) return ["Footing", `${Math.round(s.etapes[0].duree_s / 60)} min + lignes droites`];
    if (s.optionnelle) return ["Footing bonus", `${Math.round(s.duree_estimee_s / 60)} min · facultatif`];
    return [s.titre, `${Math.round(s.duree_estimee_s / 60)} min`];
  }
  const allSessions = () => data.semaines.flatMap((w) => w.seances.map((s) => ({ s, w })));

  // ---------- profil de séance ----------
  function flat(steps, out = []) {
    for (const s of steps) {
      if (s.k === "repeat") for (let i = 0; i < s.fois; i++) flat(s.etapes, out);
      else out.push(s);
    }
    return out;
  }
  function stepSec(s) {
    if (s.duree_s) return s.duree_s;
    const p = s.allure ? (s.allure[0] + s.allure[1]) / 2 : s.zone === "test" ? 270 : 380;
    return (s.distance_m / 1000) * p;
  }
  const zoneOf = (s) => (s.k === "recup" ? "recup" : s.zone || "ef");
  function profile(session, lg, stagger) {
    const st = flat(session.etapes);
    const total = st.reduce((a, s) => a + stepSec(s), 0);
    return `<div class="prof${lg ? " lg" : ""}">${lg ? '<span class="grid"></span>' : ""}${st.map((s, i) => {
      const z = zoneOf(s);
      return `<i class="z-${z}" style="flex:${(stepSec(s) / total).toFixed(4)};height:${HEIGHT[z] * 100}%;animation-delay:${stagger ? 150 + i * 22 : 0}ms"></i>`;
    }).join("")}</div>`;
  }
  // motif décoratif : le profil de la séance échantillonné en fines barres, façon onde
  function metricOf(s) {
    const [, t] = titleParts(s);
    const m = t.match(/^(\d+) × ([\d,]+) ?(m|km|min)$/);
    if (m) return `${m[1]}×${m[2]}<em>${m[3]}</em>`;
    const mins = s.etapes[0].k === "continu" ? Math.round(s.etapes[0].duree_s / 60) : Math.round(s.duree_estimee_s / 60);
    if (s.sous_type === "test") return `5<em>km</em>`;
    return `${mins}<em>min</em>`;
  }
  function pattern(s) {
    const st = flat(s.etapes), total = st.reduce((a, x) => a + stepSec(x), 0), N = 30;
    let acc = 0;
    const cuts = st.map((x) => { acc += stepSec(x); return { end: acc / total, z: zoneOf(x) }; });
    const bars = [...Array(N)].map((_, i) => {
      const t = (i + 0.5) / N, z = (cuts.find((c) => t <= c.end) || cuts[cuts.length - 1]).z;
      const wave = z === "ef" || z === "recup" ? 0.1 * Math.sin(i * 1.7) + 0.06 * Math.sin(i * 0.6) : 0;
      return `<i style="height:${Math.max(12, (HEIGHT[z] + wave) * 100)}%;animation-delay:${150 + i * 18}ms"></i>`;
    }).join("");
    return `<div class="pat"><div class="prof">${bars}</div></div>`;
  }
  function difficulty(s) {
    const st = s.sous_type;
    let d = st === "ef" ? (s.type === "longue" ? (s.duree_estimee_s >= 4800 ? 3 : 2) : 1)
      : st === "seuil" ? 3 : st === "specifique" ? 4 : st === "vma" ? 4 : 5;
    if (s.allegee && d > 1) d--;
    const mot = ["Facile", "Modéré", "Soutenu", "Intense", "Maximal"][d - 1] || "Facile";
    return `<b class="dw">${mot}</b><span class="dsq">${[1, 2, 3, 4, 5].map((i) => `<i class="${i <= d ? "on" : ""}"></i>`).join("")}<em>${d}/5</em></span>`;
  }

  // ---------- niveau + courbe ----------
  function level() {
    const n = data.niveau, o = data.objectif;
    const gap = n.prediction_s - o.s;
    const pts = [...data.historique];
    if (pts[pts.length - 1].date !== data.aujourdhui) pts.push({ date: data.aujourdhui, prediction_s: n.prediction_s });
    const gapTxt = gap > 0 ? `objectif ${esc(o.temps)} · <b>−${gap >= 60 ? pace(gap) : gap + " s"}</b>` : `<b>Objectif atteint</b>`;
    let viz;
    if (pts.length >= 3) {
      const W = document.documentElement.dataset.theme === "techy" ? 330 : 150, H = 64, t0 = D(pts[0].date).getTime(), t1 = Math.max(D(pts[pts.length - 1].date).getTime(), t0 + 1);
      const vals = pts.map((p) => p.prediction_s).concat(o.s);
      const hi = Math.max(...vals) + 15, lo = Math.min(...vals) - 15;
      const X = (p) => ((D(p.date).getTime() - t0) / (t1 - t0)) * W;
      const Y = (v) => ((v - lo) / (hi - lo)) * H;
      const line = pts.map((p, i) => `${i ? "L" : "M"}${X(p).toFixed(1)},${Y(p.prediction_s).toFixed(1)}`).join(" ");
      const last = pts[pts.length - 1], gy = Y(o.s);
      viz = `<svg class="spark" viewBox="0 -8 ${W} ${H + 16}">
          <line class="goal" x1="0" x2="${W}" y1="${gy}" y2="${gy}"/>
          <text class="goal-t" x="${W}" y="${gy - 5}" text-anchor="end">${esc(o.temps)}</text>
          <path class="line" d="${line}"/>
          ${pts.slice(0, -1).map((p) => `<circle class="pt" cx="${X(p)}" cy="${Y(p.prediction_s)}" r="3.5"/>`).join("")}
          <circle class="now" cx="${X(last)}" cy="${Y(last.prediction_s)}" r="5"/>
        </svg>`;
    } else {
      const prog = gap > 0 ? Math.max(0.04, Math.min(1, (n.depart_s - n.prediction_s) / Math.max(1, n.depart_s - o.s))) : 1;
      viz = `<div class="lbar"><div class="lt"><i style="transform:scaleX(${prog})"></i></div><div class="ll"><span>${pace(n.depart_s)}</span><span>${esc(o.temps)}</span></div></div>`;
    }
    const span = Math.max(1, n.depart_s - o.s);
    const pos = Math.max(0, Math.min(1, (n.depart_s - n.prediction_s) / span));
    const ticks = [...Array(41)].map((_, i) => `<i class="${i % 5 ? "" : "maj"}"></i>`).join("");
    const ruler = `${predCurve(n, o)}
      <div class="tx mini"><div><small>VDOT</small><b>${data.niveau.vdot}</b></div><div><small>Allure cible</small><b>${esc(o.allure)}<em>/km</em></b></div><div><small>Reste à gagner</small><b class="v">${gap > 0 ? gap : 0}<em>s</em></b></div></div>`;
    const h = new Date().getHours();
    const hello = `${h < 5 || h >= 18 ? "Bonsoir" : "Bonjour"}${data.prenom ? " " + esc(data.prenom) : ""}`;
    const cw = data.semaines.find((w) => w.debut <= data.aujourdhui && data.aujourdhui <= w.fin) || data.semaines[data.semaines.length - 1];
    const main = cw.seances.filter((x) => !x.optionnelle), done = main.filter((x) => x.statut === "faite");
    const left = main.filter((x) => x.statut !== "faite").map((x) => (KIND[kindOf(x)] || x.titre).toLowerCase());
    const say = !done.length ? `Nouvelle semaine : ${main.length} séances à caser quand tu veux.`
      : !left.length ? "Semaine bouclée. Profite de la récup."
      : `${done.length} sur ${main.length} cette semaine. Il reste ${left.map((x) => "la " + x).join(" et ")}.`;
    $("#level").innerHTML = `
      <div class="tx hello rise"><b>${hello}</b><span>${esc(say)}</span></div>
      <div class="tx sec rise" style="--d:40ms"><b>[01]</b> Niveau<span>VDOT ${data.niveau.vdot}</span></div>
      <button class="level rise ${pts.length >= 3 ? "" : "nobar"}" style="--d:90ms" id="levelBtn">
        <div>
          <small>Niveau 10 km <span>›</span></small>
          <span class="chrono focusable" id="chrono" data-t="${esc(n.prediction)}">${esc(n.prediction)}</span>
          <span class="gap">${gapTxt}</span><button class="modechip" id="modeChip">${modeTxt()}</button>
        </div>
        <i class="tx tx-cross"></i><span class="tx tx-time">${stamp()}</span>
        ${viz}${ruler}
      </button>`;
    $("#levelBtn").onclick = openPlan;
    countDown($("#chrono"), n.depart_s, n.prediction_s);
  }
  function stamp() {
    const d = new Date(), p = (x) => String(x).padStart(2, "0");
    return `${p(d.getDate())}.${p(d.getMonth() + 1)}.${String(d.getFullYear()).slice(2)}  ${p(d.getHours())}:${p(d.getMinutes())}`;
  }
  function pixband() {
    const el = $("#pixband");
    if (!el) return;
    let seed = 7, out = "";
    const rnd = () => ((seed = (seed * 9301 + 49297) % 233280) / 233280);
    const W = el.clientWidth || 390, cols = Math.floor(W / 12);
    for (let r = 0; r < 10; r++) for (let c = 0; c < cols; c++) {
      if (rnd() < 0.85 - r * 0.085) out += `<i style="left:${c * 12}px;top:${r * 12}px;opacity:${(1 - r * 0.07).toFixed(2)}"></i>`;
    }
    el.innerHTML = out;
  }
  function countDown(el, from, to) {
    if (from === to || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const t0 = performance.now(), dur = 1300;
    const tick = (t) => {
      const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      el.textContent = pace(from + (to - from) * e);
      if (k < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  // ---------- semaine : carrés de progression + cartes ----------
  function week(dir) {
    const w = data.semaines[wi];
    const squares = w.seances.filter((x) => !x.optionnelle || x.statut === "faite").map((x, i) => {
      const st = x.statut === "faite" ? "done" : x.statut === "manquee" ? "miss" : "";
      const ic = st === "done" ? "✓" : st === "miss" ? "×" : "";
      return `<i class="sq ${st}" style="--d:${120 + i * 80}ms" title="${esc(KIND[kindOf(x)])}"></i>`;
    }).join("");
    const cards = w.seances.map((s, i) => {
      const [k, t] = titleParts(s);
      const v = s.analyse && s.analyse.verdict;
      let sub, metric;
      if (s.statut === "faite") {
        const ic = v === "a_revoir" || v === "incomplete" ? `<i class="vk ko">!</i>` : `<i class="vk">✓</i>`;
        sub = `${ic}${fmt(s.date_realisee, { weekday: "short", day: "numeric" })} · ${s.analyse.realise.allure}/km`;
        metric = `${km(s.analyse.realise.distance_km)}<em>km</em>`;
      } else {
        sub = s.statut === "manquee" ? "Pas faite" : s.optionnelle ? "Facultatif" : esc(KIND[kindOf(s)] === k ? "À faire" : KIND[kindOf(s)]);
        metric = metricOf(s);
      }
      return `<button class="sc2 rise ${s.statut === "manquee" ? "missed" : ""} ${s.optionnelle && s.statut !== "faite" ? "opt" : ""}" style="${theme(s)};--d:${200 + i * 70}ms" data-i="${i}">
        <span class="tx idx">${String(i + 1).padStart(2, "0")}</span>
        <div class="sc2-t"><b>${esc(k)}</b><span>${sub}</span></div>
        <div class="sc2-m">${metric}</div></button>`;
    }).join("");
    const done = w.seances.filter((x) => x.analyse);
    const secs = done.reduce((u, x) => u + (x.analyse.realise.duree_s || 0), 0);
    const kmd = done.reduce((u, x) => u + x.analyse.realise.distance_km, 0);
    const hud = `<div class="tx hud">
      <div><small>Distance</small><b>${km(w.km_faits || 0)}<em>km</em></b></div>
      <div><small>Temps</small><b>${secs ? `${Math.floor(secs / 3600)}:${String(Math.round(secs / 60) % 60).padStart(2, "0")}` : "0:00"}<em>h</em></b></div>
      <div><small>Allure</small><b>${kmd ? pace(secs / kmd) : "–"}<em>/km</em></b></div>
      <div><small>Séances</small><b>${w.seances.filter((x) => x.statut === "faite" && !x.optionnelle).length}<em>/${w.seances.filter((x) => !x.optionnelle).length}</em></b></div>
    </div>`;
    const libres = w.libres.length ? `<div class="libre">+ ${w.libres.length} sortie${w.libres.length > 1 ? "s" : ""} libre${w.libres.length > 1 ? "s" : ""}</div>` : "";
    const kmTxt = w.km_faits ? `${km(w.km_faits)} / ${km(w.km_prevus)}` : km(w.km_prevus);
    $("#week").innerHTML = `
      <div class="tx sec rise" style="--d:120ms">Semaine<span>C${String(w.cycle).padStart(2, "0")} / S${String(w.num).padStart(2, "0")}</span></div>
      <div class="wk-head rise" style="--d:150ms">
        <button id="wPrev" ${wi === 0 ? "disabled" : ""} aria-label="Semaine précédente">‹</button>
        <div class="t" style="flex:1;padding-left:4px"><b>${esc(w.label)}</b><span>${fmt(w.debut, { day: "numeric" })}–${fmt(w.fin, { day: "numeric", month: "short" })} · S${w.num}</span></div>
        <button id="wNext" ${wi === data.semaines.length - 1 ? "disabled" : ""} aria-label="Semaine suivante">›</button>
      </div>
      <div class="wk-body ${dir ? (dir > 0 ? "slide-l" : "slide-r") : ""}">
        <div class="prog"><div class="squares">${squares}</div><div class="pkm"><b>${km(w.km_faits || 0)}</b> / ${km(w.km_prevus)} km</div>
          ${secs ? `<div class="pmore"><span>${Math.floor(secs / 3600)}h${String(Math.round(secs / 60) % 60).padStart(2, "0")}</span><span>${pace(secs / kmd)}/km</span></div>` : ""}</div>
        <div class="cards">${cards}</div>${libres}
      </div>`;
    $("#wPrev").onclick = () => go(-1);
    $("#wNext").onclick = () => go(1);
    document.querySelectorAll(".sc2").forEach((b) => (b.onclick = () => openSession(w.seances[+b.dataset.i], w)));
    if (dir) document.querySelectorAll(".sc2").forEach((el) => el.classList.remove("rise"));
  }
  function go(d) {
    const n = wi + d;
    if (n < 0 || n >= data.semaines.length) return;
    wi = n; week(d);
  }
  let tx = null, ty = null;
  $("#week").addEventListener("touchstart", (e) => { tx = e.touches[0].clientX; ty = e.touches[0].clientY; }, { passive: true });
  $("#week").addEventListener("touchend", (e) => {
    if (tx === null) return;
    const dx = e.changedTouches[0].clientX - tx, dy = e.changedTouches[0].clientY - ty;
    if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5) go(dx < 0 ? 1 : -1);
    tx = null;
  });

  // ---------- plan : allures + ajustements ----------
  function openPlan() {
    const a = data.allures;
    const cols = { ef: "petite", seuil: "seuil", specifique: "spe", vma: "vma" };
    const ic = { up: "↑", hold: "=", down: "↓", info: "·" };
    $("#planBody").innerHTML = `
      <div class="pl-h">Tes allures</div>
      <div class="pl-s">Mises à jour par tes tests et tes fractions réussies</div>
      <div class="paces">${Object.keys(ZONES).map((k) => `
        <div class="pc" style="--tbg:var(--c-${cols[k]});--tfg:var(--f-${cols[k]})"><small>${ZONES[k]}</small><div>${k === "ef" && a.ef.fc ? `<b>${a.ef.fc[0]}–${a.ef.fc[1]}</b><em> bpm</em>` : `<b>${a[k].texte}</b><em> /km</em>`}</div></div>`).join("")}</div>
      ${data.journal.length ? `<div class="pl-h" style="padding-top:36px;font-size:26px">Ajustements</div>
      <div class="card">${data.journal.slice(0, 6).map((j) => `
        <div class="jr"><i class="${j.type}">${ic[j.type]}</i><div>${esc(j.texte)}<small>${fmt(j.date, { weekday: "long", day: "numeric", month: "long" })}</small></div></div>`).join("")}</div>` : ""}`;
    open("#plan");
  }

  // ---------- fiche séance ----------
  const ZLABEL = { ef: "Endurance", seuil: "Seuil", specifique: "Allure 10 km", vma: "VMA", test: "À fond", libre: "Accélération", recup: "Récupération" };
  const BAR = { ef: "var(--ef)", recup: "var(--recup)", seuil: "var(--seuil)", specifique: "var(--spe)", vma: "var(--vma)", test: "var(--test-bar)", libre: "var(--vma)" };
  // ---------- chaleur : allures corrigées (+0,5 %/°C au-dessus de 15 °C ressentis, max +10 %) ----------
  let HEAT = { t: null, f: 1 }, HF = 1;
  const heatF = (t) => (t == null || t <= 15 ? 1 : 1 + Math.min(0.1, 0.005 * (t - 15)));
  async function loadHeat() {
    if (data.demo) { HEAT = { t: 27, f: heatF(27), demo: true }; return; }
    const l = data.lieu; if (!l) return;
    try {
      const r = await fetch(`https://api.open-meteo.com/v1/forecast?latitude=${l.lat}&longitude=${l.lon}&current=apparent_temperature&hourly=apparent_temperature&forecast_hours=3&timezone=auto`);
      const j = await r.json();
      const v = [j.current && j.current.apparent_temperature, ...((j.hourly && j.hourly.apparent_temperature) || [])].filter((x) => x != null);
      if (v.length) { const t = Math.max(...v); HEAT = { t, f: heatF(t) }; }
    } catch (e) { /* hors ligne : pas de correction */ }
  }
  const hp = (v) => v * HF; // allure corrigée pour l'affichage
  document.addEventListener("click", (e) => {
    if (!e.target.closest("#tchip")) return;
    toast(HEAT.f > 1 ? `${Math.round(HEAT.t)}° ressentis${HEAT.demo ? " (démo)" : ""} : allures ralenties de ${Math.round((HEAT.f - 1) * 100)} %` : `${Math.round(HEAT.t)}° ressentis : pas de correction sous 15°`);
  });
  function qty(s) {
    if (s.distance_m) return s.distance_m >= 1000 ? `${km(s.distance_m / 1000)} km` : `${s.distance_m} m`;
    const t = s.duree_s;
    if (t < 60) return `${t} s`;
    if (t % 60) return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`;
    return `${t / 60} min`;
  }
  // une ligne de données sous chaque étape : la cible chiffrée + ce que ça veut dire
  // sous chaque étape : la fourchette d'allure (≈ ±5 %, soit ~10 % de delta) et le cardio
  function stepData(s, z) {
    const A = data.allures, fm = data.fc_max;
    const bpm = (lo, hi) => (fm ? `${Math.round(fm * lo)}–${Math.round(fm * hi)} bpm` : null);
    const band = (c) => `${pace(hp(c) * 0.95)}–${pace(hp(c) * 1.05)}/km`;
    const pz = (k) => (A[k] ? `${pace(hp(A[k].s[1]))}–${pace(hp(A[k].s[0]))}/km` : null);
    const efSlow = A.ef ? A.ef.s[0] : 380;
    const efFc = A.ef && A.ef.fc ? `${A.ef.fc[0]}–${A.ef.fc[1]} bpm` : bpm(.65, .77);
    let p, h;
    if (s.k === "echauffement" || z === "ef") { p = pz("ef"); h = efFc; }
    else if (s.k === "retour") { p = band(efSlow + 20); h = bpm(.6, .7); }
    else if (s.k === "recup") { p = band(efSlow + 40); h = bpm(.6, .7); }
    else if (z === "libre") { p = A.vma ? band(A.vma.s[1] - 5) : null; h = bpm(.88, .95); }
    else if (z === "seuil") { p = pz("seuil"); h = bpm(.86, .9); }
    else if (z === "specifique") { p = pz("specifique"); h = bpm(.88, .92); }
    else if (z === "vma") { p = pz("vma"); h = bpm(.95, 1); }
    else if (z === "test") { p = null; h = bpm(.92, 1); }
    else return "";
    if (s.allure) p = `${pace(hp(s.allure[1]))}–${pace(hp(s.allure[0]))}/km`; // la cible réelle de l'étape
    return `<div class="sdt">${[p && `<span class="k">${p}</span>`, h && `<span>${h}</span>`].filter(Boolean).join("")}</div>`;
  }
  function stepCard(s) {
    const z = zoneOf(s);
    let main;
    if (s.k === "recup") main = `${qty(s)} <span class="dim">trot</span>`;
    else if (s.fc) main = `${qty(s)} <span class="dim">à</span> <span class="nw">${s.fc[0]} - ${s.fc[1]} <span class="dim">bpm</span></span>`;
    else if (s.allure) main = `${qty(s)} <span class="dim">à</span> <span class="nw">${pace(hp(s.allure[1]))} - ${pace(hp(s.allure[0]))} <span class="dim">/km</span></span>`;
    else if (s.fin_tour) main = `${qty(s)} <span class="dim">puis Tour</span>`;
    else main = qty(s);
    const lbl = s.k === "echauffement" ? "Échauffement" : s.k === "retour" ? "Retour au calme" : ZLABEL[z];
    return `<div class="sc"><i style="background:${BAR[z]}"></i><div><small>${lbl}</small><b>${main}</b>${stepData(s, z)}</div></div>`;
  }
  const stepCards = (steps) => steps.map((s) => s.k === "repeat"
    ? `<div class="sbox rep"><div class="in">${s.etapes.map(stepCard).join("")}</div><div class="loop"><span>↻</span><b>${s.fois}</b></div></div>`
    : `<div class="sbox">${stepCard(s)}</div>`).join("");

  const sgn = (d) => (d === 0 ? "0 s" : `${d > 0 ? "+" : "−"}${Math.abs(d)} s`);
  const delta = (p, [slow, fast]) => (p > slow ? Math.round(p - slow) : p < fast ? -Math.round(fast - p) : 0);
  const parsePace = (t) => { const [m, s] = t.split(":").map(Number); return m * 60 + s; };
  function avgPace(s) {
    const a = s.analyse;
    if (a.tours.length) return a.tours.reduce((u, t) => u + t.allure_s, 0) / a.tours.length;
    if (a.fc_moy) return null;
    return a.realise.allure ? parsePace(a.realise.allure) : null;
  }
  function compare(s) {
    if (!s.analyse || ["test", "course"].includes(s.sous_type)) return "";
    const k = kindOf(s);
    const prev = allSessions().map((x) => x.s).filter((x) => x.analyse && kindOf(x) === k && x.date_realisee < s.date_realisee)
      .sort((a, b) => (a.date_realisee < b.date_realisee ? -1 : 1)).pop();
    if (!prev) return "";
    const a = avgPace(s), b = avgPace(prev);
    if (a == null || b == null) return "";
    const d = Math.round(a - b);
    const name = { bonus: "ton dernier footing", petite: "ton dernier footing", longue: "ta dernière sortie longue", vma: "ta dernière VMA", seuil: "ton dernier seuil", specifique: "ta dernière allure 10 km" }[k];
    return `<div class="cmp ${d < 0 ? "good" : d > 0 ? "bad" : ""}">${d < 0 ? "↑" : d > 0 ? "↓" : "="} ${sgn(d)}/km vs ${name}</div>`;
  }
  function burst() {
    const cols = ["var(--vma)", "var(--spe)", "var(--seuil)", "var(--ef)"];
    return `<span class="burst">${[...Array(12)].map((_, i) => `<i style="--a:${i * 30}deg;--c:${cols[i % 4]}"></i>`).join("")}</span>`;
  }
  // ---------- parcours sur une photo de la ville ----------
  // ordre : img/ville.jpg (ta photo) → image principale Wikipédia de la ville → fond sombre
  let cityImg = null;
  function loadCity() {
    if (cityImg !== null) return Promise.resolve(cityImg);
    const tryImg = (src) => new Promise((ok, ko) => { const i = new Image(); i.onload = () => ok(src); i.onerror = ko; i.src = src; });
    return tryImg("img/ville.jpg").catch(() => fetch(`https://fr.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(data.ville || "")}`)
      .then((r) => r.json()).then((j) => tryImg((j.originalimage || j.thumbnail).source)))
      .then((src) => (cityImg = src)).catch(() => (cityImg = ""));
  }
  function mapBlock(a) {
    const r = a.realise;
    loadCity().then((src) => { const el = document.querySelector(".cityph"); if (el && src) { el.style.backgroundImage = `url("${src}")`; el.classList.add("on"); } });
    return `<figure class="mapw">
      <div class="cityph"></div><div class="mapveil"></div>
      <figcaption class="maptop"><b>${esc(data.ville || "")}</b></figcaption>
      <div class="mapstats">
        <div><small>Distance</small><b>${r.distance_km.toFixed(2).replace(".", ",")}<em>km</em></b></div>
        <div><small>Allure</small><b>${esc(r.allure)}<em>/km</em></b></div>
        <div><small>Temps</small><b>${esc(r.duree)}</b></div>
        ${r.fc ? `<div><small>FC moy.</small><b>${r.fc}<em>bpm</em></b></div>` : ""}
      </div>
    </figure>`;
  }
  // ---------- courbe de ta prédiction 10 km ----------
  function predCurve(n, o) {
    const pts = (data.historique || []).map((p) => ({ t: D(p.date).getTime(), v: p.prediction_s }));
    const now = D(data.aujourdhui).getTime();
    if (!pts.length || pts[pts.length - 1].t < now) pts.push({ t: now, v: n.prediction_s });
    if (pts.length < 2) return "";
    // escalier : la prédiction ne bouge qu'aux tests / fractions
    const W = 340, H = 96, t0 = pts[0].t, t1 = now + (now - t0) * 0.08;
    const hi = Math.max(...pts.map((p) => p.v), o.s) + 8, lo = Math.min(...pts.map((p) => p.v), o.s) - 8;
    const X = (t) => ((t - t0) / (t1 - t0)) * W, Y = (v) => 14 + ((hi - v) / (hi - lo)) * (H - 28) ;
    let d = `M${X(pts[0].t)},${Y(pts[0].v)}`;
    pts.slice(1).forEach((p, i) => { d += ` H${X(p.t).toFixed(1)} V${Y(p.v).toFixed(1)}`; });
    const gy = Y(o.s), last = pts[pts.length - 1];
    const dm = (t) => new Date(t).toLocaleDateString("fr-FR", { day: "numeric", month: "short" }).replace(".", "").toUpperCase();
    return `<div class="tx pred"><div class="ph"><span class="pt-l">Prédiction 10 km</span><span>${pace(pts[0].v)} → <b>${pace(last.v)}</b></span></div>
      <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
        <line class="g" x1="0" x2="${W}" y1="${gy}" y2="${gy}"/><text class="gt" x="0" y="${gy + 12}">OBJECTIF ${esc(o.temps)}</text>
        <path class="ln" d="${d}"/>
        ${pts.slice(0, -1).map((p) => `<circle class="pt" cx="${X(p.t)}" cy="${Y(p.v)}" r="2.5"/>`).join("")}
        <circle class="now" cx="${X(last.t)}" cy="${Y(last.v)}" r="4"/>
      </svg>
      <div class="pl"><span>${dm(pts[0].t)}</span><span>AUJOURD'HUI</span></div></div>`;
  }
  // ---------- ressenti en un tap ----------
  const FEEL = [["facile", "Facile"], ["ok", "OK"], ["dur", "Dur"]];
  function feelBlock(s) {
    const cur = store.get("sub45_feel_" + s.id) || s.ressenti || "";
    return `<div class="feel" data-id="${esc(s.id)}"><small>Ressenti</small><div class="fopts">${FEEL.map(([k, l]) =>
      `<button data-v="${k}" class="${cur === k ? "on" : ""}">${l}</button>`).join("")}</div></div>`;
  }
  document.addEventListener("click", async (e) => {
    const b = e.target.closest(".feel button");
    if (!b) return;
    const box = b.closest(".feel"), id = box.dataset.id, v = b.dataset.v;
    box.querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
    store.set("sub45_feel_" + id, v);
    if (data.demo) { toast("Ressenti noté · le plan en tiendra compte"); return; }
    try { await dispatch({ ressenti: `${id}=${v}` }); toast("Ressenti noté · plan ajusté à la synchro"); }
    catch (err) { toast("Ressenti gardé ici, synchro impossible"); }
  });
  function serieBlock(a) {
    const sr = a.serie;
    if (!sr) return "";
    let out = "";
    if (sr.vitesse && sr.vitesse.length > 5) {
      const n = sr.vitesse.length, dur = a.realise.duree_s || 0;
      const pc = sr.vitesse.map((v) => (v > 0.5 ? Math.min(600, 1000 / v) : 600));
      const sm = pc.map((_, i) => { const w = pc.slice(Math.max(0, i - 1), i + 2); return w.reduce((u, v) => u + v, 0) / w.length; });
      const cum = []; let acc = 0;
      sr.vitesse.forEach((v) => { cum.push(acc); acc += v * (dur / n); });
      const tfmt = (sec) => `${Math.floor(sec / 60)}:${String(Math.round(sec % 60)).padStart(2, "0")}`;
      const W = 340, top = 46, H = 96, lo = Math.min(...sm), hi = Math.min(Math.max(...sm), lo + 200);
      const X = (i) => (i / (n - 1)) * W, Y = (v) => top + ((Math.min(v, hi) - lo) / ((hi - lo) || 1)) * H;
      const d = sm.map((v, i) => `${i ? "L" : "M"}${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(" ");
      const fi = sm.indexOf(lo), fx = X(fi), fy = Y(lo);
      const avg = a.realise.allure ? parsePace(a.realise.allure) : null;
      // annotation 1 : point le plus rapide
      const lx = fx > W * .55 ? fx - 150 : fx + 22, right = lx < fx;
      const anchorX = right ? lx + 142 : lx;
      let svg = `<path class="pl" d="${d}"/>
        <rect class="box" x="${fx - 7}" y="${fy - 7}" width="14" height="14"/>
        <polyline class="lead" points="${fx},${fy - 7} ${fx},12 ${anchorX},12"/><circle class="dot" cx="${anchorX}" cy="12" r="2.5"/>
        <text class="an" x="${right ? anchorX - 8 : anchorX + 8}" y="9" text-anchor="${right ? "end" : "start"}">▲ PLUS RAPIDE ${pace(lo)}/KM</text>
        <text class="am" x="${right ? anchorX - 8 : anchorX + 8}" y="21" text-anchor="${right ? "end" : "start"}">T+${tfmt(dur * fi / (n - 1))} · KM ${(cum[fi] / 1000).toFixed(1).replace(".", ",")}</text>`;
      // ligne de moyenne
      if (avg && avg >= lo && avg <= hi) {
        const ay = Y(avg);
        svg += `<line class="avg" x1="0" x2="${W}" y1="${ay}" y2="${ay}"/><text class="am" x="${W}" y="${ay - 4}" text-anchor="end">MOY ${pace(avg)}</text>`;
      }
      // annotation 2 : pic de cardio
      let base = top + H;
      if (sr.fc && sr.fc.length === n) {
        const mx = Math.max(...sr.fc), hiI = sr.fc.indexOf(mx), hx = X(hiI), hy = Y(sm[hiI]);
        const by = top + H + 26, lx2 = hx > W * .55 ? hx - 140 : hx + 20, r2 = lx2 < hx, ax2 = r2 ? lx2 + 132 : lx2;
        svg += `<circle class="ring" cx="${hx}" cy="${hy}" r="5"/>
          <polyline class="lead" points="${hx},${hy + 5} ${hx},${by} ${ax2},${by}"/><circle class="dot" cx="${ax2}" cy="${by}" r="2.5"/>
          <text class="an" x="${r2 ? ax2 - 8 : ax2 + 8}" y="${by - 3}" text-anchor="${r2 ? "end" : "start"}">♥ FC MAX ${mx} BPM</text>
          <text class="am" x="${r2 ? ax2 - 8 : ax2 + 8}" y="${by + 9}" text-anchor="${r2 ? "end" : "start"}">T+${tfmt(dur * hiI / (n - 1))} · ${Math.round(mx / (data.fc_max || mx) * 100)}% FC MAX</text>`;
        base = by + 16;
      }
      // dénivelé
      if (sr.altitude && sr.altitude.length > 5) {
        const al = sr.altitude, amin = Math.min(...al), amax = Math.max(...al), ab = base + 34;
        svg += `<path class="alt" d="${al.map((v, i) => `${i ? "L" : "M"}${((i / (al.length - 1)) * W).toFixed(1)},${(ab - ((v - amin) / ((amax - amin) || 1)) * 22).toFixed(1)}`).join(" ")}"/>
          <text class="am" x="0" y="${ab + 14}">ALT ${Math.round(amin)}–${Math.round(amax)} M</text><text class="am" x="${W}" y="${ab + 14}" text-anchor="end">D+ ${Math.round(amax - amin)} M</text>`;
        base = ab + 14;
      }
      out += `<div class="curve"><div class="chd"><small>Allure</small><span class="meta">${n} PTS · ÉCH. ${Math.round(dur / n)} S · LISSAGE 3</span></div>
        <svg viewBox="0 0 ${W} ${base + 6}">${svg}</svg></div>`;
    }
    return out ? `<div class="serie">${out}</div>` : "";
  }
  function bilan(a, s) {
    const r = a.realise;
    let rows = a.tours.map((t) => ({ n: t.n, p: t.allure_s, cible: t.cible }));
    let unit = "/km";
    const showV = (p) => (unit === "/km" ? pace(p) : Math.round(p));
    if (!rows.length && a.fc_cible) { unit = "bpm"; rows = [{ n: "FC", p: a.fc_moy, cible: [a.fc_cible[1], a.fc_cible[0]] }]; }
    else if (!rows.length && a.allure_cible && r.allure) rows = [{ n: "moy", p: parsePace(r.allure), cible: a.allure_cible }];
    let reps = "", head = "";
    if (rows.length) {
      const ds = rows.map((x) => delta(x.p, x.cible));
      const avg = Math.round(ds.reduce((u, v) => u + v, 0) / ds.length);
      head = `<div class="dhead"><span>${unit === "bpm" ? "Écart cardio" : "Écart moyen"}</span><span class="dv"><b class="${avg === 0 ? "ok" : "ko"}">${unit === "bpm" ? sgn(avg).replace(" s", "") : sgn(avg)}</b><em>${unit}</em></span></div>`;
      const all = rows.flatMap((x) => [x.p, ...x.cible]);
      const lo = Math.min(...all) - 6, hi = Math.max(...all) + 6;
      const x = (p) => ((hi - p) / (hi - lo)) * 100;
      reps = `<div class="reps">${rows.map((t, i) => `
        <div class="rep"><span class="n">${t.n}</span><span class="num">${showV(t.p)}</span>
        <div class="rail"><div class="band" style="left:${x(t.cible[0])}%;right:${100 - x(t.cible[1])}%"></div>
        <div class="pt ${ds[i] ? "lent" : ""}" style="left:${x(t.p)}%;--d:${400 + i * 90}ms"></div></div>
        <span class="dl ${ds[i] ? "ko" : "ok"}">${unit === "bpm" ? sgn(ds[i]).replace(" s", "") : sgn(ds[i])}</span></div>`).join("")}</div>`;
    } else if (a.chrono_s) {
      head = `<div class="dhead"><span>Chrono 5 km</span><b>${pace(a.chrono_s)}</b></div>`;
    }
    return `<div class="card bilan">
      <div class="verdict"><span class="vic v-${a.verdict}">${VICON[a.verdict]}</span>${a.verdict === "reussie" ? burst() : ""}${esc(a.titre)}</div>
      <p class="say">${esc(a.resume)}</p>
      ${feelBlock(s)}
      ${mapBlock(a)}
      ${compare(s)}${head}${reps}${serieBlock(a)}
      ${"" && `<div class="stats">
        <div><small>Distance</small><b>${km(r.distance_km)} km</b></div>
        <div><small>Durée</small><b>${esc(r.duree)}</b></div>
        <div><small>Allure</small><b>${esc(r.allure ?? "–")}</b></div>
        <div><small>FC moy.</small><b>${r.fc ? r.fc + " bpm" : "–"}</b></div>
      </div>`}
    </div>`;
  }

  const isSent = (s) => !!(data.garmin && data.garmin.envoyees.includes(s.id));
  function openSession(s, w) {
    const sent = isSent(s);
    const [k, t] = titleParts(s);
    HF = s.statut === "faite" || s.statut === "manquee" ? 1 : HEAT.f;
    // petite pastille température : discrète l'hiver, mise en avant quand elle corrige les allures
    const heatTag = HEAT.t != null && s.statut !== "faite" && s.statut !== "manquee"
      ? `<button class="tchip ${HF > 1 ? "hot" : ""}" id="tchip" aria-label="Température">${HF > 1 ? "☀︎" : "◦"} ${Math.round(HEAT.t)}°${HF > 1 ? ` <b>+${Math.round((HF - 1) * 100)} %</b>` : ""}</button>` : "";
    $("#detail").innerHTML = `<div class="detail">
      <div class="dh" style="${theme(s)}">${pattern(s)}
        ${s.type === "allure" && s.sous_type !== "ef" ? `<span class="tag dtag">Séance clé</span>` : ""}
        <div class="dt">${s.date_realisee ? `${data.ville ? esc(data.ville) + " · " : ""}${esc(fmt(s.date_realisee, { weekday: "long", day: "numeric", month: "long" }))}` : s.date ? esc(fmt(s.date, { weekday: "long", day: "numeric", month: "long" })) : s.optionnelle ? "Bonus · facultatif" : `Semaine du ${esc(fmt(s.semaine_debut, { day: "numeric", month: "long" }))}`}</div>
        <div class="kick">${esc(k)}</div><h2 class="big" data-t="${esc(t)}">${esc(t)}</h2>
        <div class="dkpi">
          <div><small>Durée</small><b>${Math.round(s.duree_estimee_s / 60)}<em> min</em></b></div>
          <div><small>Distance</small><b>${km(s.distance_estimee_km)}<em> km</em></b></div>
          <div class="dif"><small>Difficulté</small>${difficulty(s)}</div>
        </div>
      </div>
      <div class="instr">
        <div class="ch"><b>Instructions</b><span class="chr">${heatTag}${sent ? `<span class="tag soft">Sur ta montre</span>` : ""}</span></div>
        ${flat(s.etapes).length > 1 ? profile(s, true, true) : ""}
        <div class="scards">${stepCards(s.etapes)}</div>
      </div>
      ${s.analyse ? bilan(s.analyse, s) : ""}
      ${s.statut === "faite" || s.statut === "manquee" ? "" : `<div class="sendbar"><button class="send ${sent ? "done" : ""}" id="sendBtn">${sent ? "✓ Sur ta montre · renvoyer" : "Envoyer sur la montre"}</button></div>`}
    </div>`;
    const sb = $("#sendBtn");
    if (sb) sb.onclick = () => sendSession(s, sb, "Envoyée · synchronise ta montre");
    open("#sheet");
  }

  // ---------- envoi / synchro (workflow GitHub) ----------
  function guessRepo() {
    const h = location.hostname.match(/^([^.]+)\.github\.io$/);
    const p = location.pathname.split("/").filter(Boolean)[0];
    return h && p ? `${h[1]}/${p}` : "";
  }
  async function dispatch(inputs) {
    const token = store.get("sub45_token"), repo = store.get("sub45_repo") || guessRepo();
    if (!token || !repo) { $("#repo").value = repo; open("#settings"); return false; }
    const r = await fetch(`https://api.github.com/repos/${repo}/actions/workflows/sync.yml/dispatches`, {
      method: "POST", headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json" },
      body: JSON.stringify({ ref: "main", inputs }),
    });
    if (!r.ok) throw new Error(r.status);
    setTimeout(() => load(true), 150000);
    return true;
  }
  async function sendSession(s, btn, doneTxt) {
    if (data.demo) { toast("Démo : connecte Garmin pour envoyer"); return; }
    const before = btn.textContent;
    btn.disabled = true; btn.textContent = "Envoi…";
    try {
      if (await dispatch({ seance: s.id })) { btn.textContent = doneTxt; btn.classList.add("done"); }
      else { btn.disabled = false; btn.textContent = before; }
    } catch (e) { btn.disabled = false; btn.textContent = "Échec, vérifie le jeton"; open("#settings"); }
  }
  $("#syncBtn").onclick = async () => {
    if (data.demo) { toast("Démo : connecte Garmin pour synchroniser"); return; }
    const b = $("#syncBtn"); b.classList.add("busy"); $("#syncTxt").textContent = "Synchro…";
    try { if (await dispatch({})) $("#syncTxt").textContent = "Synchro lancée"; else b.classList.remove("busy"); }
    catch (e) { b.classList.remove("busy"); $("#syncTxt").textContent = "Échec"; open("#settings"); }
  };
  function toast(t) {
    let el = $("#toast");
    if (!el) { el = document.createElement("div"); el.id = "toast"; document.body.appendChild(el); }
    el.textContent = t; el.classList.add("on"); clearTimeout(el._t); el._t = setTimeout(() => el.classList.remove("on"), 2600);
  }
  // ---------- mode : objectif seul / course ----------
  const raceDate = () => { const v = data.demo ? store.get("sub45_course") : null; return v === null ? data.date_course : v || null; };
  function modeTxt() {
    const r = raceDate();
    if (!r) return "Objectif seul ›";
    const j = Math.round((D(r) - D(data.aujourdhui)) / 864e5);
    return `Course ${esc(fmt(r, { day: "numeric", month: "short" }))} · J−${Math.max(0, j)} ›`;
  }
  let modeSel = "objectif";
  function paintMode() {
    document.querySelectorAll(".mopt").forEach((b) => b.classList.toggle("on", b.dataset.m === modeSel));
    $(".mdate").style.display = modeSel === "course" ? "" : "none";
  }
  document.addEventListener("click", (e) => {
    if (e.target.closest("#modeChip")) {
      const r = raceDate(); modeSel = r ? "course" : "objectif";
      $("#raceDate").value = r || ""; $("#raceDate").min = data.aujourdhui;
      paintMode(); open("#mode");
    }
    const m = e.target.closest(".mopt"); if (m) { modeSel = m.dataset.m; paintMode(); }
  });
  $("#saveMode").onclick = async () => {
    const d = modeSel === "course" ? $("#raceDate").value : "";
    if (modeSel === "course" && !d) { toast("Choisis une date"); return; }
    close($("#mode"));
    if (data.demo) { store.set("sub45_course", d); level(); toast(d ? "Mode course · démo" : "Objectif seul · démo"); return; }
    try { if (await dispatch({ date_course: d || "aucune" })) toast("Plan recalculé à la synchro (≈ 2 min)"); }
    catch (err) { toast("Échec, vérifie le jeton"); open("#settings"); }
  };
  $("#saveSettings").onclick = () => {
    store.set("sub45_repo", $("#repo").value.trim()); store.set("sub45_token", $("#token").value.trim());
    close($("#settings"));
  };

  // ---------- feuilles ----------
  function open(id) {
    const el = $(id); el.classList.add("open"); el.setAttribute("aria-hidden", "false");
    el.querySelector(".sheet-card").scrollTop = 0; document.body.classList.add("sheet-open");
  }
  function close(el) {
    el.classList.remove("open"); el.setAttribute("aria-hidden", "true");
    if (!document.querySelector(".sheet.open")) document.body.classList.remove("sheet-open");
  }
  document.querySelectorAll(".sheet").forEach((sh) => sh.addEventListener("click", (e) => { if (e.target.closest("[data-close]")) close(sh); }));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") document.querySelectorAll(".sheet.open").forEach(close); });

  // ---------- léger parallaxe de la silhouette floue ----------
  addEventListener("scroll", () => document.documentElement.style.setProperty("--sy", scrollY), { passive: true });
  document.documentElement.style.setProperty("--sy", 0);

  // ---------- chargement ----------
  function header() {
    const g = data.garmin;
    const t = g ? new Date(g.derniere_synchro) : new Date(data.genere_le);
    $("#syncTxt").textContent = `${t.toLocaleDateString("fr-FR", { day: "numeric", month: "short" })} ${t.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}`;
    $("#syncBtn").classList.toggle("err", !!data.erreur);
    $("#demoTag").textContent = data.demo ? "démo" : "";
    const bc = document.querySelector(".barcode");
    if (bc) bc.innerHTML = data.semaines.flatMap((w) => w.seances).slice(-18)
      .map((x) => `<i style="width:${Math.max(1, Math.round((x.analyse ? x.analyse.realise.distance_km : x.distance_estimee_km) / 4))}px;opacity:${x.analyse ? 1 : .35}"></i>`).join("");
    if (data.erreur) $("#level").insertAdjacentHTML("beforebegin", `<div class="banner">${esc(data.erreur)}</div>`);
  }
  async function load(fresh) {
    const r = await fetch(`data.json${fresh ? "?t=" + Date.now() : ""}`, { cache: "no-store" });
    data = await r.json();
    const idx = data.semaines.findIndex((w) => w.debut <= data.aujourdhui && data.aujourdhui <= w.fin);
    wi = idx < 0 ? data.semaines.length - 1 : idx;
    $("#syncBtn").classList.remove("busy");
    document.querySelectorAll(".banner").forEach((b) => b.remove());
    header(); level(); week(); pixband();
    loadHeat();
  }
  load().catch((e) => { console.error(e); $("#level").innerHTML = `<div class="banner">Impossible de charger data.json.</div>`; });
})();
