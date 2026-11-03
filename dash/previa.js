/* Midterms 2026 — pestaña Previa: pronósticos, encuestas y voto anticipado. */
(function () {
'use strict';

/* Igual que el tablero en vivo: los datos se leen de la rama `datos` y de la copia de Pages,
   y se usa la más nueva. */
var RAW = 'https://raw.githubusercontent.com/Juanpintoselso33/midterms-2026-proyeccion/datos/';
var BASES = [RAW, './'];
var STATE_NAMES = {AL:'Alabama',AK:'Alaska',AZ:'Arizona',AR:'Arkansas',CA:'California',CO:'Colorado',CT:'Connecticut',DE:'Delaware',DC:'Distrito de Columbia',FL:'Florida',GA:'Georgia',HI:'Hawái',ID:'Idaho',IL:'Illinois',IN:'Indiana',IA:'Iowa',KS:'Kansas',KY:'Kentucky',LA:'Luisiana',ME:'Maine',MD:'Maryland',MA:'Massachusetts',MI:'Míchigan',MN:'Minnesota',MS:'Misisipi',MO:'Misuri',MT:'Montana',NE:'Nebraska',NV:'Nevada',NH:'Nuevo Hampshire',NJ:'Nueva Jersey',NM:'Nuevo México',NY:'Nueva York',NC:'Carolina del Norte',ND:'Dakota del Norte',OH:'Ohio',OK:'Oklahoma',OR:'Oregón',PA:'Pensilvania',RI:'Rhode Island',SC:'Carolina del Sur',SD:'Dakota del Sur',TN:'Tennessee',TX:'Texas',UT:'Utah',VT:'Vermont',VA:'Virginia',WA:'Washington',WV:'Virginia Occidental',WI:'Wisconsin',WY:'Wyoming'};
var $ = function (s) { return document.querySelector(s); };
var P = null, OFF = 'S';

function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
function f1(x) { return x == null ? '—' : x.toLocaleString('es-AR', {minimumFractionDigits:1, maximumFractionDigits:1}); }
function pc(p) { return p == null ? '—' : Math.round(p * 100) + ' %'; }
function n0(x) { return x == null ? '—' : Math.round(x).toLocaleString('es-AR'); }
function mill(x) { return (x / 1e6).toLocaleString('es-AR', {minimumFractionDigits:1, maximumFractionDigits:1}) + ' M'; }
var MES = ['ene','feb','mar','abr','may','jun','jul','ago','sep','oct','nov','dic'];
function fecha(s) { var m = /^(\d+)\/(\d+)\/(\d+)$/.exec(s || ''); return m ? +m[2] + '-' + MES[+m[1] - 1] : (s || ''); }
function sname(s) { return STATE_NAMES[s.st] || s.name; }
function link(src, url) { return url ? '<a href="' + esc(url) + '" target="_blank" rel="noopener">' + esc(src) + '</a>' : esc(src); }
function split(d, r, n) {
  var t = (d || 0) + (r || 0) + (n || 0) || 1;
  return '<div class="split" role="img" aria-label="Demócratas ' + f1(100 * d / t) + ' %, Republicanos ' + f1(100 * r / t) + ' %">' +
    '<i class="sd" style="width:' + (100 * d / t) + '%"></i>' + (n ? '<i class="sn" style="width:' + (100 * n / t) + '%"></i>' : '') +
    '<i class="sr" style="width:' + (100 * r / t) + '%"></i></div>';
}
function margin(d, r) {
  if (d == null || r == null) return '—';
  var m = d - r;
  return Math.abs(m) < 0.05 ? 'Empate' : '<span class="' + (m > 0 ? 'dd' : 'rr') + '">' + (m > 0 ? 'D' : 'R') + ' +' + f1(Math.abs(m)) + '</span>';
}

/* ---------- pronósticos ---------- */
function renderForecasts() {
  var by = {}, order = [];
  (P.polls.forecasts || []).forEach(function (f) {
    if (!by[f.source]) { by[f.source] = {source: f.source, url: f.url, date: f.date}; order.push(f.source); }
    by[f.source][f.chamber] = f;
  });
  var rows = order.map(function (s) { return by[s]; });
  var o = P.ours.chambers;
  rows.push({source: 'Este tablero (antes del conteo)', ours: true, date: P.ours.updated,
    S: {p_D: o.S.p_D, p_R: o.S.p_R, seats_D: o.S.D_med, seats_R: o.S.R_med},
    H: {p_D: o.H.p_D, p_R: o.H.p_R, seats_D: o.H.D_med, seats_R: o.H.R_med}});
  function cell(c, lbl, total) {
    if (c && c.seats_D != null && c.seats_R == null) c.seats_R = total - c.seats_D;
    if (c && c.p_D == null) return '<td data-l="' + lbl + '"><span class="m">sin probabilidad publicada</span>' + (c.seats_D != null ? '<div class="m">Bancas: <span class="dd">D ' + n0(c.seats_D) + '</span> · <span class="rr">R ' + n0(c.seats_R) + '</span></div>' : '') + '</td>';
    if (!c) return '<td data-l="' + lbl + '" class="m">sin dato</td>';
    var seats = c.seats_D != null ? '<div class="m">Bancas: <span class="dd">D ' + n0(c.seats_D) + '</span> · <span class="rr">R ' + n0(c.seats_R) + '</span></div>' : '';
    return '<td data-l="' + lbl + '"><div class="sv"><span class="dd">D ' + pc(c.p_D) + '</span><span class="rr">R ' + pc(c.p_R) + '</span></div>' +
      split(c.p_D || 0, c.p_R || 0) + seats + '</td>';
  }
  $('#fcT').innerHTML = '<thead><tr><th>Fuente</th><th>Senado</th><th>Cámara</th><th>Fecha</th></tr></thead><tbody>' +
    rows.map(function (r) {
      return '<tr' + (r.ours ? ' class="ours"' : '') + '><td data-l="Fuente" class="full">' + link(r.source, r.url) + '</td>' +
        cell(r.S, 'Senado', 100) + cell(r.H, 'Cámara', 435) + '<td data-l="Fecha" class="m">' + esc(r.date || '') + '</td></tr>';
    }).join('') + '</tbody>';
  $('#fcNote').textContent = 'Silver Bulletin: la Cámara (95 %) sale del texto público de su pronóstico y el Senado (75 %) de una comparación de terceros; sus tablas son pagas. Los mercados de predicción (si figuran) son precios de apuestas, no encuestas. ' +
    'La fila de este tablero es su punto de partida, armado con las calificaciones de los analistas; desde el primer conteo pasa a mandar el voto real.';
}

/* ---------- encuesta nacional ---------- */
function renderGeneric() {
  var g = P.polls.generic_ballot || [];
  $('#gbT').innerHTML = g.length ? g.map(function (x) {
    return '<div class="gb"><div class="src">' + link(x.source, x.url) + '<span class="m">' + esc(x.date || '') + '</span></div>' +
      '<div class="bar"><div class="sv"><span class="dd">Demócratas ' + f1(x.D) + ' %</span><span class="rr">Republicanos ' + f1(x.R) + ' %</span></div>' +
      split(x.D, x.R, Math.max(0, 100 - x.D - x.R)) + '</div><div class="mg">' + margin(x.D, x.R) + '</div></div>';
  }).join('') : '<p class="m">Todavía no hay promedios cargados.</p>';
}

/* ---------- encuestas por carrera ---------- */
function renderRaces() {
  var all = (P.polls.races || []).filter(function (r) { return r.office === OFF; }), g = {};
  all.forEach(function (r) {
    var k = r.state, cur = g[k];
    if (!cur) { g[k] = r; r.extra = []; return; }
    if (cur.n_polls === 1 && r.n_polls !== 1) { r.extra = cur.extra.concat([cur]); g[k] = r; } else cur.extra.push(r);
  });
  var rs = Object.keys(g).map(function (k) { return g[k]; });
  function lead(r) { return r.other != null && (r.D == null || r.other > r.D) ? r.other : r.D; }
  rs.sort(function (a, b) { return Math.abs((lead(a) || 0) - (a.R || 0)) - Math.abs((lead(b) || 0) - (b.R || 0)); });
  $('#rcT').innerHTML = '<thead><tr><th>Estado</th><th>Demócrata / Ind.</th><th>Republicano</th><th></th><th class="ra">Margen</th><th>Este tablero</th><th>Fuente</th></tr></thead><tbody>' +
    (rs.length ? rs.map(function (r) {
      var ind = r.other != null && (r.D == null || r.other > r.D);
      var lv = ind ? r.other : r.D, ln = ind ? r.other_name + ' (Ind.)' : r.D_name;
      var o = P.ours.races[r.state + '-' + r.office];
      var ours = o ? '<span class="dd">' + f1(o.share_D) + '</span> – <span class="rr">' + f1(o.share_R) + '</span><div class="m">gana D/I: ' + pc(o.p_D) + '</div>' : '<span class="m">—</span>';
      return '<tr><td data-l="Estado" class="full"><b>' + esc(STATE_NAMES[r.state] || r.state) + '</b></td>' +
        '<td data-l="Demócrata / Ind."><span class="dd">' + f1(lv) + ' %</span><div class="m">' + esc(ln || '') + '</div></td>' +
        '<td data-l="Republicano"><span class="rr">' + f1(r.R) + ' %</span><div class="m">' + esc(r.R_name || '') + '</div></td>' +
        '<td data-l="Reparto" class="full">' + split(lv || 0, r.R || 0) + '</td>' +
        '<td data-l="Margen" class="ra ctr">' + margin(lv, r.R) + '</td>' +
        '<td data-l="Este tablero (2 partidos)">' + ours + '</td>' +
        '<td data-l="Fuente" class="m">' + link(r.source, r.url) + (r.date ? ' · ' + esc(r.date) : '') + (r.n_polls > 1 ? ' · ' + r.n_polls + ' encuestas' : '') +
        (r.D != null && r.other != null ? '<div>' + (ind ? esc(r.D_name) + ' (D): ' + f1(r.D) : esc(r.other_name) + ' (Ind.): ' + f1(r.other)) + ' %</div>' : '') +
        r.extra.map(function (x) { return '<div>' + esc(x.source) + ': <span class="dd">' + f1(x.D != null ? x.D : x.other) + '</span> – <span class="rr">' + f1(x.R) + '</span>' + (x.date ? ' · ' + esc(x.date) : '') + '</div>'; }).join('') + '</td></tr>';
    }).join('') : '<tr><td colspan="7" class="m">Todavía no hay encuestas cargadas para estas carreras.</td></tr>') + '</tbody>';
  $('#rcNote').textContent = 'Ordenadas de la más pareja a la menos. Las encuestas incluyen indecisos, por eso no suman 100; “Este tablero” es el reparto entre los dos principales antes del conteo.';
}

/* ---------- voto anticipado ---------- */
function renderEarly() {
  var e = P.early, p = e.party, two = p.dem + p.rep;
  var grow = e.expected / e.turn22 - 1;
  $('#evK').innerHTML =
    '<div class="kpi"><div class="k">Participación esperada (AP)</div><div class="v">' + mill(e.expected) + '</div><div class="s">' + (grow >= 0 ? '+' : '') + f1(100 * grow) + ' % contra los ' + mill(e.turn22) + ' de 2022</div></div>' +
    '<div class="kpi"><div class="k">Ya votaron por anticipado</div><div class="v">' + mill(e.voted) + '</div><div class="s">' + pc(e.voted / e.expected) + ' de lo que se espera hoy · ' + pc(e.voted / e.turn22) + ' del total de 2022</div></div>' +
    '<div class="kpi"><div class="k">Por correo · en persona</div><div class="v">' + mill(e.mail) + ' · ' + mill(e.inperson) + '</div><div class="s">' + pc(e.mail / e.voted) + ' por correo</div></div>' +
    '<div class="kpi"><div class="k">Registro de quienes votaron</div><div class="sv" style="margin-top:8px"><span class="dd">Demócratas ' + f1(100 * p.dem / p.voted) + ' %</span><span class="rr">Republicanos ' + f1(100 * p.rep / p.voted) + ' %</span></div>' +
      split(p.dem, p.rep, p.none) + '<div class="s">Sin partido u otro: ' + f1(100 * p.none / p.voted) + ' %. Sólo ' + p.states + ' estados publican el partido. Entre D y R: <span class="dd">' + f1(100 * p.dem / two) + '</span> – <span class="rr">' + f1(100 * p.rep / two) + '</span></div></div>';
  var q = ($('#evQ').value || '').trim().toLowerCase();
  var ss = e.states.filter(function (s) { return !q || sname(s).toLowerCase().indexOf(q) >= 0 || s.st.toLowerCase() === q; });
  ss.sort(function (a, b) { return (b.exp || 0) - (a.exp || 0); });
  $('#evT').innerHTML = '<thead><tr><th>Estado</th><th class="ra">Esperado hoy (AP)</th><th class="ra">Vs. 2022</th><th class="ra">Ya votaron</th><th>Parte de lo esperado</th><th class="ra">Correo · persona</th><th>Registro: D · R · sin partido</th><th>Dato del</th></tr></thead><tbody>' +
    ss.map(function (s) {
      var reg = s.party ? '<div class="sv"><span class="dd">D ' + f1(100 * s.dem / s.voted) + '</span><span class="m">' + f1(100 * s.none / s.voted) + '</span><span class="rr">R ' + f1(100 * s.rep / s.voted) + '</span></div>' + split(s.dem, s.rep, s.none) : '<span class="m">el estado no lo publica</span>';
      var g = s.exp && s.turn22 ? s.exp / s.turn22 - 1 : null;
      return '<tr><td data-l="Estado" class="full"><b>' + esc(sname(s)) + '</b></td>' +
        '<td data-l="Esperado hoy (AP)" class="ra">' + n0(s.exp) + '</td>' +
        '<td data-l="Vs. 2022" class="ra">' + (g == null ? '<span class="m">—</span>' : (g >= 0 ? '+' : '') + f1(100 * g) + ' %') + '</td>' +
        '<td data-l="Ya votaron" class="ra">' + (s.voted == null ? '<span class="m">sin dato</span>' : n0(s.voted)) + '</td>' +
        '<td data-l="Parte de lo esperado">' + (s.pct_exp == null ? '<span class="m">—</span>' : '<div class="sv"><span>' + pc(s.pct_exp) + '</span></div><div class="pbar2"><i style="width:' + Math.min(100, 100 * s.pct_exp) + '%"></i></div>') + '</td>' +
        '<td data-l="Correo · persona" class="ra m">' + (s.voted == null ? '—' : n0(s.mail) + ' · ' + n0(s.inperson)) + '</td>' +
        '<td data-l="Registro" class="full">' + (s.voted == null ? '<span class="m">—</span>' : reg) + '</td>' +
        '<td data-l="Dato del" class="m">' + esc(fecha(s.last)) + '</td></tr>';
    }).join('') + '</tbody>';
  $('#evNote').innerHTML = 'Fuente: ' + link('UF Election Lab', e.url) + ' (Michael McDonald), con datos oficiales de cada estado. ' +
    (e.missing.length ? 'No reportan: ' + e.missing.map(function (s) { return STATE_NAMES[s] || s; }).join(' y ') + '. ' : '') +
    '“Esperado hoy” es la estimación de AP de todos los votos que se van a contar (publicada por el NYT; AP la ajusta durante la noche). “Vs. 2022” la compara con todos los votos de 2022. “Parte de lo esperado” es lo ya votado por anticipado sobre ese total.';
}

function renderAll() {
  renderForecasts(); renderGeneric(); renderRaces(); renderEarly();
  $('#foot').innerHTML = 'Actualizado: ' + esc(P.updated) + '. Encuestas y pronósticos: cada fila enlaza a su fuente. ' +
    'Voto anticipado: UF Election Lab (CC BY-NC-ND 4.0). Proyección propia, no oficial. <a href="./">Volver al tablero en vivo</a>.';
}

function load() {
  Promise.all(BASES.map(function (b) {
    return fetch(b + 'previa.json?_=' + Date.now(), {cache: 'no-store'}).then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); }).catch(function () { return null; });
  })).then(function (got) {
    var ok = got.filter(Boolean).sort(function (a, b) { return String(b.updated) < String(a.updated) ? -1 : 1; });
    if (!ok.length) { $('#errbox').textContent = 'No pude cargar los datos de la previa.'; return; }
    P = ok[0]; P.polls = P.polls || {};
    renderAll();
  });
}

document.querySelectorAll('#raceOff button').forEach(function (b) {
  b.addEventListener('click', function () {
    OFF = b.getAttribute('data-v');
    document.querySelectorAll('#raceOff button').forEach(function (x) { x.classList.toggle('on', x === b); });
    renderRaces();
  });
});
$('#evQ').addEventListener('input', function () { if (P) renderEarly(); });
$('#themeBtn').addEventListener('click', function () {
  var dark = document.documentElement.getAttribute('data-theme') === 'dark' ||
    (!document.documentElement.getAttribute('data-theme') && matchMedia('(prefers-color-scheme: dark)').matches);
  var t = dark ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', t);
  try { localStorage.setItem('theme', t); } catch (e) {}
});
load();
setInterval(load, 300000);
})();
