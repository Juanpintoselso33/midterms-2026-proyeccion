/* Midterms 2026 — tablero en vivo. Sin build, sin CDNs: Leaflet + Chart.js locales. */
(function () {
'use strict';

/* ---------- configuración ---------- */
var Q = new URLSearchParams(location.search);
var SRC = (Q.get('src') || '').replace(/[^a-z0-9_-]/gi, '');
var BASE = SRC ? './' + SRC + '/' : './';
var REFRESH_MS = 30000;
var $ = function (s, el) { return (el || document).querySelector(s); };

var STATE_NAMES = {AL:'Alabama',AK:'Alaska',AZ:'Arizona',AR:'Arkansas',CA:'California',CO:'Colorado',CT:'Connecticut',DE:'Delaware',DC:'Distrito de Columbia',FL:'Florida',GA:'Georgia',HI:'Hawái',ID:'Idaho',IL:'Illinois',IN:'Indiana',IA:'Iowa',KS:'Kansas',KY:'Kentucky',LA:'Luisiana',ME:'Maine',MD:'Maryland',MA:'Massachusetts',MI:'Míchigan',MN:'Minnesota',MS:'Misisipi',MO:'Misuri',MT:'Montana',NE:'Nebraska',NV:'Nevada',NH:'Nuevo Hampshire',NJ:'Nueva Jersey',NM:'Nuevo México',NY:'Nueva York',NC:'Carolina del Norte',ND:'Dakota del Norte',OH:'Ohio',OK:'Oklahoma',OR:'Oregón',PA:'Pensilvania',RI:'Rhode Island',SC:'Carolina del Sur',SD:'Dakota del Sur',TN:'Tennessee',TX:'Texas',UT:'Utah',VT:'Vermont',VA:'Virginia',WA:'Washington',WV:'Virginia Occidental',WI:'Wisconsin',WY:'Wyoming'};
var OFFICE_NAME = {S:'Senado', G:'Gobernaciones', H:'Cámara'};
var RATING_TXT = {'solid-dem':'Seguro D','likely-dem':'Probable D','lean-dem':'Inclinado D','tilt-dem':'Leve D','tossup':'Parejo','tilt-rep':'Leve R','lean-rep':'Inclinado R','likely-rep':'Probable R','solid-rep':'Seguro R'};
var RATING_CLS = {'solid-dem':'sd','likely-dem':'ld','lean-dem':'td','tilt-dem':'td','tossup':'tu','tilt-rep':'tr','lean-rep':'tr','likely-rep':'lr','solid-rep':'sr'};
var RATING_ORD = {'solid-dem':-4,'likely-dem':-3,'lean-dem':-2,'tilt-dem':-1,'tossup':0,'tilt-rep':1,'lean-rep':2,'likely-rep':3,'solid-rep':4};

/* ---------- estado ---------- */
var DATA = null, UNITS = {}, HIST = [], RI = {}, HMAP = {}, ATLARGE = {};
var GEO = {states:null, districts:null, counties:null};
var lastOk = 0, lastUpdated = '', loading = false, firstLoad = true;
var UI = {off:'S', q:'', allH:false, sort:{S:{k:'comp',dir:1},G:{k:'comp',dir:1},H:{k:'comp',dir:1}},
          evoCh:'S', evoMet:'p', m1off:'S', m1met:'proj', m2met:'proj', dmode:'proj'};
var CH = {};          // gráficos Chart.js
var MAP = {};         // mapas Leaflet
var DET = {map:null, key:null};
var SEL = null;

/* ---------- formato ---------- */
var nf1 = new Intl.NumberFormat('es-AR', {minimumFractionDigits:1, maximumFractionDigits:1});
var nf0 = new Intl.NumberFormat('es-AR', {maximumFractionDigits:0});
function f1(x) { return x == null || isNaN(x) ? '—' : nf1.format(x); }
function f0(x) { return x == null || isNaN(x) ? '—' : nf0.format(x); }
function fpct(x) { return x == null || isNaN(x) ? '—' : nf1.format(x) + ' %'; }
function fprob(p) {
  if (p == null || isNaN(p)) return '—';
  var v = p * 100;
  if (v > 99.5) return '>99,5 %';
  if (v < 0.5) return '<0,5 %';
  return (v < 10 || v > 90 ? nf1.format(v) : nf0.format(v)) + ' %';
}
function frange(a) { return a ? f1(a[0]) + '–' + f1(a[1]) : '—'; }
function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
function css(v) { return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); }
function isDark() {
  var t = document.documentElement.getAttribute('data-theme');
  return t ? t === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
}

/* ---------- paleta divergente ---------- */
var PAL = {
  light: {neu:[196,176,222], d:[[150,178,236],[37,86,196]], r:[[236,160,150],[196,47,38]], seq:[[232,236,242],[40,52,78]], na:[234,231,225]},
  dark:  {neu:[120,98,158],  d:[[82,116,200],[130,170,255]],  r:[[170,80,72],[255,123,109]],  seq:[[40,48,64],[170,190,230]], na:[30,34,43]}
};
function mix(a, b, t) { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]; }
function rgb(c) { return 'rgb(' + Math.round(c[0]) + ',' + Math.round(c[1]) + ',' + Math.round(c[2]) + ')'; }
/* t en [-1,1]: positivo azul (D/Ind.), negativo rojo */
function divColor(t) {
  var P = PAL[isDark() ? 'dark' : 'light'];
  t = Math.max(-1, Math.min(1, t));
  var s = t >= 0 ? P.d : P.r, a = Math.abs(t);
  return rgb(a < 0.5 ? mix(P.neu, s[0], a / 0.5) : mix(s[0], s[1], (a - 0.5) / 0.5));
}
function seqColor(v) { var P = PAL[isDark() ? 'dark' : 'light']; return rgb(mix(P.seq[0], P.seq[1], Math.max(0, Math.min(1, v / 100)))); }
function naColor() { return rgb(PAL[isDark() ? 'dark' : 'light'].na); }
function gradient(kind) {
  var st = [], i, n = 12;
  for (i = 0; i <= n; i++) {
    var t = i / n;
    st.push(kind === 'seq' ? seqColor(t * 100) : divColor(2 * t - 1));
  }
  return 'linear-gradient(90deg,' + st.join(',') + ')';
}

/* ---------- helpers de carrera ---------- */
function cc(c) { return c === 'R' ? 'r' : 'd'; }
function sideLetter(r) { return r.x_party || 'D'; }
function sideName(r) { return sideLetter(r) === 'I' ? 'Ind.' : sideLetter(r); }
function yLetter(r) { return r.y_party || 'R'; }
function tag(l, cls) { return '<i class="tg ' + (cls || (l === 'R' ? 'r' : 'd')) + '" title="' + (l === 'R' ? 'Republicano' : l === 'I' ? 'Independiente' : 'Demócrata') + '">' + l + '</i>'; }
function tx(r) { return tag(sideLetter(r), cc(r.x_caucus || 'D')); }
function ty(r) { return tag(yLetter(r), cc(r.y_caucus || 'R')); }
function xn(r) { return r.x_name || sideName(r); }
function yn(r) { return r.y_name || 'R'; }
function xc(r) { return cc(r.x_caucus || 'D'); }
function yc(r) { return cc(r.y_caucus || 'R'); }
function candTxt(r, s) { var l = s === 'x' ? sideLetter(r) : yLetter(r), n = s === 'x' ? xn(r) : yn(r); return n + ' (' + (l === 'I' ? 'Ind.' : l) + ')'; }
function isSpecial(r) { var p = r.id.split('-'); return p[1] && p[1] !== 'G' && p[1] !== 'L'; }
function raceLabel(r) {
  if (r.office === 'H') return ATLARGE[r.state] ? r.state + ' (único)' : r.state + '-' + r.seat;
  return r.state + (r.office === 'S' && isSpecial(r) ? ' (especial)' : '');
}
function raceTitle(r) {
  var n = STATE_NAMES[r.state] || r.state;
  if (r.office === 'H') return ATLARGE[r.state] ? n + ' · distrito único' : n + ' · distrito ' + r.seat;
  return n + (r.office === 'S' && isSpecial(r) ? ' · Senado (especial)' : r.office === 'S' ? ' · Senado' : ' · Gobernación');
}
function hasProj(r) { return !r.same_party && r.proj_B != null; }
function samePartyTxt(r) { return r.y_party ? 'Mismo partido' : 'Sin rival'; }
function ratingChip(r) {
  if (!r.rating) return '<span class="chip na">Sin rating</span>';
  var t = RATING_TXT[r.rating] || r.rating;
  if (r.side === 'O' && /dem/.test(r.rating)) t = t.replace(/ D$/, ' Ind.');
  return '<span class="chip ' + (RATING_CLS[r.rating] || 'na') + '">' + esc(t) + '</span>';
}
function winnerTxt(r) {
  var w = (r.winner || '')[0];
  return w === 'X' ? candTxt(r, 'x') : w === 'Y' ? candTxt(r, 'y') : '';
}
function statusOf(r) {
  var w = winnerTxt(r), c = String(r.call || '').toLowerCase();
  if (w) return {k:3, t:'Ganó ' + w, cls:(r.winner[0] === 'X' ? xc(r) : yc(r))};
  if (/called/.test(c) && !/uncalled|not/.test(c)) return {k:3, t:'Proyectada', cls:''};
  if (/runoff/.test(c)) return {k:2, t:'Segunda vuelta', cls:''};
  if (!r.eevp || /too/.test(c)) return {k:0, t:'Sin datos', cls:''};
  return {k:1, t:'En conteo', cls:''};
}
function compKey(r) { return hasProj(r) && r.p_B_win != null ? Math.abs(r.p_B_win - 0.5) : 9; }
function isCompetitive(r) {
  if (r.same_party) return false;
  if (/tossup|lean|tilt/.test(r.rating || '')) return true;
  return r.p_B_win != null && r.p_B_win >= 0.1 && r.p_B_win <= 0.9;
}

/* ---------- carga ---------- */
function bust(u) { return u + (u.indexOf('?') < 0 ? '?' : '&') + '_=' + Date.now(); }
function getJSON(name, optional) {
  return fetch(bust(BASE + name), {cache:'no-store'}).then(function (r) {
    if (!r.ok) { if (optional) return null; throw new Error(name + ' → HTTP ' + r.status); }
    return r.json();
  });
}
function getGeo(name) { return fetch('./geo/' + name + '.json').then(function (r) { if (!r.ok) throw new Error('geo/' + name); return r.json(); }); }

function load() {
  if (loading) return Promise.resolve();
  loading = true;
  return Promise.all([getJSON('data.json'), getJSON('units.json', true), getJSON('history.json', true)]).then(function (res) {
    DATA = res[0]; UNITS = res[1] || {}; HIST = Array.isArray(res[2]) ? res[2] : [];
    lastOk = Date.now(); lastUpdated = DATA.updated || '';
    $('#errbox').textContent = '';
    $('#live').classList.remove('err');
    index();
    renderAll();
  }).catch(function (e) {
    $('#live').classList.add('err');
    if (!DATA) {
      $('#errbox').innerHTML = 'No pude cargar los datos (' + esc(e.message) + '). ' +
        (SRC ? '' : 'Todavía no hay <code>data.json</code> publicado: probá con <a href="?src=sample26">?src=sample26</a> o <a href="?src=sample">?src=sample</a>.');
    }
    tickLive();
  }).then(function () { loading = false; });
}

function index() {
  RI = {}; HMAP = {}; ATLARGE = {};
  var cnt = {};
  DATA.races.forEach(function (r) {
    RI[r.id] = r;
    if (r.office === 'H') { HMAP[r.state + '-' + r.seat] = r; cnt[r.state] = (cnt[r.state] || 0) + 1; }
  });
  Object.keys(cnt).forEach(function (s) { if (cnt[s] === 1) ATLARGE[s] = true; });
}

/* ---------- render general ---------- */
function renderAll() {
  var note = '';
  if (SRC === 'sample') note = 'Datos de ensayo: conteo parcial de 2024 usado para probar el tablero.';
  else if (SRC === 'sample26') note = 'Datos de prueba: estructura real de 2026, todavía sin votos.';
  else if (SRC) note = 'Fuente alternativa: ' + SRC;
  $('#srcnote').textContent = note;
  renderChambers();
  renderEvo();
  renderTabs();
  renderTable();
  renderMaps();
  if (SEL && RI[SEL]) renderDetail(false);
  tickLive();
}

function tickLive() {
  var el = $('#liveTxt');
  if (!lastOk) { el.textContent = 'Sin conexión'; return; }
  var left = Math.max(0, Math.round((lastOk + REFRESH_MS - Date.now()) / 1000));
  el.textContent = 'Actualizado: ' + lastUpdated + ' · próxima en ' + left + ' s';
}

/* ---------- cámaras ---------- */
function chamberStats(off) {
  var rs = DATA.races.filter(function (r) { return r.office === off; });
  var counted = 0, expected = 0, n = rs.length, started = 0, called = 0;
  rs.forEach(function (r) {
    counted += r.counted || 0; expected += r.expected || 0;
    if (r.eevp > 0) started++;
    if (statusOf(r).k === 3) called++;
  });
  return {n:n, pct: expected ? 100 * counted / expected : 0, started:started, called:called};
}
function renderChambers() {
  var host = $('#chambers');
  ['S', 'H'].forEach(function (off) {
    var c = DATA.chambers && DATA.chambers[off];
    var id = 'ch-' + off, el = document.getElementById(id);
    if (!c) { if (el) el.remove(); return; }
    if (!el) {
      el = document.createElement('article'); el.className = 'card ch'; el.id = id;
      el.innerHTML = '<div class="chtxt"></div><div class="hist"><canvas role="img"></canvas></div><div class="chfoot chnote"></div>';
      host.appendChild(el);
      if (off === 'H' && $('#ch-S')) host.appendChild(el);
    }
    var name = off === 'S' ? 'Senado' : 'Cámara de Representantes';
    var rest = Math.max(0, 1 - c.p_D - c.p_R);
        $('.chtxt', el).innerHTML =
      '<h2>' + name + '</h2><p class="need">' + c.total + ' bancas · mayoría: D/Ind. ' + c.D_needs + ' · R ' + c.R_needs + '</p>' +
      '<div class="duo">' +
        '<div class="side d"><div class="pname">Demócratas / Ind.</div><div class="big num">' + bigP(c.p_D) + '</div><div class="sub2">probabilidad de controlar</div>' +
          '<div class="med"><b class="num">' + c.D_med + '</b> bancas' + '<span>rango 90 %: ' + c.D_ci90[0] + '–' + c.D_ci90[1] + '</span></div></div>' +
        '<div class="side rr r"><div class="pname">Republicanos</div><div class="big num">' + bigP(c.p_R) + '</div><div class="sub2">probabilidad de controlar</div>' +
          '<div class="med"><b class="num">' + c.R_med + '</b> bancas' + '<span>rango 90 %: ' + c.R_ci90[0] + '–' + c.R_ci90[1] + '</span></div></div>' +
      '</div>' +
      '<div class="pbar" role="img" aria-label="Demócratas ' + fprob(c.p_D) + ', Republicanos ' + fprob(c.p_R) + '"><i class="bd" style="width:' + (c.p_D * 100) + '%"></i>' +
        (rest > 0.004 ? '<i style="width:' + (rest * 100) + '%;background:var(--grey)"></i>' : '') +
        '<i class="br" style="width:' + (c.p_R * 100) + '%"></i></div>' +
      (rest > 0.004 ? '<div class="sub2" style="margin-top:6px">Sin mayoría clara en ' + fprob(rest) + ' de las simulaciones' + (c.I_med ? ' (independientes en la mediana: ' + c.I_med + ')' : '') + '.</div>' : (c.I_med ? '<div class="sub2" style="margin-top:6px">Independientes en la mediana: ' + c.I_med + ' (contados con los demócratas).</div>' : ''));
    var st = chamberStats(off);
    $('.chfoot', el).innerHTML = '<span>Distribución de bancas demócratas en las simulaciones</span><span>' + st.started + ' de ' + st.n + ' carreras con voto · ' + f1(st.pct) + ' % del voto esperado<span class="prog"><i style="width:' + Math.min(100, st.pct) + '%"></i></span></span>';
    drawHist(off, c, $('canvas', el));
  });
}
function bigP(p) {
  var v = p * 100;
  if (v > 99.5) return '>99,5<small>%</small>';
  if (v < 0.5) return '<0,5<small>%</small>';
  return (v < 10 || v > 90 ? nf1.format(v) : nf0.format(v)) + '<small>%</small>';
}

/* ---------- gráficos ---------- */
function chartDefaults() {
  Chart.defaults.color = css('--mut');
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.font.size = 12;
}
var threshPlugin = {
  id: 'thresh',
  afterDatasetsDraw: function (chart, a, o) {
    if (!o || o.need == null) return;
    var x = chart.scales.x, area = chart.chartArea, idx = chart.data.labels.indexOf(o.need);
    if (idx < 0) return;
    var half = chart.data.labels.length > 1 ? (x.getPixelForValue(1) - x.getPixelForValue(0)) / 2 : 0;
    var px = x.getPixelForValue(idx) - half, ctx = chart.ctx;
    ctx.save();
    ctx.strokeStyle = css('--ink'); ctx.lineWidth = 1.5; ctx.setLineDash([5, 4]);
    ctx.beginPath(); ctx.moveTo(px, area.top); ctx.lineTo(px, area.bottom); ctx.stroke(); ctx.setLineDash([]);
    ctx.font = '600 11px ' + Chart.defaults.font.family; ctx.textBaseline = 'top';
    ctx.fillStyle = css('--r'); ctx.textAlign = 'right'; ctx.fillText('Mayoría R ◂', px - 6, area.top + 2);
    ctx.fillStyle = css('--d'); ctx.textAlign = 'left'; ctx.fillText('▸ Mayoría D/Ind. (≥ ' + o.need + ')', px + 6, area.top + 2);
    ctx.restore();
  }
};
function drawHist(off, c, canvas) {
  var keys = Object.keys(c.dist).map(Number);
  var lo = Math.min.apply(null, keys) - 1, hi = Math.max.apply(null, keys) + 1;
  lo = Math.min(lo, c.D_needs - 3); hi = Math.max(hi, c.D_needs + 3);
  var labels = [], data = [], cols = [], i;
  for (i = lo; i <= hi; i++) { labels.push(i); data.push(100 * (c.dist[i] || 0)); cols.push(i >= c.D_needs ? css('--d') : css('--r')); }
  var key = 'hist-' + off;
  if (CH[key]) {
    var ch = CH[key];
    ch.data.labels = labels; ch.data.datasets[0].data = data; ch.data.datasets[0].backgroundColor = cols;
    ch.options.plugins.thresh.need = c.D_needs; ch._c = c;
    ch.update('none'); return;
  }
  var chart = new Chart(canvas, {
    type: 'bar',
    data: {labels: labels, datasets: [{data: data, backgroundColor: cols, borderWidth: 0, barPercentage: 1, categoryPercentage: 0.94}]},
    plugins: [threshPlugin],
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      plugins: {
        legend: {display: false},
        thresh: {need: c.D_needs},
        tooltip: {
          callbacks: {
            title: function (it) { var d = +it[0].label, cc = chart._c; return 'D/Ind. ' + (d + (cc.I_med || 0) * 0) + ' · R ' + (cc.total - d - (cc.I_med || 0)) + (cc.I_med ? ' · Ind. ' + cc.I_med : ''); },
            label: function (it) { return nf1.format(it.parsed.y) + ' % de las simulaciones'; }
          }
        }
      },
      scales: {
        x: {grid: {display: false}, ticks: {maxTicksLimit: 10, autoSkip: true, maxRotation: 0}, title: {display: true, text: 'Bancas demócratas (las republicanas son el resto)', color: css('--mut')}},
        y: {beginAtZero: true, grid: {color: css('--line2')}, ticks: {callback: function (v) { return v + ' %'; }, maxTicksLimit: 4}}
      }
    }
  });
  chart._c = c;
  CH[key] = chart;
}

function evoConfig() {
  var d = css('--d'), r = css('--r');
  var ch = UI.evoCh, p = UI.evoMet === 'p';
  var pts = HIST.filter(function (h) { return h[ch]; });
  var labels = pts.map(function (h) { return h.t; });
  function ser(f) { return pts.map(f); }
  var ds;
  if (p) {
    ds = [
      {label: 'D', data: ser(function (h) { return 100 * h[ch].p_D; }), borderColor: d, backgroundColor: d, borderWidth: 2.5, pointRadius: 3, tension: 0.15},
      {label: 'R', data: ser(function (h) { return 100 * h[ch].p_R; }), borderColor: r, backgroundColor: r, borderWidth: 2.5, pointRadius: 3, tension: 0.15}
    ];
  } else {
    var band = function (lo, hi, col) {
      return [
        {label: 'lo', data: ser(lo), borderWidth: 0, pointRadius: 0, fill: false},
        {label: 'hi', data: ser(hi), borderWidth: 0, pointRadius: 0, fill: '-1', backgroundColor: col + '33'}
      ];
    };
    ds = band(function (h) { return h[ch].D_ci90[0]; }, function (h) { return h[ch].D_ci90[1]; }, d)
      .concat([{label: 'D', data: ser(function (h) { return h[ch].D_med; }), borderColor: d, backgroundColor: d, borderWidth: 2.5, pointRadius: 3}])
      .concat(band(function (h) { return h[ch].R_ci90[0]; }, function (h) { return h[ch].R_ci90[1]; }, r))
      .concat([{label: 'R', data: ser(function (h) { return h[ch].R_med; }), borderColor: r, backgroundColor: r, borderWidth: 2.5, pointRadius: 3}]);
  }
  return {
    type: 'line',
    data: {labels: labels, datasets: ds},
    options: {
      responsive: true, maintainAspectRatio: false, animation: false,
      interaction: {mode: 'index', intersect: false},
      plugins: {
        legend: {display: false},
        tooltip: {
          filter: function (it) { return p || it.dataset.label === 'D' || it.dataset.label === 'R'; },
          callbacks: {
            label: function (it) {
              var h = pts[it.dataIndex][ch], isD = it.dataset.label === 'D', who = isD ? 'D/Ind.' : 'R';
              if (p) return who + ': ' + fprob(isD ? h.p_D : h.p_R);
              return who + ': ' + (isD ? h.D_med : h.R_med) + ' bancas (rango 90 %: ' + (isD ? h.D_ci90 : h.R_ci90).join('–') + ')';
            }
          }
        }
      },
      scales: {
        x: {grid: {display: false}, ticks: {maxTicksLimit: 8, maxRotation: 0}},
        y: p ? {min: 0, max: 100, ticks: {callback: function (v) { return v + ' %'; }, stepSize: 25},
                grid: {color: function (c) { return c.tick.value === 50 ? css('--mut') : css('--line2'); }}}
             : {grid: {color: css('--line2')}, title: {display: true, text: 'Bancas', color: css('--mut')}}
      }
    }
  };
}
function renderEvo() {
  var cfg = evoConfig(), ch = CH.evo;
  var c = DATA.chambers && DATA.chambers[UI.evoCh];
  $('#evoNote').textContent = (HIST.length ? HIST.length + (HIST.length === 1 ? ' corrida del modelo' : ' corridas del modelo') : 'Todavía no hay historial: el gráfico se va a llenar con las próximas corridas') +
    (c ? ' · mayoría: D/Ind. ' + c.D_needs + ' bancas, R ' + c.R_needs + '.' : '.');
  if (ch && ch._sig === UI.evoCh + UI.evoMet) {
    ch.data = cfg.data; ch.options.scales = cfg.options.scales; ch.update('none'); return;
  }
  if (ch) ch.destroy();
  CH.evo = new Chart($('#evoCanvas'), cfg);
  CH.evo._sig = UI.evoCh + UI.evoMet;
}

/* ---------- tabla de carreras ---------- */
function renderTabs() {
  var host = $('#tabOff'), html = '';
  ['S', 'G', 'H'].forEach(function (o) {
    var n = DATA.races.filter(function (r) { return r.office === o; }).length;
    if (!n) return;
    html += '<button type="button" data-v="' + o + '" aria-pressed="' + (UI.off === o) + '" class="' + (UI.off === o ? 'on' : '') + '">' + OFFICE_NAME[o] + '<span class="cnt">' + n + '</span></button>';
  });
  host.innerHTML = html;
  $('#allWrap').style.display = UI.off === 'H' ? '' : 'none';
}
var COLS = [
  {k:'name', l:'Carrera', cls:'c-n'},
  {k:'rating', l:'Rating', cls:'c-r'},
  {k:'cnt', l:'Contado', cls:'c-c'},
  {k:'part', l:'Parcial (D/I · R)', cls:'c-p'},
  {k:'proj', l:'Proyección e IC 90 %', cls:'c-proj'},
  {k:'prob', l:'Prob. de ganar', cls:'c-pr'},
  {k:'stat', l:'Estado', cls:'c-s'}
];
function sortVal(r, k) {
  switch (k) {
    case 'name': return r.state + ('000' + (parseInt(r.seat, 10) || 0)).slice(-3) + (isSpecial(r) ? 'z' : '');
    case 'rating': return r.rating ? RATING_ORD[r.rating] : null;
    case 'cnt': return r.eevp;
    case 'part': return r.partial_B;
    case 'proj': return hasProj(r) ? r.proj_B : null;
    case 'prob': return hasProj(r) ? r.p_B_win : null;
    case 'stat': return statusOf(r).k;
    case 'comp': return compKey(r);
  }
}
function filteredRaces() {
  var rs = DATA.races.filter(function (r) { return r.office === UI.off; });
  var total = rs.length;
  if (UI.off === 'H' && !UI.allH) rs = rs.filter(isCompetitive);
  var q = UI.q.trim().toLowerCase();
  if (q) rs = rs.filter(function (r) {
    return (r.id + ' ' + raceLabel(r) + ' ' + r.state + '-' + r.seat + ' ' + (STATE_NAMES[r.state] || '')).toLowerCase().indexOf(q) >= 0;
  });
  var s = UI.sort[UI.off];
  rs = rs.slice().sort(function (a, b) {
    var x = sortVal(a, s.k), y = sortVal(b, s.k);
    if (x == null && y == null) return 0;
    if (x == null) return 1; if (y == null) return -1;
    var c = x < y ? -1 : x > y ? 1 : 0;
    if (!c) c = compKey(a) - compKey(b);
    return c * s.dir;
  });
  return {rows: rs, total: total};
}
function rowHTML(r) {
  var L = sideLetter(r), SD = sideName(r);
  var st = statusOf(r);
  var np = hasProj(r);
  var cnt = '<div class="cprog num">' + f1(r.eevp) + ' %<span class="prog"><i style="width:' + Math.min(100, r.eevp || 0) + '%"></i></span></div>';
  var part = r.partial_B == null ? '<span class="sp">—</span>' :
    '<div class="pair">' + tx(r) + '<b class="d">' + f1(r.partial_B) + '</b><span class="sp">·</span>' + ty(r) + '<b class="r">' + f1(r.partial_R) + '</b></div>';
  var proj, prob;
  if (r.same_party) {
    proj = '<span class="chip na">' + samePartyTxt(r) + '</span><div class="cil">' + esc(candTxt(r, 'x') + (r.y_party ? ' · ' + candTxt(r, 'y') : '')) + '</div>';
    prob = '<span class="sp">—</span>';
  } else if (!np) {
    proj = '<span class="sp">—</span>'; prob = '<span class="sp">—</span>';
  } else {
    proj = '<div class="pair">' + tx(r) + '<b class="d">' + f1(r.proj_B) + '</b><span class="sp">·</span>' + ty(r) + '<b class="r">' + f1(r.proj_R) + '</b></div>' +
      '<div class="sbar" aria-hidden="true"><i class="a" style="width:' + r.proj_B + '%"></i><i class="b" style="width:' + r.proj_R + '%"></i></div>' +
      '<div class="cil"><span>' + esc(xn(r)) + ' ' + frange(r.ci90_B) + '</span><span>' + esc(yn(r)) + ' ' + frange(r.ci90_R) + '</span></div>';
    var pw = r.p_B_win;
    prob = '<div class="pair">' + tx(r) + '<b class="d">' + fprob(pw) + '</b></div><div class="pair" style="margin-top:3px">' + ty(r) + '<b class="r">' + fprob(1 - pw) + '</b></div>';
  }
  var stat = '<span class="' + (st.k === 3 ? 'st-won ' + st.cls : '') + '">' + esc(st.t) + '</span>';
  var nm = '<div class="rn">' + esc(raceLabel(r)) + '<small>' + esc(STATE_NAMES[r.state] || '') + (r.runoff_risk ? ' · 2ª vuelta: ' + fprob(r.p_runoff) : '') + (r.tabulation === 'ranked-choice' ? ' · voto ordenado' : '') + '</small>' + (r.x_name ? '<small>' + esc(candTxt(r, 'x') + (r.y_party ? ' vs ' + candTxt(r, 'y') : '')) + '</small>' : '') + '</div>';
  return '<tr tabindex="0" data-id="' + esc(r.id) + '" class="' + (r.id === SEL ? 'sel' : '') + '">' +
    '<td class="c-n" data-l="Carrera">' + nm + '</td><td class="c-r" data-l="Rating">' + ratingChip(r) + '</td>' +
    '<td class="c-c" data-l="Contado">' + cnt + '</td><td class="c-p" data-l="Parcial (D/I · R)">' + part + '</td>' +
    '<td class="c-proj" data-l="Proyección e IC 90 %">' + proj + '</td><td class="c-pr" data-l="Prob. de ganar">' + prob + '</td>' +
    '<td class="c-s" data-l="Estado">' + stat + '</td></tr>';
}
function renderTable() {
  var f = filteredRaces(), s = UI.sort[UI.off];
  var head = '<thead><tr>' + COLS.map(function (c) {
    var on = s.k === c.k;
    return '<th scope="col" data-k="' + c.k + '"' + (on ? ' aria-sort="' + (s.dir > 0 ? 'ascending' : 'descending') + '"' : '') + '><button type="button">' + c.l + '</button></th>';
  }).join('') + '</tr></thead>';
  var body = f.rows.length ? f.rows.map(rowHTML).join('') : '';
  var sc = $('#tscroll'), top = sc.scrollTop;
  $('#rt').innerHTML = head + '<tbody>' + (body || '<tr><td colspan="7" class="empty" style="display:table-cell">No hay carreras que coincidan.</td></tr>') + '</tbody>';
  sc.scrollTop = top;
  $('#tcount').textContent = f.rows.length + ' de ' + f.total + ' carreras' + (UI.off === 'H' && !UI.allH ? ' (competitivas: parejas, inclinadas o con chances entre 10 % y 90 %)' : '');
  $('#allH').checked = UI.allH;
}

/* ---------- mapas ---------- */
var METRICS = {
  proj: {l: 'Proyección (% D/I vs R)', kind: 'div', span: 15},
  prob: {l: 'Probabilidad de ganar', kind: 'div', span: 50},
  part: {l: 'Conteo parcial', kind: 'div', span: 15},
  cnt:  {l: '% contado', kind: 'seq'}
};
function metricVal(r, m) {
  if (!r || r.same_party) return null;
  if (m === 'proj') return r.proj_B;
  if (m === 'prob') return r.p_B_win == null ? null : r.p_B_win * 100;
  if (m === 'part') return r.partial_B;
  if (m === 'cnt') return r.eevp;
}
function colorFor(m, v) {
  if (v == null || isNaN(v)) return naColor();
  var M = METRICS[m];
  return M.kind === 'seq' ? seqColor(v) : divColor((v - 50) / M.span);
}
function legendHTML(m) {
  var M = METRICS[m];
  if (M.kind === 'seq') return '<span>0 %</span><div class="gr" style="background:' + gradient('seq') + '"></div><span>100 % contado</span><span class="na"><i style="background:' + naColor() + '"></i>sin dato</span>';
  var lo = 50 - M.span, hi = 50 + M.span;
  return '<span class="r"><b>' + lo + (m === 'prob' ? ' %' : ' %') + '</b> R</span><div class="gr" style="background:' + gradient('div') + '"></div><span class="d">D/Ind. <b>' + hi + ' %</b></span><span class="na"><i style="background:' + naColor() + '"></i>sin dato / sin elección</span>';
}
function mkMap(el, interactive) {
  var m = L.map(el, {crs: L.CRS.Simple, zoomSnap: 0.25, zoomDelta: 0.5, attributionControl: false, minZoom: -8, maxZoom: 6,
    scrollWheelZoom: false, dragging: interactive !== false && !L.Browser.mobile, zoomControl: true});
  return m;
}
function ttPair(r) {
  if (r.same_party) return '<div class="m">' + esc(samePartyTxt(r)) + ' · ' + esc(candTxt(r, 'x') + (r.y_party ? ' / ' + candTxt(r, 'y') : '')) + '</div>';
  return '<div class="row"><span>' + tx(r) + ' ' + esc(xn(r)) + '</span><b>' + fpct(r.proj_B) + ' · ' + fprob(r.p_B_win) + '</b></div>' +
         '<div class="row"><span>' + ty(r) + ' ' + esc(yn(r)) + '</span><b>' + fpct(r.proj_R) + ' · ' + fprob(r.p_B_win == null ? null : 1 - r.p_B_win) + '</b></div>' +
         '<div class="m">proyección · prob. de ganar · ' + f1(r.eevp) + ' % contado' + (r.partial_B != null ? ' · parcial ' + f1(r.partial_B) + ' / ' + f1(r.partial_R) : '') + '</div>';
}
function strokeColor() { return css('--card'); }

function stateRaces(abbr) {
  return DATA.races.filter(function (r) { return r.office === UI.m1off && r.state === abbr; });
}
function primaryOf(rs) {
  if (!rs.length) return null;
  return rs.slice().sort(function (a, b) { return compKey(a) - compKey(b); })[0];
}
function styleState(f) {
  var a = f.properties.a, rs = stateRaces(a);
  if (!rs.length) return {fillColor: naColor(), fillOpacity: 0.35, color: strokeColor(), weight: 1};
  return {fillColor: colorFor(UI.m1met, metricVal(primaryOf(rs), UI.m1met)), fillOpacity: 1, color: strokeColor(), weight: 1};
}
function styleDistrict(f) {
  var r = HMAP[f.properties.id];
  return {fillColor: r ? colorFor(UI.m2met, metricVal(r, UI.m2met)) : naColor(), fillOpacity: r ? 1 : 0.3, color: strokeColor(), weight: 0.4};
}
function fitMap(map, layer) {
  map.invalidateSize();
  var b = layer.getBounds();
  map.fitBounds(b, {padding: [8, 8]});
  map.setMinZoom(map.getZoom() - 1);
}
function hover(layer, styler) {
  layer.on('mouseover', function () { layer.setStyle({weight: 2, color: css('--ink')}); layer.bringToFront(); });
  layer.on('mouseout', function () { layer.setStyle(styler(layer.feature)); });
}
function fill(sel, m) { $(sel).innerHTML = Object.keys(METRICS).map(function (k) { return '<option value="' + k + '"' + (k === m ? ' selected' : '') + '>' + METRICS[k].l + '</option>'; }).join(''); }

function renderMaps() {
  if (!$('#m1met').options.length) { fill('#m1met', UI.m1met); fill('#m2met', UI.m2met); }
  Array.prototype.forEach.call(document.querySelectorAll('#m1off button'), function (b) { b.classList.toggle('on', b.dataset.v === UI.m1off); b.setAttribute('aria-pressed', b.dataset.v === UI.m1off); });
  $('#lg1').innerHTML = legendHTML(UI.m1met);
  $('#lg2').innerHTML = legendHTML(UI.m2met);
  if (!GEO.states) { Promise.all([getGeo('states'), getGeo('districts')]).then(function (g) { GEO.states = g[0]; GEO.districts = g[1]; buildMaps(); restyleMaps(); }).catch(function (e) { $('#errbox').textContent = 'No pude cargar la geometría: ' + e.message; }); return; }
  if (!MAP.m1) buildMaps();
  restyleMaps();
}
function buildMaps() {
  if (MAP.m1 || !GEO.states) return;
  var m1 = mkMap('map1');
  MAP.m1 = m1;
  MAP.s1 = L.geoJSON(GEO.states, {style: styleState, onEachFeature: function (f, l) {
    hover(l, styleState);
    l.bindTooltip(function () { return stateTip(f.properties.a); }, {sticky: true});
    l.on('click', function () {
      var rs = stateRaces(f.properties.a);
      if (rs.length === 1) openRace(rs[0].id);
      else if (rs.length > 1) {
        var html = '<div class="pop"><b>' + (STATE_NAMES[f.properties.a] || '') + '</b>' + rs.map(function (r) { return '<button type="button" data-id="' + esc(r.id) + '">' + esc(raceTitle(r)) + '</button>'; }).join('') + '</div>';
        L.popup().setLatLng(l.getBounds().getCenter()).setContent(html).openOn(m1);
      }
    });
  }}).addTo(m1);
  fitMap(m1, MAP.s1);
  var m2 = mkMap('map2');
  MAP.m2 = m2;
  MAP.s2 = L.geoJSON(GEO.districts, {style: styleDistrict, onEachFeature: function (f, l) {
    if (f.properties.id === 'DC-1' || !HMAP[f.properties.id]) { /* sin carrera */ }
    hover(l, styleDistrict);
    l.bindTooltip(function () {
      var r = HMAP[f.properties.id];
      return r ? '<div class="tt"><b>' + esc(raceTitle(r)) + '</b>' + ttPair(r) + '</div>' : '<div class="tt"><b>' + esc(f.properties.id) + '</b><div class="m">sin carrera</div></div>';
    }, {sticky: true});
    l.on('click', function () { var r = HMAP[f.properties.id]; if (r) openRace(r.id); });
  }}).addTo(m2);
  MAP.b2 = L.geoJSON(GEO.states, {interactive: false, style: function () { return {fill: false, color: css('--ink2'), weight: 1, opacity: 0.55}; }}).addTo(m2);
  fitMap(m2, MAP.s2);
}
function stateTip(a) {
  var rs = stateRaces(a);
  var h = '<div class="tt"><b>' + esc(STATE_NAMES[a] || a) + '</b>';
  if (!rs.length) return h + '<div class="m">sin elección de ' + (UI.m1off === 'S' ? 'Senado' : 'gobernador') + '</div></div>';
  rs.forEach(function (r) { h += (rs.length > 1 ? '<div class="m" style="margin-top:6px">' + esc(raceTitle(r)) + '</div>' : '') + ttPair(r); });
  return h + '</div>';
}
function restyleMaps() {
  if (MAP.s1) MAP.s1.setStyle(styleState);
  if (MAP.s2) MAP.s2.setStyle(styleDistrict);
  if (MAP.b2) MAP.b2.setStyle({color: css('--ink2')});
}

/* ---------- panel de detalle ---------- */
var DM = {part:'Parcial', proj:'Proyección', swing:'Cambio vs. base pres.', cnt:'% contado'};
function openRace(id, noPush) {
  if (!RI[id]) return;
  SEL = id;
  $('#drawer').classList.add('on'); $('#scrim').classList.add('on'); $('#drawer').setAttribute('aria-hidden', 'false');
  $('.db', $('#drawer')).scrollTop = 0; $('#drawer').scrollTop = 0;
  if (!noPush) try { history.replaceState(null, '', '#race=' + encodeURIComponent(id)); } catch (e) {}
  renderTable();
  (GEO.counties ? Promise.resolve() : getGeo('counties').then(function (g) { GEO.counties = g; })).then(function () {
    return GEO.districts ? null : getGeo('districts').then(function (g) { GEO.districts = g; });
  }).then(function () { renderDetail(true); }).catch(function (e) { $('#dNote').textContent = 'No pude cargar la geometría: ' + e.message; renderDetail(true); });
}
function closeRace() {
  SEL = null;
  $('#drawer').classList.remove('on'); $('#scrim').classList.remove('on'); $('#drawer').setAttribute('aria-hidden', 'true');
  try { history.replaceState(null, '', location.pathname + location.search); } catch (e) {}
  renderTable();
}
function unitVal(u, mode) {
  if (!u) return null;
  if (mode === 'part') return u.p;
  if (mode === 'proj') return u.j;
  if (mode === 'cnt') return u.e;
  if (mode === 'swing') return u.j != null && u.b != null ? u.j - u.b : null;
}
function unitColor(u, mode) {
  var v = unitVal(u, mode);
  if (v == null) return naColor();
  if (mode === 'cnt') return seqColor(v);
  if (mode === 'swing') return divColor(v / 10);
  return divColor((v - 50) / 20);
}
function mean(a, k) { var s = 0, n = 0; a.forEach(function (u) { if (u[k] != null) { s += u[k]; n++; } }); return n ? s / n : null; }

function detailGeo(r) {
  var units = UNITS[r.id] || {}, arr = Object.keys(units).map(function (k) { return units[k]; });
  var byF = {};
  arr.forEach(function (u) { if (u.f && u.f.length === 5) byF[u.f] = u; });
  var feats = (GEO.counties ? GEO.counties.features : []).filter(function (f) {
    return byF[f.properties.f] && (r.office === 'H' || f.properties.s === r.state);
  });
  var fallback = !feats.length || feats.length < 0.5 * arr.length;
  var agg = null;
  if (fallback && arr.length && GEO.states) {
    feats = GEO.states.features.filter(function (f) { return f.properties.a === r.state; });
    agg = {n: STATE_NAMES[r.state] + ' (promedio de ' + arr.length + ' unidades)', e: mean(arr, 'e'), p: mean(arr, 'p'), j: mean(arr, 'j'), b: mean(arr, 'b')};
  }
  return {arr: arr, byF: byF, feats: feats, agg: agg, fallback: fallback && !!agg};
}

function unitTip(u, r) {
  var L_ = xn(r), R_ = yn(r), has = function (x) { return x != null; };
  var h = '<div class="tt"><b>' + esc(u.n) + '</b>';
  h += '<div class="row"><span>Contado</span><b>' + fpct(u.e) + '</b></div>';
  h += '<div class="row"><span>Parcial</span><b>' + (has(u.p) ? L_ + ' ' + f1(u.p) + ' · ' + R_ + ' ' + f1(100 - u.p) : '—') + '</b></div>';
  h += '<div class="row"><span>Proyección</span><b>' + (has(u.j) ? L_ + ' ' + f1(u.j) + ' · ' + R_ + ' ' + f1(100 - u.j) : '—') + '</b></div>';
  h += '<div class="row"><span>Base pres. (D · R)</span><b>' + (has(u.b) ? f1(u.b) + ' · ' + f1(100 - u.b) : '—') + '</b></div>';
  if (has(u.j) && has(u.b)) { var s = u.j - u.b; h += '<div class="row"><span>Cambio</span><b>' + (s > 0 ? '+' : '') + f1(s) + ' pts ' + (s >= 0 ? L_ : R_) + '</b></div>'; }
  return h + '</div>';
}

function renderDetail(fit) {
  var r = RI[SEL]; if (!r) return;
  var L_ = sideLetter(r), SD = sideName(r);
  $('#dTitle').textContent = raceTitle(r);
  var st = statusOf(r);
  $('#dMeta').innerHTML = ratingChip(r) + ' &nbsp;' + f1(r.eevp) + ' % contado · ' + esc(st.t) + (r.runoff_risk ? ' · prob. de segunda vuelta (regla del 50 %): ' + fprob(r.p_runoff) : '') + (r.tabulation === 'ranked-choice' ? ' · voto ordenado (RCV)' : '');
  var colD = '<div><h4 class="d">' + tx(r) + esc(candTxt(r, 'x')) + '</h4>';
  var colR = '<div><h4 class="r">' + ty(r) + esc(candTxt(r, 'y')) + '</h4>';
  if (r.same_party) {
    $('#dCmp').innerHTML = '<div style="grid-column:1/-1"><h4>' + samePartyTxt(r) + (r.x_name ? ': ' + esc(candTxt(r, 'x') + (r.y_party ? ' y ' + candTxt(r, 'y') : '')) : '') + '</h4><p class="note" style="margin:0">' + (r.y_party ? 'Compiten candidatos del mismo partido' : 'Candidato sin rival') + ': no hay proyección entre partidos.</p></div>';
  } else {
    var pw = r.p_B_win;
    $('#dCmp').innerHTML =
      colD + '<dl><dt>Conteo parcial</dt><dd class="v d">' + fpct(r.partial_B) + '</dd><dt>Proyección</dt><dd class="v d">' + fpct(r.proj_B) + '</dd><dt>Intervalo 90 %</dt><dd class="d">' + frange(r.ci90_B) + '</dd><dt>Prob. de ganar</dt><dd class="v d">' + fprob(pw) + '</dd></dl></div>' +
      colR + '<dl><dt>Conteo parcial</dt><dd class="v r">' + fpct(r.partial_R) + '</dd><dt>Proyección</dt><dd class="v r">' + fpct(r.proj_R) + '</dd><dt>Intervalo 90 %</dt><dd class="r">' + frange(r.ci90_R) + '</dd><dt>Prob. de ganar</dt><dd class="v r">' + fprob(pw == null ? null : 1 - pw) + '</dd></dl></div>';
  }
  $('#dMode').innerHTML = Object.keys(DM).map(function (k) { return '<button type="button" data-v="' + k + '" aria-pressed="' + (UI.dmode === k) + '" class="' + (UI.dmode === k ? 'on' : '') + '">' + DM[k] + '</button>'; }).join('');
  $('#dLg').innerHTML = detailLegend();

  var G = detailGeo(r), key = r.id + '|' + G.fallback + '|' + G.feats.length;
  var unitFor = function (f) { return G.fallback ? G.agg : G.byF[f.properties.f]; };
  var styler = function (f) { return {fillColor: unitColor(unitFor(f), UI.dmode), fillOpacity: 1, color: strokeColor(), weight: 0.8}; };
  if (!DET.map) DET.map = mkMap('dmap');
  var map = DET.map;
  if (DET.key !== key || fit) {
    if (DET.layer) map.removeLayer(DET.layer);
    if (DET.outline) map.removeLayer(DET.outline);
    DET.outline = null;
    if (G.feats.length) {
      DET.layer = L.geoJSON({type: 'FeatureCollection', features: G.feats}, {style: styler, onEachFeature: function (f, l) {
        hover(l, styler);
        l.bindTooltip(function () { var u = unitFor(f); return u ? unitTip(u, r) : '<div class="tt"><b>' + esc(f.properties.f) + '</b></div>'; }, {sticky: true});
      }}).addTo(map);
      var fitLayer = DET.layer;
      if (r.office === 'H' && GEO.districts) {
        var df = GEO.districts.features.filter(function (f) { return f.properties.id === r.state + '-' + r.seat; });
        if (df.length) {
          DET.outline = L.geoJSON({type: 'FeatureCollection', features: df}, {interactive: false, style: function () { return {fill: false, color: css('--ink'), weight: 2.4, opacity: 0.9}; }}).addTo(map);
          fitLayer = DET.outline;
        }
      }
      map.invalidateSize();
      map.fitBounds(fitLayer.getBounds(), {padding: [10, 10]});
      map.setMinZoom(map.getZoom() - 2);
    } else DET.layer = null;
    DET.key = key;
  } else if (DET.layer) {
    DET.layer.setStyle(styler);
    if (DET.outline) DET.outline.setStyle({color: css('--ink')});
  }
  DET.styler = styler;
  var note = '';
  if (!G.feats.length) note = 'No hay geometría para estas unidades.';
  else if (G.fallback && G.arr.every(function (u) { return !u.f || u.f.length === 2; })) note = G.arr.length === 1 ? 'Esta carrera tiene una sola unidad estatal: todavía no hay desglose por condado, se muestra el estado entero.' : 'Las unidades de esta carrera no son condados (p. ej. distritos legislativos): se muestra el estado entero con el promedio.';
  else if (G.fallback) note = 'Las unidades de esta carrera no coinciden con condados del mapa (distritos legislativos o regiones de planificación): se muestra el estado entero con el promedio.';
  else if (r.office === 'H') note = 'Condados que tocan el distrito; la línea gruesa marca el límite del distrito. Un condado puede estar repartido entre varios distritos.';
  $('#dNote').textContent = note;
  renderUnits(r, G);
  setTimeout(function () { if (DET.map) DET.map.invalidateSize(); }, 280);
}
function detailLegend() {
  var m = UI.dmode;
  if (m === 'cnt') return '<span>0 %</span><div class="gr" style="background:' + gradient('seq') + '"></div><span>100 % contado</span><span class="na"><i style="background:' + naColor() + '"></i>sin dato</span>';
  if (m === 'swing') return '<span class="r"><b>−10</b> pts hacia R</span><div class="gr" style="background:' + gradient('div') + '"></div><span class="d">hacia D/Ind. <b>+10</b> pts</span><span class="na"><i style="background:' + naColor() + '"></i>sin dato</span>';
  return '<span class="r"><b>30 %</b> R</span><div class="gr" style="background:' + gradient('div') + '"></div><span class="d">D/Ind. <b>70 %</b></span><span class="na"><i style="background:' + naColor() + '"></i>sin dato</span>';
}
function renderUnits(r, G) {
  var L_ = xn(r), R_ = yn(r);
  var rows = G.arr.slice().sort(function (a, b) { return String(a.n).localeCompare(b.n, 'es'); });
  if (rows.length > 600) rows = rows.slice(0, 600);
  var pair = function (x) { return x == null ? '—' : '<span class="d">' + f1(x) + '</span> · <span class="r">' + f1(100 - x) + '</span>'; };
  var html = '<table><thead><tr><th>Unidad</th><th>Contado %</th><th>Parcial ' + L_ + ' · ' + R_ + '</th><th>Proyección ' + L_ + ' · ' + R_ + '</th><th>Base pres. D · R</th><th>Cambio</th></tr></thead><tbody>';
  rows.forEach(function (u) {
    var s = u.j != null && u.b != null ? u.j - u.b : null;
    html += '<tr><td>' + esc(u.n) + '</td><td>' + f1(u.e) + '</td><td>' + pair(u.p) + '</td><td>' + pair(u.j) + '</td><td>' + pair(u.b) + '</td><td>' + (s == null ? '—' : '<span class="' + (s >= 0 ? 'd' : 'r') + '">' + (s > 0 ? '+' : '') + f1(s) + '</span>') + '</td></tr>';
  });
  $('#dUnits').innerHTML = rows.length ? html + '</tbody></table>' : '<p class="empty">Sin datos por unidad para esta carrera.</p>';
}

/* ---------- tema ---------- */
function setTheme(t) {
  if (t) document.documentElement.setAttribute('data-theme', t); else document.documentElement.removeAttribute('data-theme');
  try { if (t) localStorage.setItem('theme', t); } catch (e) {}
  rethemeAll();
}
function rethemeAll() {
  if (!DATA) return;
  chartDefaults();
  Object.keys(CH).forEach(function (k) { CH[k].destroy(); delete CH[k]; });
  renderChambers(); renderEvo(); renderMaps();
  if (SEL && RI[SEL]) renderDetail(false);
}

/* ---------- eventos ---------- */
function bind() {
  $('#themeBtn').addEventListener('click', function () { setTheme(isDark() ? 'light' : 'dark'); });
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () { if (!document.documentElement.getAttribute('data-theme')) rethemeAll(); });
  $('#evoCh').addEventListener('click', function (e) { var b = e.target.closest('button'); if (!b) return; UI.evoCh = b.dataset.v; toggleSeg('#evoCh', b); renderEvo(); });
  $('#evoMet').addEventListener('click', function (e) { var b = e.target.closest('button'); if (!b) return; UI.evoMet = b.dataset.v; toggleSeg('#evoMet', b); renderEvo(); });
  $('#tabOff').addEventListener('click', function (e) { var b = e.target.closest('button'); if (!b) return; UI.off = b.dataset.v; renderTabs(); renderTable(); });
  $('#q').addEventListener('input', function (e) { UI.q = e.target.value; renderTable(); });
  $('#allH').addEventListener('change', function (e) { UI.allH = e.target.checked; renderTable(); });
  $('#rt').addEventListener('click', function (e) {
    var th = e.target.closest('th');
    if (th) {
      var k = th.dataset.k, s = UI.sort[UI.off];
      if (s.k === k) s.dir = -s.dir; else { s.k = k; s.dir = (k === 'name' || k === 'comp' || k === 'stat' && false) ? 1 : (k === 'rating' ? 1 : -1); }
      renderTable(); return;
    }
    var tr = e.target.closest('tr[data-id]'); if (tr) openRace(tr.dataset.id);
  });
  $('#rt').addEventListener('keydown', function (e) { if (e.key === 'Enter') { var tr = e.target.closest('tr[data-id]'); if (tr) openRace(tr.dataset.id); } });
  $('#m1off').addEventListener('click', function (e) { var b = e.target.closest('button'); if (!b) return; UI.m1off = b.dataset.v; renderMaps(); });
  $('#m1met').addEventListener('change', function (e) { UI.m1met = e.target.value; renderMaps(); });
  $('#m2met').addEventListener('change', function (e) { UI.m2met = e.target.value; renderMaps(); });
  $('#dMode').addEventListener('click', function (e) { var b = e.target.closest('button'); if (!b) return; UI.dmode = b.dataset.v; renderDetail(false); });
  $('#dClose').addEventListener('click', closeRace);
  $('#scrim').addEventListener('click', closeRace);
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && SEL) closeRace(); });
  document.addEventListener('click', function (e) { var b = e.target.closest('.pop button'); if (b) { openRace(b.dataset.id); if (MAP.m1) MAP.m1.closePopup(); } });
}
function toggleSeg(sel, btn) {
  Array.prototype.forEach.call(document.querySelectorAll(sel + ' button'), function (b) { b.classList.toggle('on', b === btn); b.setAttribute('aria-pressed', b === btn); });
}

/* ---------- arranque ---------- */
try { var th = localStorage.getItem('theme'); if (th) document.documentElement.setAttribute('data-theme', th); } catch (e) {}
chartDefaults();
bind();
load().then(function () {
  var m = /race=([^&]+)/.exec(location.hash);
  if (m && DATA) openRace(decodeURIComponent(m[1]), true);
});
setInterval(load, REFRESH_MS);
setInterval(tickLive, 1000);
})();
