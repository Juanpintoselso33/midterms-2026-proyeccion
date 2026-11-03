/* Midterms 2026 — Previa: pestañas de pronósticos, encuestas y participación, con mapas. */
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
  rows.push({source: 'Este tablero (antes del conteo, 19:59)', ours: true, date: P.ours.updated,
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
    'La fila de este tablero es su punto de partida, armado con las encuestas; desde el primer conteo pasa a mandar el voto real.';
}

/* ---------- pronósticos por estado ---------- */
var RATINGS = [['solid-rep', 'Segura R', -1], ['likely-rep', 'Probable R', -0.66], ['lean-rep', 'Inclinada R', -0.4], ['tilt-rep', 'Leve R', -0.2], ['tossup', 'Pareja', 0],
  ['tilt-dem', 'Leve D', 0.2], ['lean-dem', 'Inclinada D', 0.4], ['likely-dem', 'Probable D', 0.66], ['solid-dem', 'Segura D', 1]];
function ratingOf(k) { return RATINGS.filter(function (r) { return r[0] === k; })[0]; }
function rlabel(k) { var g = ratingOf(k); return g ? g[1] : (k || '—'); }
function xname(r) { return r.x + (r.ind ? ' (Ind.)' : ''); }
function fcRace(a) { return P.ours.races[a + '-' + FOFF]; }
var FSRC = [['Decision Desk HQ', 'DDHQ'], ['Polymarket', 'Polymarket'], ['Kalshi', 'Kalshi'], ['Cook Political Report', 'Cook'], ["Sabato's Crystal Ball", 'Sabato'], ['Inside Elections', 'Inside Elections']];
function fshort(s) { var m = FSRC.filter(function (x) { return x[0] === s; })[0]; return m ? m[1] : s; }
function fcExtra(a) {
  var names = FSRC.map(function (x) { return x[0]; });
  return (P.polls.race_forecasts || []).filter(function (f) { return f.state === a && f.office === FOFF && names.indexOf(f.source) >= 0; })
    .sort(function (x, y) { return names.indexOf(x.source) - names.indexOf(y.source); });
}
function fcStyle(f) {
  var r = fcRace(f.properties.a), g = r && ratingOf(r.rating);
  if (!r) return {fillColor: naColor(), fillOpacity: 0.45, color: css('--card'), weight: 1};
  return {fillColor: g ? divColor(g[2]) : divColor(2 * (r.p_D - 0.5)), fillOpacity: 1, color: css('--card'), weight: 1};
}
function probRow(lbl, pd, pr) {
  if (pr == null && pd != null) pr = 1 - pd;
  return '<div class="row"><span>' + esc(lbl) + '</span><b><span class="dd">D/I ' + pc(pd) + '</span> · <span class="rr">R ' + pc(pr) + '</span></b></div>';
}
function fcTip(a) {
  var r = fcRace(a), n = '<b>' + esc(STATE_NAMES[a] || a) + '</b>';
  if (!r) return n + '<div class="m">sin elección</div>';
  return n + '<div class="row"><span class="dd">' + esc(xname(r)) + '</span><span class="rr">' + esc(r.y) + '</span></div>' +
    '<div class="row"><span>Calificación (NYT)</span><b>' + (r.rating ? rlabel(r.rating) : 'sin calificación') + '</b></div>' +
    fcExtra(a).map(function (f) { return f.p_D != null ? probRow(fshort(f.source), f.p_D, f.p_R) : '<div class="row"><span>' + esc(fshort(f.source)) + '</span><b>' + esc(rlabel(f.rating)) + '</b></div>'; }).join('') +
    probRow('Este tablero', r.p_D);
}
function renderFcRaces() {
  var rs = Object.keys(P.ours.races).map(function (k) { var r = P.ours.races[k]; r.k = k; return r; }).filter(function (r) { return r.k.slice(3) === FOFF; });
  rs.sort(function (a, b) { return Math.abs(a.p_D - 0.5) - Math.abs(b.p_D - 0.5); });
  var srcs = FSRC.map(function (x) { return x[0]; }).filter(function (s) { return (P.polls.race_forecasts || []).some(function (f) { return f.source === s && f.office === FOFF; }); });
  function cellP(pd, pr) { if (pr == null && pd != null) pr = 1 - pd; return pd == null ? '<span class="m">—</span>' : '<div class="sv"><span class="dd">D/I ' + pc(pd) + '</span><span class="rr">R ' + pc(pr) + '</span></div>' + split(pd, pr); }
  $('#frT').innerHTML = '<thead><tr><th>Estado</th><th>Candidatos</th><th>Calificación (NYT)</th>' + srcs.map(function (s) { return '<th>' + esc(fshort(s)) + '</th>'; }).join('') + '<th>Este tablero</th></tr></thead><tbody>' +
    rs.map(function (r) {
      var a = r.k.slice(0, 2), g = ratingOf(r.rating), ex = fcExtra(a);
      return '<tr><td data-l="Estado" class="full"><b>' + esc(STATE_NAMES[a] || a) + '</b></td>' +
        '<td data-l="Candidatos"><span class="dd">' + esc(xname(r)) + '</span> · <span class="rr">' + esc(r.y) + '</span></td>' +
        '<td data-l="Calificación (NYT)">' + (g ? '<span class="' + (g[2] > 0 ? 'dd' : g[2] < 0 ? 'rr' : '') + '">' + g[1] + '</span>' : '<span class="m">—</span>') + '</td>' +
        srcs.map(function (s) {
          var f = ex.filter(function (x) { return x.source === s; })[0];
          return '<td data-l="' + esc(fshort(s)) + '">' + (!f ? '<span class="m">—</span>' : f.p_D != null ? cellP(f.p_D, f.p_R) : esc(rlabel(f.rating))) + '</td>';
        }).join('') +
        '<td data-l="Este tablero">' + cellP(r.p_D) + '</td></tr>';
    }).join('') + '</tbody>';
  $('#frNote').textContent = 'Calificación: la que publica el NYT junto con los resultados. DDHQ es el modelo de Decision Desk HQ; Polymarket y Kalshi son precios de mercados de apuestas (no encuestas), leídos hoy; Cook, Sabato e Inside Elections publican calificaciones, no probabilidades (tomadas de las tablas de Wikipedia). Donde el rival del republicano es un independiente, D/I es el independiente. “Este tablero” es la probabilidad del modelo propio antes del conteo, que parte de las encuestas. Orden: carreras más parejas primero.';
  if (MAPS.fmap) MAPS.fmap.layer.setStyle(fcStyle);
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
function lead(r) { return r.other != null && (r.D == null || r.other > r.D) ? r.other : r.D; }
function raceRows(off) {
  var all = (P.polls.races || []).filter(function (r) { return r.office === off; }), g = {};
  all.forEach(function (r) {
    var k = r.state, cur = g[k];
    if (!cur) { g[k] = r; r.extra = []; return; }
    if (cur.n_polls === 1 && r.n_polls !== 1) { r.extra = cur.extra.concat([cur]); g[k] = r; } else cur.extra.push(r);
  });
  return g;
}
function renderRaces() {
  var g = raceRows(OFF), rs = Object.keys(g).map(function (k) { return g[k]; });
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
  restyle();
  $('#rcNote').textContent = 'Ordenadas de la más pareja a la menos. Las encuestas incluyen indecisos, por eso no suman 100; “Este tablero” es el reparto entre los dos principales antes del conteo.';
}

/* ---------- mapas ---------- */
var PAL = {
  light: {neu:[196,176,222], d:[[150,178,236],[37,86,196]], r:[[236,160,150],[196,47,38]], seq:[[232,236,242],[40,52,78]], na:[234,231,225]},
  dark:  {neu:[120,98,158],  d:[[82,116,200],[130,170,255]],  r:[[170,80,72],[255,123,109]],  seq:[[40,48,64],[170,190,230]], na:[30,34,43]}
};
function isDark() { var t = document.documentElement.getAttribute('data-theme'); return t ? t === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches; }
function mix(a, b, t) { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]; }
function rgb(c) { return 'rgb(' + Math.round(c[0]) + ',' + Math.round(c[1]) + ',' + Math.round(c[2]) + ')'; }
function pal() { return PAL[isDark() ? 'dark' : 'light']; }
/* t en [-1,1]: positivo azul (D/Ind.), negativo rojo */
function divColor(t) {
  var Q = pal(); t = Math.max(-1, Math.min(1, t));
  var c = t >= 0 ? Q.d : Q.r, a = Math.abs(t);
  return rgb(a < 0.5 ? mix(Q.neu, c[0], a / 0.5) : mix(c[0], c[1], (a - 0.5) / 0.5));
}
function seqColor(t) { var Q = pal(); return rgb(mix(Q.seq[0], Q.seq[1], Math.max(0, Math.min(1, t)))); }
function naColor() { return rgb(pal().na); }
function css(v) { return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); }
function grad(f) { var st = []; for (var i = 0; i <= 12; i++) st.push(f(i / 12)); return 'linear-gradient(90deg,' + st.join(',') + ')'; }

var GEO = null, MAPS = {}, EMET = 'reg', PSPAN = 15, FOFF = 'S';
var EMETS = {
  share: {hint: 'Color: qué parte de los votos que AP espera hoy ya se emitió por anticipado.', lo: '0 %', hi: '100 %',
    val: function (s) { return s.pct_exp == null ? null : s.pct_exp; }, color: function (v) { return seqColor(v); }},
  grow: {hint: 'Color: cuántos votos espera AP hoy comparado con todos los votos de 2022.', lo: '−10 %', hi: '+40 %',
    val: function (s) { return s.exp && s.turn22 ? s.exp / s.turn22 - 1 : null; }, color: function (v) { return seqColor((v + 0.1) / 0.5); }},
  reg: {hint: 'Color: quién va adelante entre quienes ya votaron, según su partido de registro (no es el voto: muchos independientes votan a uno u otro). Sólo en los estados que publican el partido.', lo: 'R +30', hi: 'D +30',
    val: function (s) { return s.party && s.voted ? (s.dem - s.rep) / s.voted : null; }, color: function (v) { return divColor(v / 0.3); }, div: true}
};
function stateOf(a) { return P.early.states.filter(function (s) { return s.st === a; })[0]; }
function pollStyle(f) {
  var r = raceRows(OFF)[f.properties.a];
  if (!r) return {fillColor: naColor(), fillOpacity: 0.45, color: css('--card'), weight: 1};
  return {fillColor: divColor(((lead(r) || 0) - (r.R || 0)) / PSPAN), fillOpacity: 1, color: css('--card'), weight: 1};
}
function earlyStyle(f) {
  var s = stateOf(f.properties.a), M = EMETS[EMET], v = s ? M.val(s) : null;
  return {fillColor: v == null ? naColor() : M.color(v), fillOpacity: v == null ? 0.45 : 1, color: css('--card'), weight: 1};
}
function pollTip(a) {
  var r = raceRows(OFF)[a], n = '<b>' + esc(STATE_NAMES[a] || a) + '</b>';
  if (!r) return n + '<div class="m">sin encuestas cargadas</div>';
  var ind = r.other != null && (r.D == null || r.other > r.D);
  return n + '<div class="row"><span class="dd">' + esc(ind ? r.other_name + ' (Ind.)' : r.D_name) + '</span><b>' + f1(lead(r)) + ' %</b></div>' +
    '<div class="row"><span class="rr">' + esc(r.R_name) + '</span><b>' + f1(r.R) + ' %</b></div>' +
    '<div class="m">' + margin(lead(r), r.R) + ' · ' + esc(r.source) + '</div>';
}
function earlyTip(a) {
  var s = stateOf(a), n = '<b>' + esc(STATE_NAMES[a] || a) + '</b>';
  if (!s) return n + '<div class="m">sin dato</div>';
  var g = s.exp && s.turn22 ? s.exp / s.turn22 - 1 : null;
  return n + '<div class="row"><span>Esperado hoy (AP)</span><b>' + n0(s.exp) + '</b></div>' +
    '<div class="row"><span>Vs. 2022</span><b>' + (g == null ? '—' : (g >= 0 ? '+' : '') + f1(100 * g) + ' %') + '</b></div>' +
    '<div class="row"><span>Ya votaron</span><b>' + (s.voted == null ? 'sin dato' : n0(s.voted) + ' (' + pc(s.pct_exp) + ')') + '</b></div>' +
    (s.party ? '<div class="row"><span class="dd">Registrados D ' + f1(100 * s.dem / s.voted) + ' %</span><span class="rr">R ' + f1(100 * s.rep / s.voted) + ' %</span></div>' : '<div class="m">el estado no publica el partido</div>');
}
function buildMap(id, style, tip) {
  var el = document.getElementById(id);
  if (MAPS[id] || !GEO || el.offsetParent === null) return;
  var m = L.map(el, {crs: L.CRS.Simple, zoomSnap: 0.25, zoomDelta: 0.5, attributionControl: false, minZoom: -8, maxZoom: 6,
    scrollWheelZoom: false, dragging: !L.Browser.mobile});
  var lay = L.geoJSON(GEO, {style: style, onEachFeature: function (f, l) {
    l.bindTooltip(function () { return '<div class="tt">' + tip(f.properties.a) + '</div>'; }, {sticky: true});
    l.on('mouseover', function () { l.setStyle({weight: 2, color: css('--ink')}); l.bringToFront(); });
    l.on('mouseout', function () { l.setStyle(style(f)); });
  }}).addTo(m);
  m.fitBounds(lay.getBounds(), {padding: [8, 8]});
  MAPS[id] = {map: m, layer: lay, style: style};
}
function restyle() {
  if (!P) return;
  $('#plg').innerHTML = '<span class="rr"><b>R +' + PSPAN + '</b></span><div class="gr" style="background:' + grad(function (t) { return divColor(2 * t - 1); }) + '"></div><span class="dd"><b>D/Ind. +' + PSPAN + '</b></span><span class="na"><i style="background:' + naColor() + '"></i>sin encuestas / sin elección</span>';
  var M = EMETS[EMET];
  $('#emHint').textContent = M.hint;
  $('#elg').innerHTML = '<span' + (M.div ? ' class="rr"' : '') + '><b>' + M.lo + '</b></span><div class="gr" style="background:' + grad(M.div ? function (t) { return divColor(2 * t - 1); } : seqColor) + '"></div><span' + (M.div ? ' class="dd"' : '') + '><b>' + M.hi + '</b></span><span class="na"><i style="background:' + naColor() + '"></i>sin dato</span>';
  if (!GEO) {
    fetch('./geo/states.json').then(function (r) { return r.json(); }).then(function (g) { GEO = g; restyle(); });
    return;
  }
  $('#flg').innerHTML = RATINGS.map(function (r) { return '<span class="na"><i style="background:' + divColor(r[2]) + '"></i>' + r[1] + '</span>'; }).join('') + '<span class="na"><i style="background:' + naColor() + '"></i>sin elección</span>';
  buildMap('fmap', fcStyle, fcTip);
  buildMap('pmap', pollStyle, pollTip);
  buildMap('emap', earlyStyle, earlyTip);
  Object.keys(MAPS).forEach(function (k) { MAPS[k].map.invalidateSize(); MAPS[k].layer.setStyle(MAPS[k].style); });
}

/* ---------- pestañas ---------- */
var TABS = ['pronosticos', 'encuestas', 'participacion'];
function showTab() {
  var t = (location.hash || '').slice(1);
  if (TABS.indexOf(t) < 0) t = TABS[0];
  TABS.forEach(function (x) { document.getElementById('tab-' + x).hidden = x !== t; });
  document.querySelectorAll('.navl a[data-tab]').forEach(function (a) { a.classList.toggle('on', a.getAttribute('data-tab') === t); a.setAttribute('aria-current', a.getAttribute('data-tab') === t ? 'page' : 'false'); });
  window.scrollTo(0, 0);
  restyle();
}
window.addEventListener('hashchange', showTab);

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
  $('#evT').innerHTML = '<thead><tr><th>Estado</th><th class="ra">Esperado hoy (AP)</th><th class="ra">Vs. 2022</th><th class="ra">Ya votaron</th><th>Parte de lo esperado</th><th class="ra">Correo · persona</th><th>Adelante (registro)</th><th>Registro: D · R · sin partido</th><th>Dato del</th></tr></thead><tbody>' +
    ss.map(function (s) {
      var reg = s.party ? '<div class="sv"><span class="dd">D ' + f1(100 * s.dem / s.voted) + '</span><span class="m">' + f1(100 * s.none / s.voted) + '</span><span class="rr">R ' + f1(100 * s.rep / s.voted) + '</span></div>' + split(s.dem, s.rep, s.none) : '<span class="m">el estado no lo publica</span>';
      var g = s.exp && s.turn22 ? s.exp / s.turn22 - 1 : null;
      return '<tr><td data-l="Estado" class="full"><b>' + esc(sname(s)) + '</b></td>' +
        '<td data-l="Esperado hoy (AP)" class="ra">' + n0(s.exp) + '</td>' +
        '<td data-l="Vs. 2022" class="ra">' + (g == null ? '<span class="m">—</span>' : (g >= 0 ? '+' : '') + f1(100 * g) + ' %') + '</td>' +
        '<td data-l="Ya votaron" class="ra">' + (s.voted == null ? '<span class="m">sin dato</span>' : n0(s.voted)) + '</td>' +
        '<td data-l="Parte de lo esperado">' + (s.pct_exp == null ? '<span class="m">—</span>' : '<div class="sv"><span>' + pc(s.pct_exp) + '</span></div><div class="pbar2"><i style="width:' + Math.min(100, 100 * s.pct_exp) + '%"></i></div>') + '</td>' +
        '<td data-l="Correo · persona" class="ra m">' + (s.voted == null ? '—' : n0(s.mail) + ' · ' + n0(s.inperson)) + '</td>' +
        '<td data-l="Adelante (registro)">' + (s.party && s.voted ? margin(100 * s.dem / s.voted, 100 * s.rep / s.voted) : '<span class="m">—</span>') + '</td>' +
        '<td data-l="Registro" class="full">' + (s.voted == null ? '<span class="m">—</span>' : reg) + '</td>' +
        '<td data-l="Dato del" class="m">' + esc(fecha(s.last)) + '</td></tr>';
    }).join('') + '</tbody>';
  restyle();
  $('#evNote').innerHTML = 'Fuente: ' + link('UF Election Lab', e.url) + ' (Michael McDonald), con datos oficiales de cada estado. ' +
    (e.missing.length ? 'No reportan: ' + e.missing.map(function (s) { return STATE_NAMES[s] || s; }).join(' y ') + '. ' : '') +
    '“Esperado hoy” es la estimación de AP de todos los votos que se van a contar (publicada por el NYT; AP la ajusta durante la noche). “Vs. 2022” la compara con todos los votos de 2022. “Parte de lo esperado” es lo ya votado por anticipado sobre ese total.';
}

function renderAll() {
  renderForecasts(); renderFcRaces(); renderGeneric(); renderRaces(); renderEarly();
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
    showTab();
  });
}

document.querySelectorAll('#raceOff button').forEach(function (b) {
  b.addEventListener('click', function () {
    OFF = b.getAttribute('data-v');
    document.querySelectorAll('#raceOff button').forEach(function (x) { x.classList.toggle('on', x === b); });
    renderRaces();
  });
});
document.querySelectorAll('#fcOff button').forEach(function (b) {
  b.addEventListener('click', function () {
    FOFF = b.getAttribute('data-v');
    document.querySelectorAll('#fcOff button').forEach(function (x) { x.classList.toggle('on', x === b); });
    renderFcRaces();
  });
});
$('#evQ').addEventListener('input', function () { if (P) renderEarly(); });
document.querySelectorAll('#emMet button').forEach(function (b) {
  b.addEventListener('click', function () {
    EMET = b.getAttribute('data-v');
    document.querySelectorAll('#emMet button').forEach(function (x) { x.classList.toggle('on', x === b); });
    restyle();
  });
});
$('#themeBtn').addEventListener('click', function () {
  var dark = document.documentElement.getAttribute('data-theme') === 'dark' ||
    (!document.documentElement.getAttribute('data-theme') && matchMedia('(prefers-color-scheme: dark)').matches);
  var t = dark ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', t);
  try { localStorage.setItem('theme', t); } catch (e) {}
  restyle();
});
load();
setInterval(load, 300000);
})();
