/* EDIFY reels: one config per page film, ported from assets/motion/<page>/<page>-film.html.
   The object, its chapters and its keyframes are the films' own; the words live in each page.
   A.el('id') finds #r-id inside the reel. */
(function () {
  'use strict';
  var R = window.EdReel;
  if (!R) return;

  /* ---------- 02 Home: one ribbon, one developer with one agent. It lands on the workflow rail,
     then becomes the mark as one unbroken path. */
  R.define('home', {
    duration: 43,
    paper: [-1, 0, 6.6, 0.9],
    geom: { NU: 240, NV: 56, NC: 8 },
    ribbons: [
      { phi0: 0.2, span: 5.4, r0: 0.58, r1: 0.34, h0: 0.0, h1: 0.46, f: 1.15, ph: 0.4, tilt: 0.42, roll: 0.18, w0: 0.56, tw: 3.1, th0: 0.4, taper: 0.42, blueStrands: [44, 49] }
    ],
    chapters: [
      { t: 0, n: 'Make it reliable' }, { t: 6.9, n: 'The problem' }, { t: 13.0, n: 'How it works' },
      { t: 20.5, n: 'The codebase graph' }, { t: 27.5, n: 'Verification' }, { t: 33.5, n: 'Local-first' }
    ],
    init: function (A) {
      this.rail = A.target({ pts: [[60, 640], [1860, 640]], w: 150, T: 30, tone: 0.8 });
      this.mk = A.mark(960, 430, 4.0, [{ s0: 0, s1: 5, slot: 0, n: 1 }]);
    },
    state: function (t, S, A) {
      var E = A.E, pr = A.pr;
      var p = A.kf([[0, 1540, 560, 245], [6.8, 1540, 560, 245], [8.3, 1570, 470, 205], [12.6, 1570, 470, 205], [14.6, 1330, 470, 260],
                    [19.6, 1330, 470, 260], [21.0, 1460, 360, 215], [27.2, 1460, 360, 215], [33.4, 1400, 520, 280], [37.4, 1400, 520, 280]], t);
      S.cx = p[0]; S.cy = p[1]; S.s = p[2];
      S.yaw = 0.9 + 0.16 * t + 2.4 * E.out(A.cl(t / 15));
      S.jitter = 1.0 - pr(t, 13.2, 3.2, E.inout);
      S.reveal[0] = pr(t, 0.25, 1.8, E.out);
      S.alpha = A.cl(1 - pr(t, 27.3, 0.7, E.inout) + pr(t, 33.3, 0.9, E.out));
      var railK = pr(t, 14.9, 1.5, E.emph) * (1 - pr(t, 19.95, 1.3, E.emph));
      var markK = pr(t, 37.5, 1.9, E.emph);
      if (markK > 0) S.target[0] = { k: markK, def: this.mk };
      else if (railK > 0) S.target[0] = { k: railK, def: this.rail };
      S.blueMix = 1 - pr(t, 38.6, 1.0, E.inout);
      S.pulse[0] = 0.25 * Math.max(0, 1 - Math.abs(t - 29.05) / 0.5);
    }
  });

  /* ---------- 03 How it works: three ribbons, spec, plan, tasks. Three passes tighten them; in the
     build they lie straight as three lanes and go red, then return; in verify the plan ribbon
     shows oxide when edify check names plan.md:70. The three become the mark. */
  R.define('how-it-works', {
    duration: 45,
    paper: [8.45, 0.95, 15.6, 0.9],
    geom: { NU: 170, NV: 38, NC: 7 },
    ribbons: [
      { phi0: 0.00, span: 4.30, r0: 0.62, r1: 0.30, h0: 0.02, h1: 0.40, f: 0.80, ph: 0.0, tilt: 0.38, roll: 0.12, w0: 0.46, tw: 2.2, th0: 0.30, taper: 0.55 },
      { phi0: 2.10, span: 3.90, r0: 0.78, r1: 0.20, h0: -0.10, h1: 0.34, f: 1.10, ph: 1.4, tilt: -0.55, roll: 0.30, w0: 0.40, tw: -1.8, th0: 1.20, taper: 0.45 },
      { phi0: 4.20, span: 4.40, r0: 0.52, r1: 0.36, h0: 0.14, h1: 0.32, f: 0.60, ph: 2.1, tilt: 0.92, roll: -0.40, w0: 0.38, tw: 2.6, th0: 2.00, taper: 0.60, blueStrands: [28, 32] }
    ],
    chapters: [
      { t: 0, n: 'Think hard once' }, { t: 8.4, n: 'The map' }, { t: 16.0, n: 'Build' },
      { t: 24.2, n: 'Verify' }, { t: 31.5, n: 'Six commands' }, { t: 37.0, n: 'Limits, first' }
    ],
    init: function (A) {
      this.lanes = [610, 682, 754].map(function (y) { return A.target({ pts: [[60, y], [1860, y]], w: 48, T: 11, tone: 0.8 }); });
      this.mk = A.mark(960, 430, 4.0, A.markAssign());
      var box = A.el('tests'), h = '';
      for (var i = 0; i < 32; i++) h += '<i></i>';
      box.innerHTML = h; this.tests = box.children; this.cap = A.el('testcap');
    },
    state: function (t, S, A) {
      var E = A.E, pr = A.pr;
      var p = A.kf([[0, 1380, 560, 330], [8.3, 1380, 560, 330], [9.6, 1610, 520, 212], [16.0, 1610, 520, 212], [16.05, 1560, 300, 110],
                    [31.6, 1560, 300, 110], [32.6, 1500, 600, 250], [36.8, 1500, 600, 250], [37.9, 1420, 520, 270], [40.2, 1420, 520, 270]], t);
      S.cx = p[0]; S.cy = p[1]; S.s = p[2];
      var land = [1.6, 3.0, 4.4], inLanes = t >= 16.2 && t < 24.3;
      S.alpha = t < 16.2 ? 1 - pr(t, 15.35, 0.6, E.inout) : inLanes ? 1 - pr(t, 23.2, 0.7, E.inout) : pr(t, 24.6, 0.8, E.out);
      for (var r = 0; r < 3; r++) {
        S.reveal[r] = inLanes ? pr(t, 16.4 + r * 0.2, 1.4, E.edify) : pr(t, land[r] - 0.5, 1.4, E.out);
        S.place[r] = { k: 0, jitter: 1.3 * (1 - pr(t, land[r], 2.6, E.inout)) };
        if (inLanes) S.target[r] = { k: 1, def: this.lanes[r] };
        if (t > 19.0 && t < 20.4 + r * 0.75) S.color[r] = 'o';
      }
      if (t > 26.0 && t < 27.6) S.color[1] = 'o';
      var mk = pr(t, 40.4, 1.9, E.emph);
      if (mk > 0) for (var r2 = 0; r2 < 3; r2++) S.target[r2] = { k: mk, def: this.mk };
      S.blueMix = 1 - pr(t, 41.4, 1.0, E.inout);
    },
    onFrame: function (t, A) {
      for (var i = 0; i < this.tests.length; i++) {
        var s = this.tests[i].style, on = A.pr(t, 19.0 + i * 0.02, 0.3, A.E.edify), out = A.pr(t, 23.8, 0.3, A.E.inout);
        s.opacity = (on * (1 - out)).toFixed(3);
        s.background = t > 20.4 + i * 0.07 ? '#E8ECF2' : '';
      }
      var txt = t < 19.0 || t > 24.0 ? '' : t < 20.4 ? 'phase 2 · the target exists, and it is red' : t < 22.7 ? 'phases 3 to 6 · red to green, in order' : 'phase 6 · the same target, green';
      if (this.cap.textContent !== txt) this.cap.textContent = txt;
    }
  });

  /* ---------- 04 Docs: the object is the map. 21 short ribbons are the 21 edges of the sample
     repo's graph; they float as a tangle until edify init prints the graph line, then land
     between the 18 nodes. Counts and named nodes are the real output; positions are drawn. */
  (function () {
    var N = [
      [1070, 590, 'package', ''],
      [1230, 360, 'module', ''], [1230, 520, 'module', ''], [1230, 680, 'module', ''], [1230, 820, 'module', ''],
      [1400, 310, 'file', 'src/api.py'], [1400, 520, 'file', 'src/auth/clock.py'], [1400, 620, 'file', 'src/auth/session.py'], [1400, 730, 'file', ''], [1400, 830, 'file', ''],
      [1600, 200, 'route', 'POST /login'], [1600, 270, 'route', 'POST /refresh'], [1600, 350, 'symbol', 'login'], [1600, 420, 'symbol', 'refresh'],
      [1600, 520, 'symbol', 'is_expired'], [1600, 620, 'symbol', 'create_session'], [1600, 730, 'symbol', ''], [1600, 830, 'symbol', '']
    ];
    var EDG = [[0,1],[0,2],[0,3],[0,4],[1,5],[2,6],[2,7],[3,8],[4,9],[5,10],[5,11],[5,12],[5,13],[6,14],[7,15],[8,16],[9,17],[15,14],[12,15],[13,15],[7,6]];
    function rnd(k) { var x = Math.sin(k * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); }
    var RB = EDG.map(function (e, k) {
      return { phi0: rnd(k) * 6.28, span: 2.0 + rnd(k + 40) * 1.4, r0: 0.35 + rnd(k + 80) * 0.45, r1: 0.12, h0: (rnd(k + 9) - 0.5) * 0.5, h1: 0.3, f: 0.8, ph: rnd(k + 3) * 6,
        tilt: (rnd(k + 5) - 0.5) * 2.4, roll: (rnd(k + 7) - 0.5) * 2.4, w0: 0.11, wmin: 0.015, tw: 2.2, th0: rnd(k + 11) * 3, taper: 0.5 };
    });
    R.define('docs', {
      duration: 32,
      geom: { NU: 44, NV: 6, NC: 2 },
      ribbons: RB,
      chapters: [{ t: 0, n: 'Quickstart' }, { t: 6.4, n: 'What you see' }, { t: 16.0, n: 'Ask the map' }, { t: 24.0, n: 'One real task' }],
      init: function (A) {
        var BOW = { 17: 46, 18: 78, 19: 110, 20: -46 };
        this.edges = EDG.map(function (e, k) {
          var a = N[e[0]].slice(0, 2), b = N[e[1]].slice(0, 2), pts = [a, b];
          if (BOW[k]) pts = [a, [(a[0] + b[0]) / 2 + BOW[k], (a[1] + b[1]) / 2], b];
          return A.target({ pts: pts, w: 5, T: 3, tone: 0.72 });
        });
        this.mk = A.mark(960, 430, 4.0, A.markAssign());
      },
      state: function (t, S, A) {
        var E = A.E, pr = A.pr;
        var p = A.kf([[0, 1440, 560, 300], [6.2, 1440, 560, 300], [8.6, 1440, 540, 280]], t);
        S.cx = p[0]; S.cy = p[1]; S.s = p[2];
        S.yaw = 0.9 + 0.22 * t;
        S.jitter = 0.35;
        var mk = pr(t, 26.6, 1.9, E.emph);
        this.ek = [];
        for (var r = 0; r < A.NR; r++) {
          S.reveal[r] = pr(t, 0.4 + r * 0.05, 1.2, E.out);
          var k = pr(t, 8.8 + r * 0.13, 0.9, E.emph);
          this.ek.push(k);
          if (mk > 0) S.target[r] = { k: mk, def: this.mk };
          else if (k > 0) S.target[r] = { k: k, def: this.edges[r] };
        }
        if (t > 18.7 && t < 23.6) S.color[17] = 'b';
        if (t > 19.8 && t < 23.6) { S.color[18] = 'b'; S.color[19] = 'b'; }
        this.mk_k = mk;
      },
      drawOver: function (ctx, t, S, pal, A) {
        if (pal !== 'void') return;
        var fade = 1 - this.mk_k, pr = A.pr, E = A.E;
        var lit = {}; if (t > 17.5 && t < 23.6) lit[14] = 1; if (t > 18.7 && t < 23.6) lit[15] = 1; if (t > 19.8 && t < 23.6) { lit[12] = 1; lit[13] = 1; }
        ctx.save(); ctx.font = '12px "IBM Plex Mono", monospace'; ctx.textBaseline = 'middle';
        for (var n = 0; n < N.length; n++) {
          var a = 0;
          for (var e = 0; e < EDG.length; e++) if (EDG[e][0] === n || EDG[e][1] === n) a = Math.max(a, this.ek[e]);
          a = A.cl((a - 0.6) / 0.4) * fade; if (a <= 0) continue;
          var nd = N[n], sz = { package: 14, module: 11, file: 10, symbol: 8, route: 8 }[nd[2]];
          ctx.globalAlpha = a; ctx.fillStyle = '#07090C'; ctx.fillRect(nd[0] - sz / 2 - 3, nd[1] - sz / 2 - 3, sz + 6, sz + 6);
          if (nd[2] === 'route') { ctx.strokeStyle = lit[n] ? '#5A93F5' : '#E8ECF2'; ctx.lineWidth = 1; ctx.strokeRect(nd[0] - sz / 2 + 0.5, nd[1] - sz / 2 + 0.5, sz - 1, sz - 1); }
          else { ctx.fillStyle = lit[n] ? '#5A93F5' : '#E8ECF2'; ctx.fillRect(nd[0] - sz / 2, nd[1] - sz / 2, sz, sz); }
          if (nd[3]) {
            var col = lit[n] ? '#5A93F5' : 'rgba(232,236,242,0.55)';
            var lx = nd[2] === 'file' ? nd[0] - ctx.measureText(nd[3]).width / 2 : nd[0] + 16, ly = nd[2] === 'file' ? nd[1] - 18 : nd[1];
            ctx.fillStyle = '#07090C'; ctx.fillRect(lx - 4, ly - 9, ctx.measureText(nd[3]).width + 8, 18);
            ctx.fillStyle = col; ctx.textAlign = 'left'; ctx.fillText(nd[3], lx, ly);
          }
        }
        var cap = pr(t, 11.8, 0.42, E.edify) * (1 - pr(t, 26.2, 0.36, E.inout));
        if (cap > 0) {
          ctx.globalAlpha = cap; ctx.textAlign = 'left'; ctx.fillStyle = 'rgba(232,236,242,0.44)';
          ctx.fillText('the sample repo’s map · 18 nodes · 21 edges · positions drawn for this film', 1060, 920);
          ctx.fillText('package · modules · files · symbols and routes', 1060, 944);
        }
        ctx.restore();
      }
    });
  })();

  /* ---------- 05 Benchmarks: three identical ribbons for the three arms, turning in step. They
     flatten into the column rules of the empty table. No arm is coloured. */
  (function () {
    var RB = { phi0: 0.0, span: 4.3, r0: 0.62, r1: 0.30, h0: 0.02, h1: 0.40, f: 0.80, ph: 0.0, tilt: 0.38, roll: 0.12, w0: 0.46, tw: 2.2, th0: 0.30, taper: 0.55 };
    var ROWS = ['Tasks passed', 'Tests passing', 'Human interventions', 'Retries', 'Tokens / cost', 'Total time'];
    R.define('benchmarks', {
      duration: 37,
      paper: [7.55, 0.95, 14.5, 0.9],
      geom: { NU: 150, NV: 36, NC: 6 },
      ribbons: [RB, RB, RB],
      chapters: [{ t: 0, n: 'Same model' }, { t: 7.5, n: 'Status' }, { t: 15.0, n: 'The three arms' }, { t: 23.2, n: 'The minimum credible package' }, { t: 29.6, n: 'Help run it' }],
      init: function (A) {
        this.cols = [620, 1020, 1420].map(function (x) { return A.target({ pts: [[x, 318], [x, 752]], w: 14, T: 5, tone: 0.6 }); });
        this.mk = A.mark(960, 430, 4.0, A.markAssign());
        var h = '<div class="f-r f-h" role="row" data-ti="15.9" data-to="22.6" data-fx="fade"><span role="columnheader">metric</span><span role="columnheader">A &middot; agent alone</span><span role="columnheader">B &middot; spec kit</span><span role="columnheader">C &middot; EDIFY</span></div>';
        ROWS.forEach(function (r, i) {
          h += '<div class="f-r" role="row" data-ti="' + (16.2 + i * 0.12).toFixed(2) + '" data-to="22.6" data-fx="wipe"><span role="rowheader">' + r + '</span>' +
            [0, 1, 2].map(function () { return '<span class="f-d" role="cell">&mdash;</span>'; }).join('') + '</div>';
        });
        A.el('tbl').innerHTML = h;
      },
      state: function (t, S, A) {
        var E = A.E, pr = A.pr;
        var y = A.kf([[0, 610, 120], [7.2, 610, 120], [8.6, 560, 150], [29.4, 560, 150], [30.4, 600, 135]], t);
        var xs = t < 29 ? [1060, 1380, 1700] : [1100, 1400, 1700];
        S.alpha = A.cl(1 - pr(t, 22.8, 0.8, E.inout) + pr(t, 29.6, 0.9, E.out));
        var ck = pr(t, 13.3, 1.5, E.emph) * (1 - pr(t, 22.5, 1.1, E.emph)), mk = pr(t, 32.6, 1.9, E.emph);
        S.cx = xs[1]; S.cy = y[0]; S.s = y[1] * 2.2;
        for (var r = 0; r < 3; r++) {
          S.reveal[r] = pr(t, 0.5 + r * 0.12, 1.5, E.out);
          S.place[r] = { k: 1, cx: xs[r], cy: y[0], s: y[1], yaw: 0.9 + 0.3 * t, pitch: 0.3 };
          if (mk > 0) S.target[r] = { k: mk, def: this.mk };
          else if (ck > 0) S.target[r] = { k: ck, def: this.cols[r] };
        }
      }
    });
  })();

  /* ---------- 06 About: one ribbon, the path of the mark. It lands on the drawing as supplied,
     then resolves onto the constructed geometry. At the close it draws itself in path order. */
  (function () {
    var MP = [[6, 28], [44, 6], [66, 94], [30, 74], [94, 52]];
    function hand(mx, my, ms) {
      var pts = [], SUB = 8;
      var cj = [[1.6, -1.1], [-1.2, 0.9], [1.4, 1.2], [-1.5, -0.8], [0.9, 1.5]];
      for (var k = 0; k < 5; k++) {
        var A = MP[k], B = MP[(k + 1) % 5], dx = B[0] - A[0], dy = B[1] - A[1], L = Math.hypot(dx, dy), nx = -dy / L, ny = dx / L;
        for (var s = 0; s < SUB; s++) {
          var u = s / SUB, w = 2.2 * Math.sin(Math.PI * u) * Math.sin(u * 7.3 + k * 1.9);
          var x = A[0] + dx * u + nx * w + (s === 0 ? cj[k][0] : 0), y = A[1] + dy * u + ny * w + (s === 0 ? cj[k][1] : 0);
          pts.push([mx + (x - 50) * ms, my + (y - 50) * ms]);
        }
      }
      var top = []; for (var t = SUB; t < 2 * SUB; t++) top.push(t);
      return { pts: pts, closed: true, w: 11 * ms, T: 13, top: top, tone: 0.9 };
    }
    var WHOLE = [{ s0: 0, s1: 5, slot: 0, n: 1 }];
    R.define('about', {
      duration: 37,
      paper: [7.2, 0.95, 14.1, 0.9],
      geom: { NU: 240, NV: 48, NC: 8 },
      ribbons: [
        { phi0: 1.1, span: 5.0, r0: 0.62, r1: 0.30, h0: 0.02, h1: 0.44, f: 1.3, ph: 0.9, tilt: -0.4, roll: 0.35, w0: 0.5, tw: -2.6, th0: 1.0, taper: 0.45, blueStrands: [21, 25] }
      ],
      chapters: [{ t: 0, n: 'The same starting line' }, { t: 7.1, n: 'Two roots' }, { t: 14.5, n: 'The drawing' }, { t: 21.6, n: 'What we will not trade' }, { t: 28.5, n: 'Name the limit first' }],
      init: function (A) {
        this.MX = 1360; this.MY = 500; this.MS = 4.4;
        this.hand = A.target(hand(this.MX, this.MY, this.MS));
        this.markR = A.mark(this.MX, this.MY, this.MS, WHOLE);
        this.markC = A.mark(960, 430, 4.0, WHOLE);
      },
      state: function (t, S, A) {
        var E = A.E, pr = A.pr;
        var p = A.kf([[0, 1400, 540, 300], [6.8, 1400, 540, 300], [8.2, 1140, 520, 265], [13.8, 1140, 520, 265], [15.2, 1360, 500, 290]], t);
        S.cx = p[0]; S.cy = p[1]; S.s = p[2];
        S.jitter = 0.45 * (1 - pr(t, 13.6, 1.6, E.inout));
        S.reveal[0] = pr(t, 0.3, 1.8, E.out);
        var hk = pr(t, 15.0, 1.9, E.emph), cm = pr(t, 18.1, 1.5, E.emph);
        S.alpha = A.cl(1 - pr(t, 21.3, 0.7, E.inout));
        if (t < 32) {
          if (hk > 0) S.target[0] = { k: hk, def: this.hand, def2: this.markR, m: cm };
        } else {
          S.alpha = 1; S.target[0] = { k: 1, def: this.markC };
          S.reveal[0] = pr(t, 32.3, 1.8, E.inout);
          S.cx = 960; S.cy = 430; S.s = 200;
        }
        S.blueMix = t < 32 ? 1 - pr(t, 18.6, 0.9, E.inout) : 0;
      },
      drawUnder: function (ctx, t, S, pal, A) {
        if (pal !== 'void') return;
        var a = A.pr(t, 17.8, A.D.section, A.E.edify) * (1 - A.pr(t, 21.1, 0.4, A.E.inout));
        if (a <= 0) return;
        var mx = this.MX, my = this.MY, ms = this.MS, x0 = mx - 50 * ms, y0 = my - 50 * ms, sz = 100 * ms;
        ctx.save(); ctx.globalAlpha = a;
        ctx.strokeStyle = 'rgba(232,236,242,0.07)'; ctx.lineWidth = 1; ctx.beginPath();
        for (var g = 10; g < 100; g += 10) { ctx.moveTo(x0 + g * ms + 0.5, y0); ctx.lineTo(x0 + g * ms + 0.5, y0 + sz); ctx.moveTo(x0, y0 + g * ms + 0.5); ctx.lineTo(x0 + sz, y0 + g * ms + 0.5); }
        ctx.stroke();
        ctx.strokeStyle = 'rgba(232,236,242,0.30)'; ctx.strokeRect(x0 + 0.5, y0 + 0.5, sz, sz);
        ctx.restore();
      },
      drawOver: function (ctx, t, S, pal, A) {
        if (pal !== 'void') return;
        var a = A.pr(t, 18.4, A.D.el, A.E.edify) * (1 - A.pr(t, 21.1, 0.4, A.E.inout));
        if (a <= 0) return;
        var mx = this.MX, my = this.MY, ms = this.MS;
        ctx.save(); ctx.globalAlpha = a; ctx.font = '12px "IBM Plex Mono", monospace'; ctx.textBaseline = 'middle';
        var off = [[-44, 0], [0, -20], [0, 22], [-44, 12], [18, 0]];
        MP.forEach(function (q, k) {
          var x = mx + (q[0] - 50) * ms, y = my + (q[1] - 50) * ms;
          ctx.fillStyle = '#5A93F5'; ctx.fillRect(x - 4, y - 4, 8, 8);
          ctx.fillStyle = 'rgba(232,236,242,0.66)'; ctx.textAlign = 'left';
          ctx.fillText(q[0] + ' ' + q[1], x + off[k][0] - (off[k][0] === 0 ? 14 : 0), y + off[k][1]);
        });
        ctx.restore();
      }
    });
  })();

  /* ---------- 01 Teams: five ribbons, one per person, each in its own session window. They fuse
     into one form (the shared brain), and at the close become the five strokes of the mark. */
  (function () {
    var WINS = [
      { who: 'sg', agent: 'claude-code', area: 'perception', x: 900, y: 214, w: 330, h: 250, rib: 0,
        ev: [[0, 'context: this machine only', ''], [7.3, 'claim T-sg-15', 'f-sq f-d'], [8.5, 'contested: mr claimed it too', 'f-sq f-am']] },
      { who: 'mr', agent: 'codex', area: 'controls', x: 1270, y: 160, w: 300, h: 250, rib: 2,
        ev: [[0, 'context: this machine only', ''], [7.55, 'claim T-sg-15', 'f-sq f-d'], [8.5, 'contested: sg claimed it too', 'f-sq f-am']] },
      { who: 'cl', agent: 'human', area: 'firmware &middot; rig B', x: 1600, y: 336, w: 260, h: 250, rib: 1,
        ev: [[0, 'context: this bench only', ''], [8.0, 'CAN fix known only by hand', 'f-sq f-am']] },
      { who: 'rl', agent: 'human', area: 'research', x: 1030, y: 548, w: 330, h: 250, rib: 3,
        ev: [[0, 'context: this machine only', ''], [8.8, 'goal.md rewritten after test day', 'f-sq f-d']] },
      { who: 'ak', agent: 'cursor', area: 'planning', x: 1440, y: 640, w: 330, h: 250, rib: 4,
        ev: [[0, 'context: this machine only', ''], [9.4, 'still working to the old goal', 'f-sq f-ox']] }
    ];
    R.define('teams', {
      duration: 49,
      paper: [12.15, 0.95, 19.55, 0.9],
      geom: { NU: 150, NV: 40, NC: 7 },
      ribbons: [
        { phi0: 0.00, span: 4.30, r0: 0.62, r1: 0.30, h0: 0.02, h1: 0.40, f: 0.80, ph: 0.0, tilt: 0.38, roll: 0.12, w0: 0.46, tw: 2.2, th0: 0.30, taper: 0.55 },
        { phi0: 1.35, span: 3.70, r0: 0.80, r1: 0.18, h0: -0.10, h1: 0.34, f: 1.10, ph: 1.4, tilt: -0.55, roll: 0.30, w0: 0.40, tw: -1.8, th0: 1.20, taper: 0.45, blue: true },
        { phi0: 2.60, span: 4.60, r0: 0.50, r1: 0.38, h0: 0.14, h1: 0.30, f: 0.60, ph: 2.1, tilt: 0.92, roll: -0.40, w0: 0.36, tw: 2.6, th0: 2.00, taper: 0.60 },
        { phi0: 3.90, span: 3.30, r0: 0.70, r1: 0.25, h0: -0.20, h1: 0.44, f: 1.30, ph: 0.7, tilt: -0.22, roll: 0.72, w0: 0.42, tw: 1.6, th0: 0.80, taper: 0.50 },
        { phi0: 5.10, span: 3.90, r0: 0.58, r1: 0.30, h0: 0.00, h1: 0.38, f: 0.90, ph: 3.0, tilt: 0.60, roll: -0.80, w0: 0.38, tw: -2.2, th0: 2.60, taper: 0.55 }
      ],
      chapters: [
        { t: 0, n: 'The boundary' }, { t: 6.5, n: 'Fragments' }, { t: 12.5, n: 'The shared brain' }, { t: 19.8, n: 'On disk' },
        { t: 27.4, n: 'Status' }, { t: 35.1, n: 'The learning loop' }, { t: 41.0, n: 'No server' }
      ],
      init: function (A) {
        var box = A.el('wins');
        WINS.forEach(function (w, i) {
          var el = document.createElement('div');
          el.className = 'f-win';
          el.style.cssText = 'left:' + w.x + 'px;top:' + w.y + 'px;width:' + w.w + 'px;height:' + w.h + 'px';
          el.setAttribute('data-ti', (0.35 + i * 0.06).toFixed(2));
          el.setAttribute('data-to', (11.35 + i * 0.05).toFixed(2));
          el.setAttribute('data-fx', 'blur');
          el.innerHTML = '<div class="f-wh"><span class="f-lbl">' + w.who + ' &middot; ' + w.agent + '</span><span class="f-lbl f-t4">' + w.area + '</span></div><div class="f-wf">' +
            w.ev.map(function (e, k) { return '<div data-ev="' + k + '">' + (e[2] ? '<i class="' + e[2] + '"></i>' : '') + e[1] + '</div>'; }).join('') + '</div>';
          box.appendChild(el);
          w.foot = el.querySelectorAll('[data-ev]');
        });
        this.mk = A.mark(960, 440, 4.2, A.markAssign());
        this.dot = A.el('ctlDot'); this.st1 = A.el('st1'); this.st2 = A.el('st2'); this.trav = A.el('trav');
        this.nodes = ['n1', 'n2', 'n3', 'n4'].map(A.el);
        this.lines = [].slice.call(A.root.querySelectorAll('.f-arr .f-line'));
      },
      state: function (t, S, A) {
        var E = A.E, pr = A.pr, cl = A.cl, lerp = A.lerp;
        var p = A.kf([[0, 1570, 540, 232], [19.5, 1570, 540, 232], [20.9, 1390, 548, 322], [27.2, 1390, 548, 322], [34.9, 1440, 390, 190],
                      [41.0, 1440, 390, 190], [42.2, 1400, 520, 250]], t);
        S.cx = p[0]; S.cy = p[1]; S.s = p[2];
        S.yaw = 0.9 + t * 0.16 + Math.sin(t * 0.37) * 0.04;
        var frag = 1 - pr(t, 11.7, 1.9, E.emph);
        S.alpha = cl(1 - pr(t, 27.3, 0.7, E.inout) + pr(t, 35.0, 0.9, E.out));
        var P = [[22.9, 0], [23.3, 2], [23.7, 1], [24.1, 3], [39.6, 1], [39.72, 1]];
        for (var q = 0; q < P.length; q++) {
          var d = t - P[q][0];
          if (d > 0 && d < 1.2) S.pulse[P[q][1]] = Math.max(S.pulse[P[q][1]], d < 0.14 ? d / 0.14 : 1 - E.out((d - 0.14) / 1.06));
        }
        var order = [0, 2, 3, 4, 1];
        for (var r = 0; r < 5; r++) {
          S.reveal[r] = pr(t, 0.7 + r * 0.16, 1.5, E.out);
          var w = null; for (var k = 0; k < WINS.length; k++) if (WINS[k].rib === r) w = WINS[k];
          if (frag > 0) S.place[r] = { k: E.emph(cl(frag * 1.25 - r * 0.06)), cx: w.x + w.w / 2, cy: w.y + 36 + (w.h - 66) / 2, s: 70,
            yaw: t * (0.32 + 0.09 * r) * (r % 2 ? -1 : 1) + r * 1.3, pitch: 0.3 };
          var mk = pr(t, 44.2 + order.indexOf(r) * 0.13, 1.6, E.emph);
          if (mk > 0) S.target[r] = { k: mk, def: this.mk };
        }
        S.blueMix = 1 - pr(t, 45.2, 1.0, E.inout);
        void lerp;
      },
      onFrame: function (t, A) {
        var pr = A.pr, E = A.E, lerp = A.lerp, cl = A.cl;
        WINS.forEach(function (w) {
          for (var k = 0; k < w.foot.length; k++) {
            var s0 = w.ev[k][0], s1 = k + 1 < w.ev.length ? w.ev[k + 1][0] : 1e9;
            var pin = k === 0 ? 1 : pr(t, s0, 0.3, E.edify), pout = pr(t, s1, 0.2, E.inout), st = w.foot[k].style;
            st.opacity = (pin * (1 - pout)).toFixed(3);
            st.transform = 'translateY(' + ((1 - pin) * 8 - pout * 8).toFixed(2) + 'px)';
          }
        });
        var dp = pr(t, 16.3, A.D.scene, E.emph);
        this.dot.style.left = lerp(0, 205, dp).toFixed(2) + 'px';
        this.st1.style.color = dp < 0.5 ? '#2C6FD6' : '';
        this.st2.style.color = dp >= 0.5 ? '#2C6FD6' : '';
        var stops = [[250, 36.9], [754, 37.7], [1218, 38.5], [1658, 39.4]], tp = 0, tx = stops[0][0];
        if (t >= 36.9 && t < 40.7) {
          for (var s = 0; s < stops.length - 1; s++) if (t >= stops[s][1]) tx = lerp(stops[s][0], stops[s + 1][0], E.edify(cl((t - stops[s][1] - 0.2) / 0.55)));
          tp = pr(t, 36.9, 0.2, E.edify) * (1 - pr(t, 40.5, 0.2, E.inout));
        }
        this.trav.style.opacity = tp.toFixed(3);
        this.trav.style.transform = 'translate(' + (tx - 4).toFixed(1) + 'px, 695.5px)';
        this.nodes.forEach(function (el, k) {
          var lit = pr(t, stops[k][1] + (k ? 0.72 : 0.1), 0.3, E.edify);
          el.querySelector('.f-m').style.color = lit > 0.5 ? '#E8ECF2' : '';
          el.querySelector('.f-edge').style.opacity = (k === 3 ? lit : lit * (1 - pr(t, stops[k][1] + 1.3, 0.4, E.inout))).toFixed(3);
        });
        this.lines.forEach(function (l, k) { l.style.transform = 'scaleX(' + pr(t, 36.8 + k * 0.15, A.D.el, E.edify).toFixed(3) + ')'; });
      }
    });
  })();
})();
