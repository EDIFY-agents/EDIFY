/* EDIFY reels: the page films, played by the scroll.
   A port of assets/motion/engine/edify-film.js. Every frame of a film is a pure function of t,
   so instead of a video the page draws the film live and the scroll sets t. The film's words are
   the page's own words, in the DOM, shown once.

     <section class="reel" data-reel="home" data-from="7" data-to="43" data-intro="9" data-pace="16">
       <div class="reel-pin"><div class="reel-paper"></div>
         <div class="reel-frame"><canvas class="reel-cv"></canvas>
           <div class="reel-ui"><div class="rc" data-ch="0"> …cues… </div> …</div></div></div>
     </section>

   Wide screens pin the frame under the header and scrub t through the section's height. Narrow
   screens and reduced motion let the chapters flow as ordinary blocks over a sticky canvas that
   follows the object. Without JavaScript the chapters read as plain blocks.
   Film configs register with EdReel.define(name, config); see reels.js. */
(function () {
  'use strict';

  var W = 1920, H = 1080, HEADER = 66;
  var doc = document;

  /* ------------------------------------------------------------------ easing (tokens) */
  function bez(x1, y1, x2, y2) {
    function a(p1, p2) { return 1 - 3 * p2 + 3 * p1; } function b(p1, p2) { return 3 * p2 - 6 * p1; } function c(p1) { return 3 * p1; }
    function f(t, p1, p2) { return ((a(p1, p2) * t + b(p1, p2)) * t + c(p1)) * t; }
    function d(t, p1, p2) { return 3 * a(p1, p2) * t * t + 2 * b(p1, p2) * t + c(p1); }
    return function (x) {
      if (x <= 0) return 0; if (x >= 1) return 1;
      var t = x;
      for (var i = 0; i < 8; i++) { var e = f(t, x1, x2) - x, s = d(t, x1, x2); if (Math.abs(e) < 1e-6 || Math.abs(s) < 1e-6) break; t -= e / s; }
      if (t < 0 || t > 1) { var lo = 0, hi = 1; t = x; for (var j = 0; j < 30; j++) { var v = f(t, x1, x2); if (v < x) lo = t; else hi = t; t = (lo + hi) / 2; } }
      return f(t, y1, y2);
    };
  }
  var E = {
    out: bez(0.16, 1, 0.3, 1), inout: bez(0.65, 0, 0.35, 1), emph: bez(0.22, 1, 0.36, 1), edify: bez(0.2, 0.8, 0.2, 1),
    lin: function (x) { return x < 0 ? 0 : x > 1 ? 1 : x; }
  };
  var D = { micro: 0.14, el: 0.42, section: 0.9, scene: 1.4 };
  function cl(x) { return x < 0 ? 0 : x > 1 ? 1 : x; }
  function pr(t, t0, dur, ease) { return (ease || E.lin)(cl((t - t0) / dur)); }
  function lerp(a, b, k) { return a + (b - a) * k; }
  function kf(K, t) {
    if (t <= K[0][0]) return K[0].slice(1);
    for (var k = 0; k < K.length - 1; k++) {
      if (t <= K[k + 1][0]) {
        var e = E.emph(cl((t - K[k][0]) / (K[k + 1][0] - K[k][0])));
        return K[k].slice(1).map(function (v, i) { return lerp(v, K[k + 1][i + 1], e); });
      }
    }
    return K[K.length - 1].slice(1);
  }

  /* ------------------------------------------------------------------ the object: hairlines only */
  function Engine(C) {
    var G = C.geom || {}, NU = G.NU || 150, NV = G.NV || 40, NC = G.NC || 7;
    var RIB = C.ribbons, NR = RIB.length;
    var LOC = new Float32Array(NR * NU * NV * 3);
    for (var r = 0; r < NR; r++) {
      var p = RIB[r];
      var ct = Math.cos(p.tilt || 0), st = Math.sin(p.tilt || 0), cr = Math.cos(p.roll || 0), sr = Math.sin(p.roll || 0);
      for (var j = 0; j < NU; j++) {
        var u = j / (NU - 1);
        var phi = p.phi0 + p.span * u, rad = p.r0 + p.r1 * Math.sin(Math.PI * u);
        var cy = (p.h0 || 0) + p.h1 * Math.sin(2 * Math.PI * p.f * u + p.ph);
        var cx = rad * Math.cos(phi), cz = rad * Math.sin(phi);
        var rx = Math.cos(phi), rz = Math.sin(phi), th = p.th0 + p.tw * u;
        var w = p.w0 * Math.pow(Math.max(0, Math.sin(Math.PI * u)), p.taper == null ? 0.5 : p.taper) + (p.wmin || 0);
        var ax = Math.cos(th) * rx, ay = Math.sin(th), az = Math.cos(th) * rz;
        for (var i = 0; i < NV; i++) {
          var v = (i / (NV - 1)) * 2 - 1;
          var x = cx + v * w * ax, y = cy + v * w * ay, z = cz + v * w * az;
          var y1 = y * ct - z * st, z1 = y * st + z * ct, x2 = x * cr - y1 * sr, y2 = x * sr + y1 * cr;
          var o = ((r * NU + j) * NV + i) * 3;
          LOC[o] = x2 + (p.ox || 0); LOC[o + 1] = y2 + (p.oy || 0); LOC[o + 2] = z1 + (p.oz || 0);
        }
      }
    }
    var SCR = new Float32Array(NR * NU * NV * 3), TOP = new Uint8Array(NR * NU * NV);
    var tA = new Float32Array(3), tB = new Float32Array(3);
    function rigid(x, y, z, yaw, pitch, cx, cy, s, out) {
      var c = Math.cos(yaw), sn = Math.sin(yaw), x1 = x * c + z * sn, z1 = -x * sn + z * c;
      var cp = Math.cos(pitch), sp = Math.sin(pitch), y2 = y * cp - z1 * sp, z2 = y * sp + z1 * cp;
      var f = 3.6 / (3.6 - z2);
      out[0] = cx + x1 * s * f; out[1] = cy - y2 * s * f; out[2] = z2 * s;
    }

    /* flat targets: a polyline with a stroke width, drawn as mitred threads */
    function target(def) {
      if (def._th) return def;
      var P = def.pts, n = P.length, closed = !!def.closed, nseg = closed ? n : n - 1, T = def.T || 13;
      function dir(k) { var A = P[k], B = P[(k + 1) % n], dx = B[0] - A[0], dy = B[1] - A[1], L = Math.hypot(dx, dy); return [dx / L, dy / L]; }
      function off(k, d) { var u = dir(k); return [P[k][0] - u[1] * d, P[k][1] + u[0] * d, u]; }
      function hit(k1, k2, d) {
        var a = off(k1, d), b = off(k2, d), u1 = a[2], u2 = b[2], den = u1[0] * u2[1] - u1[1] * u2[0];
        if (Math.abs(den) < 1e-9) return [b[0], b[1]];
        var tt = ((b[0] - a[0]) * u2[1] - (b[1] - a[1]) * u2[0]) / den;
        return [a[0] + u1[0] * tt, a[1] + u1[1] * tt];
      }
      def._th = [];
      for (var q = 0; q < T; q++) {
        var d = (T === 1 ? 0 : (q / (T - 1) * 2 - 1)) * def.w * 0.5, V = [];
        for (var k = 0; k < n; k++) {
          if (!closed && k === 0) { var o0 = off(0, d); V.push([o0[0], o0[1]]); }
          else if (!closed && k === n - 1) { var u = dir(n - 2); V.push([P[k][0] - u[1] * d, P[k][1] + u[0] * d]); }
          else V.push(hit((k - 1 + n) % n, k, d));
        }
        if (closed) V.push(V[0]);
        var cum = [0];
        for (var s = 0; s < nseg; s++) cum.push(cum[s] + Math.hypot(V[s + 1][0] - V[s][0], V[s + 1][1] - V[s][1]));
        def._th.push({ V: V, cum: cum });
      }
      def._nseg = nseg;
      return def;
    }
    var TP = [0, 0, 0];
    function targetPoint(def, r, u, i) {
      var a = def.assign ? def.assign[r] : null, s0 = a ? a.s0 : 0, s1 = a ? a.s1 : def._nseg, slot = a ? a.slot : 0, ns = a ? a.n : 1;
      var T = def._th.length, q = T === 1 ? 0 : Math.round((slot * NV + i) / (ns * NV - 1) * (T - 1));
      var th = def._th[q], cum = th.cum, l = lerp(cum[s0], cum[s1], u), k = s0;
      while (k < s1 - 1 && cum[k + 1] < l) k++;
      var seg = cum[k + 1] - cum[k], f = seg > 0 ? (l - cum[k]) / seg : 0;
      TP[0] = lerp(th.V[k][0], th.V[k + 1][0], f); TP[1] = lerp(th.V[k][1], th.V[k + 1][1], f);
      TP[2] = def.top == null ? 0 : (def.top === k || (def.top.indexOf && def.top.indexOf(k) >= 0)) ? 1 : 0;
      return TP;
    }
    var MP = [[6, 28], [44, 6], [66, 94], [30, 74], [94, 52]];
    function mark(mx, my, ms, assign) {
      function X(p) { return [mx + (p[0] - 50) * ms, my + (p[1] - 50) * ms]; }
      return target({ pts: MP.map(X), closed: true, w: 9 * ms, T: 13, top: 1, assign: assign, tone: 0.93,
        knock: [X([50.5, 32]).concat(X([54.9, 49.4])), X([56.4, 55.5]).concat(X([60.7, 72.9]))], kw: 15 * ms });
    }
    function markAssign() {
      var A = [];
      if (NR <= 5) {
        var b = [0]; for (var r = 1; r <= NR; r++) b.push(Math.round(r * 5 / NR));
        for (var r2 = 0; r2 < NR; r2++) A.push({ s0: b[r2], s1: b[r2 + 1], slot: 0, n: 1 });
      } else {
        var per = [0, 0, 0, 0, 0]; for (var r3 = 0; r3 < NR; r3++) per[r3 % 5]++;
        for (var r4 = 0; r4 < NR; r4++) A.push({ s0: r4 % 5, s1: r4 % 5 + 1, slot: Math.floor(r4 / 5), n: per[r4 % 5] });
      }
      return A;
    }

    function newState(t) {
      var S = { alpha: 1, reveal: [], pulse: [], color: [], place: [], target: [], jitter: 0, jt: t, blueMix: 1,
        cx: 1330, cy: 560, s: 360, yaw: 0.9 + t * 0.16, pitch: 0.34 };
      for (var r = 0; r < NR; r++) { S.reveal.push(1); S.pulse.push(0); S.color.push(null); S.place.push(null); S.target.push(null); }
      return S;
    }

    function computeScreen(S) {
      for (var r = 0; r < NR; r++) {
        var pl = S.place[r], tg = S.target[r], tk = tg ? tg.k : 0, def = tg ? tg.def : null, jit = (S.jitter || 0) + ((pl && pl.jitter) || 0);
        for (var j = 0; j < NU; j++) {
          var u = j / (NU - 1), jx = 0, jy = 0;
          if (jit > 0) { jy = jit * 0.09 * Math.sin(u * 11 + S.jt * 5.1 + r * 1.7); jx = jit * 0.07 * Math.cos(u * 8 - S.jt * 3.7 + r); }
          for (var i = 0; i < NV; i++) {
            var li = (r * NU + j) * NV + i, o = li * 3;
            var x = LOC[o] + jx, y = LOC[o + 1] + jy, z = LOC[o + 2];
            rigid(x, y, z, S.yaw, S.pitch, S.cx, S.cy, S.s, tA);
            var X = tA[0], Y = tA[1], Z = tA[2];
            if (pl && pl.k > 0) {
              rigid(x, y, z, pl.yaw, pl.pitch == null ? 0.3 : pl.pitch, pl.cx, pl.cy, pl.s, tB);
              X = lerp(X, tB[0], pl.k); Y = lerp(Y, tB[1], pl.k); Z = lerp(Z, tB[2], pl.k);
            }
            var top = 0;
            if (tk > 0) {
              var P = targetPoint(def, r, u, i), px = P[0], py = P[1];
              top = P[2];
              if (tg.def2 && tg.m > 0) {
                var P2 = targetPoint(tg.def2, r, u, i);
                px = lerp(px, P2[0], tg.m); py = lerp(py, P2[1], tg.m); if (tg.m > 0.5) top = P2[2];
              }
              X = lerp(X, px, tk); Y = lerp(Y, py, tk); Z = lerp(Z, 0, tk);
            }
            SCR[o] = X; SCR[o + 1] = Y; SCR[o + 2] = Z; TOP[li] = top;
          }
        }
      }
    }

    /* shading: two-sided diffuse plus a tight specular band, quantised to 8 hairline tones */
    var LV = [-0.42, 0.58, 0.70]; (function () { var n = Math.hypot(LV[0], LV[1], LV[2]); LV = LV.map(function (v) { return v / n; }); })();
    var HV = (function () { var h = [LV[0], LV[1], LV[2] + 1], n = Math.hypot(h[0], h[1], h[2]); return h.map(function (v) { return v / n; }); })();
    var NL = 8, NQ = NR * NU * NC;
    var QZ = new Float64Array(NQ), QL = new Uint8Array(NQ), QORD = new Uint32Array(NQ);
    function buildQuads(S) {
      var nQ = 0;
      for (var r = 0; r < NR; r++) {
        var lim = Math.floor(S.reveal[r] * (NU - 1)), pul = S.pulse[r], tg = S.target[r], tk = tg ? tg.k : 0, tone = tg && tg.def.tone != null ? tg.def.tone : 0.93;
        for (var j = 0; j < lim; j++) {
          for (var c = 0; c < NC; c++) {
            var i0 = Math.round(c * (NV - 1) / NC), i1 = Math.round((c + 1) * (NV - 1) / NC);
            var a0 = ((r * NU + j) * NV + i0) * 3, a1 = ((r * NU + j + 1) * NV + i0) * 3, b1 = ((r * NU + j + 1) * NV + i1) * 3, b0 = ((r * NU + j) * NV + i1) * 3;
            var ux = SCR[a1] - SCR[a0], uy = -(SCR[a1 + 1] - SCR[a0 + 1]), uz = SCR[a1 + 2] - SCR[a0 + 2];
            var vx = SCR[b0] - SCR[a0], vy = -(SCR[b0 + 1] - SCR[a0 + 1]), vz = SCR[b0 + 2] - SCR[a0 + 2];
            var nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx, nn = Math.hypot(nx, ny, nz) || 1;
            nx /= nn; ny /= nn; nz /= nn;
            var dif = Math.abs(nx * LV[0] + ny * LV[1] + nz * LV[2]), spc = Math.pow(Math.abs(nx * HV[0] + ny * HV[1] + nz * HV[2]), 22);
            var s = lerp(0.16 + 0.56 * dif + 0.95 * spc, tone, tk) + pul * 0.7;
            var q = (r * NU + j) * NC + c;
            QL[q] = Math.min(NL - 1, Math.max(0, Math.floor(s * NL)));
            QZ[q] = (SCR[a0 + 2] + SCR[a1 + 2] + SCR[b1 + 2] + SCR[b0 + 2]) * 0.25 + (TOP[(r * NU + j) * NV + i0] ? 4000 * tk : 0);
            QORD[nQ++] = q;
          }
        }
      }
      var ord = QORD.subarray(0, nQ);
      ord.sort(function (a, b) { return QZ[a] - QZ[b]; });
      return ord;
    }
    var STY = {};
    function styles(pal, key) {
      var id = pal + key; if (STY[id]) return STY[id];
      var out = [];
      for (var l = 0; l < NL; l++) {
        var k = l / (NL - 1), v;
        if (pal === 'paper') {
          if (key === 'b') v = 'rgba(44,111,214,' + (0.98 - 0.62 * Math.pow(k, 1.2)).toFixed(3) + ')';
          else if (key === 'o') v = 'rgba(190,72,58,' + (0.98 - 0.6 * Math.pow(k, 1.2)).toFixed(3) + ')';
          else v = 'rgba(20,22,26,' + (0.94 - 0.84 * Math.pow(k, 1.25)).toFixed(3) + ')';
        } else if (key === 'b') v = 'rgba(' + Math.round(lerp(44, 90, k)) + ',' + Math.round(lerp(111, 147, k)) + ',' + Math.round(lerp(214, 245, k)) + ',' + (0.5 + 0.5 * k).toFixed(3) + ')';
        else if (key === 'o') v = 'rgba(' + Math.round(lerp(190, 226, k)) + ',' + Math.round(lerp(72, 104, k)) + ',' + Math.round(lerp(58, 86, k)) + ',' + (0.55 + 0.45 * k).toFixed(3) + ')';
        else v = 'rgba(232,236,242,' + (0.10 + 0.90 * Math.pow(k, 1.15)).toFixed(3) + ')';
        out.push(v);
      }
      return (STY[id] = out);
    }
    function drawObject(ctx, ord, pal, S, lwk) {
      var bg = pal === 'paper' ? '#F2F1EE' : '#07090C';
      ctx.save(); ctx.globalAlpha = S.alpha; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; ctx.fillStyle = bg;
      var knocked = {}, RUN = 14, lw = (pal === 'paper' ? 1.0 : 1.05) * lwk;
      for (var n0 = 0; n0 < ord.length; n0 += RUN) {
        var fill = new Path2D(), lines = {}, n1 = Math.min(ord.length, n0 + RUN);
        for (var n = n0; n < n1; n++) {
          var q = ord[n], c = q % NC, rj = (q - c) / NC, j = rj % NU, r = (rj - j) / NU;
          var i0 = Math.round(c * (NV - 1) / NC), i1 = Math.round((c + 1) * (NV - 1) / NC);
          var tg = S.target[r];
          var kd = tg ? (tg.def2 && tg.m > 0.5 ? tg.def2 : tg.def) : null;
          if (tg && tg.k > 0 && kd.knock && TOP[(r * NU + j) * NV + i0] && !knocked[r]) {
            knocked[r] = 1;
            if (!kd._kn) {
              kd._kn = 1;
              var ka = Math.pow(tg.k, 3) * (kd === tg.def2 && !tg.def.knock ? tg.m : 1);
              ctx.save(); ctx.globalAlpha = S.alpha * ka; ctx.strokeStyle = bg; ctx.lineWidth = kd.kw; ctx.lineCap = 'butt';
              ctx.beginPath(); kd.knock.forEach(function (k) { ctx.moveTo(k[0], k[1]); ctx.lineTo(k[2], k[3]); }); ctx.stroke(); ctx.restore();
            }
          }
          var a0 = ((r * NU + j) * NV + i0) * 3, a1 = ((r * NU + j + 1) * NV + i0) * 3, b1 = ((r * NU + j + 1) * NV + i1) * 3, b0 = ((r * NU + j) * NV + i1) * 3;
          if (!(tg && tg.k > 0.9)) { fill.moveTo(SCR[a0], SCR[a0 + 1]); fill.lineTo(SCR[a1], SCR[a1 + 1]); fill.lineTo(SCR[b1], SCR[b1 + 1]); fill.lineTo(SCR[b0], SCR[b0 + 1]); fill.closePath(); }
          var base = S.color[r] || (RIB[r].blue && S.blueMix > 0.5 ? 'b' : 'w'), bs = RIB[r].blueStrands;
          for (var i = i0; i <= i1; i++) {
            if (i === i1 && c < NC - 1) continue;
            var key = (bs && S.blueMix > 0.5 && i >= bs[0] && i <= bs[1] ? 'b' : base) + QL[q];
            var lp = lines[key] || (lines[key] = new Path2D());
            var p0 = ((r * NU + j) * NV + i) * 3, p1 = ((r * NU + j + 1) * NV + i) * 3;
            lp.moveTo(SCR[p0], SCR[p0 + 1]); lp.lineTo(SCR[p1], SCR[p1 + 1]);
          }
        }
        ctx.strokeStyle = bg; ctx.lineWidth = 1.1 * lwk; ctx.fill(fill); ctx.stroke(fill);
        ctx.lineWidth = lw;
        for (var k in lines) { ctx.strokeStyle = styles(pal, k[0])[+k.slice(1)]; ctx.stroke(lines[k]); }
      }
      for (var r2 = 0; r2 < NR; r2++) if (S.target[r2]) { S.target[r2].def._kn = 0; if (S.target[r2].def2) S.target[r2].def2._kn = 0; }
      ctx.restore();
    }

    return { NR: NR, target: target, mark: mark, markAssign: markAssign, newState: newState,
      computeScreen: computeScreen, buildQuads: buildQuads, drawObject: drawObject };
  }

  /* ------------------------------------------------------------------ cues: the film's words, in the page */
  /* A cue enters once t passes its time and leaves once t passes its out time, each at its own
     pace, so a line is never left half-drawn when the scroll stops. The object is the part the
     scroll scrubs. */
  function collectCues(root) {
    return [].slice.call(root.querySelectorAll('[data-ti]')).filter(function (el) { return !el.classList.contains('f-x'); }).map(function (el) {
      var c = { el: el, tin: parseFloat(el.dataset.ti), tout: el.dataset.to ? parseFloat(el.dataset.to) : 1e9,
        fx: el.dataset.fx || 'fade', st: el.dataset.st ? parseFloat(el.dataset.st) : 0.11, ease: E[el.dataset.ease || 'edify'], a: 0, o: 0, dirty: true };
      if (c.fx === 'ladder') c.lines = [].slice.call(el.querySelectorAll(':scope > .ln > span'));
      c.strikes = [].slice.call(el.querySelectorAll('.f-x')).map(function (x) { return { el: x, dt: parseFloat(x.dataset.ti) - c.tin }; });
      c.amax = 0.8 + (c.lines ? c.lines.length * c.st : 0) + c.strikes.reduce(function (m, s) { return Math.max(m, s.dt + 0.5); }, 0);
      return c;
    });
  }
  function clearCue(c) {
    var el = c.el;
    el.style.opacity = el.style.transform = el.style.filter = el.style.clipPath = '';
    (c.lines || []).forEach(function (l) { l.style.transform = l.style.opacity = ''; });
    c.strikes.forEach(function (s) { s.el.style.transform = 'scaleX(1)'; });
  }
  function stepCue(c, t, dt) {
    var a = c.a, o = c.o;
    c.a = t >= c.tin ? Math.min(c.amax, a + dt) : Math.max(0, a - dt * 2.2);
    c.o = t > c.tout ? Math.min(0.9, o + dt) : Math.max(0, o - dt * 2.2);
    if (c.a === a && c.o === o && !c.dirty) return;
    c.dirty = false;
    var el = c.el, tt = c.tin + c.a, of = pr(c.o, 0, 0.36, E.inout);
    if (c.fx === 'ladder') {
      el.style.opacity = c.a > 0 ? (1 - of).toFixed(4) : '0';
      for (var i = 0; i < c.lines.length; i++) {
        var p = pr(tt, c.tin + i * c.st, D.el, c.ease), q = pr(c.o, i * 0.04, 0.36, E.inout), s = c.lines[i].style;
        s.transform = 'translateY(' + ((1 - p) * 0.42 - q * 0.22).toFixed(4) + 'em)';
        s.opacity = (p * (1 - q)).toFixed(4);
      }
      for (var k = 0; k < c.strikes.length; k++) {
        var g = pr(c.a, c.strikes[k].dt, D.el, E.edify);
        c.strikes[k].el.style.transform = 'scaleX(' + g.toFixed(4) + ')';
        if (c.lines[k]) c.lines[k].style.color = g > 0 ? 'rgba(232,236,242,' + (1 - 0.62 * g).toFixed(3) + ')' : '';
      }
    } else if (c.fx === 'blur') {
      var pb = pr(tt, c.tin, D.el + 0.18, E.out);
      el.style.opacity = (pb * (1 - of)).toFixed(4);
      el.style.filter = pb < 1 ? 'blur(' + ((1 - pb) * 14).toFixed(2) + 'px)' : 'none';
      el.style.transform = 'translateY(' + ((1 - pb) * 28).toFixed(2) + 'px)';
    } else if (c.fx === 'wipe') {
      var pw = pr(tt, c.tin, 0.32, E.edify);
      el.style.clipPath = 'inset(0 ' + ((1 - pw) * 100).toFixed(2) + '% 0 0)';
      el.style.opacity = c.a > 0 ? (1 - of).toFixed(4) : '0';
    } else if (c.fx === 'rule') {
      var pg = pr(tt, c.tin, D.section, E.edify);
      el.style.transform = 'scaleX(' + pg.toFixed(4) + ')';
      el.style.opacity = (1 - of).toFixed(4);
    } else {
      var pf = pr(tt, c.tin, D.el, E.edify);
      el.style.opacity = (pf * (1 - of)).toFixed(4);
      el.style.transform = 'translateY(' + ((1 - pf) * 10).toFixed(2) + 'px)';
    }
  }

  /* ------------------------------------------------------------------ a reel on the page */
  var REG = {};
  var reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion:reduce)').matches;
  var pad = function (n) { return (n < 10 ? '0' : '') + n; };
  var esc = function (x) { return String(x).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };

  function Reel(root, C) {
    var R = this;
    this.root = root; this.C = C;
    var ds = root.dataset;
    this.from = parseFloat(ds.from || '0');
    this.to = parseFloat(ds.to || String(C.duration));
    this.intro = ds.intro ? parseFloat(ds.intro) : this.from;
    this.pace = parseFloat(ds.pace || '15');                       /* vh of scroll per film second */
    this.pin = root.querySelector('.reel-pin');
    this.frame = root.querySelector('.reel-frame');
    this.cv = root.querySelector('.reel-cv');
    this.ui = root.querySelector('.reel-ui');
    this.paperEl = root.querySelector('.reel-paper');
    this.ctx = this.cv.getContext('2d');
    this.blocks = [].slice.call(root.querySelectorAll('.rc'));
    this.chapters = (C.chapters || [{ t: 0, n: '' }]).filter(function (c, i, a) { var nx = a[i + 1]; return !nx || nx.t > R.from; });
    this.eng = Engine(C);
    this.A = { E: E, D: D, pr: pr, cl: cl, lerp: lerp, kf: kf, W: W, H: H, NR: this.eng.NR,
      target: this.eng.target, mark: this.eng.mark, markAssign: this.eng.markAssign,
      el: function (id) { return root.querySelector('#r-' + id); }, root: root };
    if (C.init) C.init(this.A);
    this.cues = collectCues(this.ui);
    this.t = this.from; this.target = this.from; this.drawnT = -1; this.clock = 0;
    this.cam = null; this.last = 0; this.on = false; this.introAt = 0; this.userScrolled = false;
    this.buildHud();
    this.layout();
    new IntersectionObserver(function (es) { R.on = es[0].isIntersecting; if (R.on) R.wake(); }, { rootMargin: '200px 0px' }).observe(root);
  }

  Reel.prototype.buildHud = function () {
    var R = this, ch = this.chapters, span = this.to - this.from;
    var hud = doc.createElement('div');
    hud.className = 'reel-hud';
    hud.innerHTML = '<span class="n"></span><span class="c"></span><span class="tk">' + ch.map(function (c, i) {
      var a = Math.max(c.t, R.from), z = i + 1 < ch.length ? ch[i + 1].t : R.to;
      return '<button type="button" style="flex:' + Math.max(0.5, z - a).toFixed(2) + '" aria-label="Chapter ' + (i + 1) + ', ' + esc(c.n) + '"><i></i></button>';
    }).join('') + '</span><span class="hint" aria-hidden="true">scroll</span>';
    this.pin.appendChild(hud);
    this.hud = { el: hud, n: hud.querySelector('.n'), c: hud.querySelector('.c'), segs: [].slice.call(hud.querySelectorAll('.tk button')), cur: -1 };
    this.hud.segs.forEach(function (b, i) {
      b.addEventListener('click', function () { R.seek(Math.max(ch[i].t, R.from) + 0.05); });
    });
    this.span = span;
  };

  /* scroll position of film time t */
  Reel.prototype.seek = function (t) {
    var y;
    if (this.mode === 'pin') {
      var top = this.root.getBoundingClientRect().top + window.scrollY - HEADER;
      y = top + (t - this.from) / this.span * (this.root.offsetHeight - this.pinH);
    } else {
      var b = this.blockAt(t);
      if (!b) return;
      var r = b.el.getBoundingClientRect();
      y = r.top + window.scrollY - window.innerHeight * 0.1;
    }
    window.scrollTo({ top: Math.max(0, y), behavior: reduced ? 'auto' : 'smooth' });
  };

  Reel.prototype.blockAt = function (t) {
    var list = this.flowBlocks || [];
    for (var i = list.length - 1; i >= 0; i--) if (t >= list[i].t0 - 1e-3) return list[i];
    return list[0];
  };

  Reel.prototype.layout = function () {
    var vw = window.innerWidth, vh = window.innerHeight;
    var want = (!reduced && vw >= 900 && vw / Math.max(1, vh - HEADER) >= 1.15) ? 'pin' : 'flow';
    if (want !== this.mode) {
      this.mode = want;
      this.root.classList.toggle('is-pin', want === 'pin');
      this.root.classList.toggle('is-flow', want === 'flow');
      if (want === 'pin') { this.frame.appendChild(this.ui); this.cues.forEach(function (c) { c.dirty = true; }); }
      else { this.root.appendChild(this.ui); this.cues.forEach(clearCue); }
      this.cam = null;
    }
    this.root.classList.add('is-live');
    var pw = this.pin.clientWidth, ph = this.pin.clientHeight;
    this.pinW = pw; this.pinH = ph;
    if (this.mode === 'pin') {
      this.root.style.height = Math.round(this.span * this.pace * vh / 100 + ph) + 'px';
      var k = Math.min(pw / 1920, ph / 860, 1.5);
      this.k = k; this.ox = (pw - W * k) / 2; this.oy = (ph - H * k) / 2;
      this.frame.style.transform = 'translate(' + this.ox.toFixed(2) + 'px,' + this.oy.toFixed(2) + 'px) scale(' + k.toFixed(5) + ')';
      var g = (56 * k).toFixed(3) + 'px';
      this.pin.style.backgroundSize = g + ' ' + g;
      this.pin.style.backgroundPosition = this.ox.toFixed(2) + 'px ' + this.oy.toFixed(2) + 'px';
    } else {
      this.root.style.height = '';
      this.pin.style.backgroundSize = this.pin.style.backgroundPosition = '';
      var ch = this.C.chapters || [], R = this, to = this.to;
      this.flowBlocks = this.blocks.map(function (el) {
        var i = el.dataset.ch === 'end' ? ch.length : +el.dataset.ch;
        var t0 = i >= ch.length ? Math.max(R.from, to - 3) : Math.max(R.from, ch[i].t);
        var t1 = i + 1 < ch.length ? ch[i + 1].t : to;
        if (i === ch.length - 1) { var endB = R.blocks.filter(function (b) { return b.dataset.ch === 'end'; })[0]; if (endB) t1 = Math.max(t0, to - 3); }
        return { el: el, t0: t0, t1: Math.max(t0 + 0.01, t1) };
      }).filter(function (b) { return b.t1 > R.from; });
    }
    this.sizeCanvas();
    this.drawnT = -1;
  };

  Reel.prototype.sizeCanvas = function () {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var k = this.mode === 'pin' ? this.k : Math.max(0.3, Math.min(1, this.pinW / 900));
    var s = Math.min(k * dpr, Math.sqrt(6.5e6 / (W * H)));
    this.cs = s;
    var w = Math.round(W * s), h = Math.round(H * s);
    if (this.cv.width !== w || this.cv.height !== h) { this.cv.width = w; this.cv.height = h; }
  };

  /* where the scroll puts the playhead */
  Reel.prototype.scrollT = function () {
    var r = this.root.getBoundingClientRect();
    if (this.mode === 'pin') {
      var p = cl((HEADER - r.top) / Math.max(1, r.height - this.pinH));
      return this.from + p * this.span;
    }
    var y = window.innerHeight * 0.55, list = this.flowBlocks, b = null;
    for (var i = 0; i < list.length; i++) {
      var br = list[i].el.getBoundingClientRect();
      if (br.top <= y) b = { d: list[i], r: br };
    }
    if (!b) return this.from;
    var local = cl((y - b.r.top) / Math.max(1, b.r.height));
    if (reduced) return lerp(b.d.t0, b.d.t1, 0.7);
    return lerp(b.d.t0, b.d.t1, local);
  };

  Reel.prototype.wake = function () {
    if (this.running) return;
    this.running = true; this.last = 0;
    var R = this;
    requestAnimationFrame(function step(now) {
      if (!R.on || doc.hidden) { R.running = false; return; }
      R.tick(now);
      requestAnimationFrame(step);
    });
  };

  Reel.prototype.tick = function (now) {
    var dt = this.last ? Math.min(0.1, (now - this.last) / 1000) : 0.016;
    this.last = now; this.clock += dt;
    var target = this.scrollT();
    // the first beat plays by itself once the reel is on screen, like a film starting
    var r = this.root.getBoundingClientRect();
    if (!reduced && this.mode === 'pin' && r.top < window.innerHeight * 0.6) {
      if (!this.introAt) this.introAt = now;
      var it = Math.min(this.intro, this.from + (now - this.introAt) / 1000);
      if (target < it) target = it;
    }
    this.target = target;
    var diff = target - this.t;
    if (reduced) this.t = target;
    else this.t = Math.abs(diff) < 0.002 ? target : this.t + diff * (1 - Math.exp(-dt / 0.14));
    var drift = reduced ? 0 : 0.05 * Math.sin(this.clock * 0.45);
    if (this.mode === 'pin') for (var i = 0; i < this.cues.length; i++) stepCue(this.cues[i], this.t, dt);
    if (reduced && Math.abs(this.t - this.drawnT) < 1e-4) return;
    // settled: the object only breathes, so every other frame is enough
    if (Math.abs(diff) < 0.002 && (this.n = (this.n || 0) + 1) % 2) return;
    this.render(this.t, drift);
    this.drawnT = this.t;
    this.updateHud();
  };

  Reel.prototype.paperBand = function (t) {
    var p = this.C.paper;
    if (!p || this.mode !== 'pin') return [0, 0];
    var inP = p[0] < 0 ? 1 : pr(t, p[0], p[1], E.inout), outP = pr(t, p[2], p[3], E.inout);
    return [outP * H, inP * H];
  };

  Reel.prototype.render = function (t, drift) {
    var C = this.C, A = this.A, eng = this.eng, ctx = this.ctx;
    t = Math.max(0, Math.min(C.duration - 1e-4, t));
    var pb = this.paperBand(t), pTop = pb[0], pBot = pb[1], hasPaper = pBot - pTop > 0.5;
    var S = eng.newState(t);
    C.state.call(C, t, S, A);
    S.yaw += drift;
    eng.computeScreen(S);
    var ord = eng.buildQuads(S);

    // the frame: pinned it is the film's own 1920x1080; flowing, a camera follows the object
    var s = this.cs, fx = 0, fy = 0, lwk = 1;
    if (this.mode === 'flow') {
      var pw = this.pinW, ph = this.pinH;
      var want = { k: cl(Math.min(pw * 0.86 / (S.s * 2.6), ph * 0.46 / (S.s * 2.1))) , x: S.cx, y: S.cy };
      want.k = Math.max(0.28, Math.min(0.95, want.k));
      if (!this.cam) this.cam = want;
      else { var e = reduced ? 1 : 0.08; this.cam = { k: lerp(this.cam.k, want.k, e), x: lerp(this.cam.x, want.x, e), y: lerp(this.cam.y, want.y, e) }; }
      var cam = this.cam, css = s / (Math.min(window.devicePixelRatio || 1, 2));
      // canvas covers the pin; frame point (cam.x, cam.y) lands at (pw/2, ph*0.3)
      fx = pw / 2 - cam.x * cam.k; fy = ph * 0.3 - cam.y * cam.k;
      this.frame.style.transform = 'translate(' + fx.toFixed(2) + 'px,' + fy.toFixed(2) + 'px) scale(' + cam.k.toFixed(5) + ')';
      lwk = Math.max(1, 0.6 / cam.k);
      void css;
    }
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, this.cv.width, this.cv.height);
    ctx.setTransform(s, 0, 0, s, 0, 0);
    var region = function (pal, fn) {
      ctx.save(); ctx.beginPath();
      if (pal === 'paper') ctx.rect(0, pTop, W, pBot - pTop);
      else if (hasPaper) { ctx.rect(-W, -H, 3 * W, pTop + H); ctx.rect(-W, pBot, 3 * W, 2 * H - pBot); }
      else ctx.rect(-W, -H, 3 * W, 3 * H);
      ctx.clip(); fn(); ctx.restore();
    };
    ['void', 'paper'].forEach(function (pal) {
      if (pal === 'paper' && !hasPaper) return;
      region(pal, function () {
        if (C.drawUnder) C.drawUnder(ctx, t, S, pal, A);
        if (S.alpha > 0.001) eng.drawObject(ctx, ord, pal, S, lwk);
        if (C.drawOver) C.drawOver(ctx, t, S, pal, A);
      });
    });
    if (C.onFrame) C.onFrame(t, A);

    // the paper band runs the full width of the page, not just the frame
    if (this.paperEl) {
      if (hasPaper) {
        // a band that reaches the frame's edge carries on to the pin's edge
        var top = pTop < 0.5 ? 0 : this.oy + pTop * this.k, bot = pBot > H - 0.5 ? this.pinH : this.oy + pBot * this.k, hgt = bot - top;
        this.paperEl.style.transform = 'translate3d(0,' + top.toFixed(2) + 'px,0)';
        this.paperEl.style.height = hgt.toFixed(2) + 'px';
        this.paperEl.style.backgroundPosition = this.ox.toFixed(2) + 'px ' + (this.oy - top).toFixed(2) + 'px';
        this.paperEl.style.backgroundSize = (56 * this.k).toFixed(3) + 'px ' + (56 * this.k).toFixed(3) + 'px';
        this.paperEl.style.visibility = 'visible';
      } else this.paperEl.style.visibility = 'hidden';
      this.root.classList.toggle('on-paper', hasPaper && pTop < H * 0.2 && pBot > H * 0.8);
    }
  };

  Reel.prototype.updateHud = function () {
    var h = this.hud, t = this.t, ch = this.chapters, R = this, i = 0;
    for (var k = 0; k < ch.length; k++) if (t + 0.05 >= ch[k].t) i = k;
    h.segs.forEach(function (sg, k) {
      var a = Math.max(ch[k].t, R.from), z = k + 1 < ch.length ? ch[k + 1].t : R.to;
      var f = t >= z ? 1 : t <= a ? 0 : (t - a) / (z - a);
      if (sg._f !== f) { sg._f = f; sg.style.setProperty('--f', f.toFixed(3)); }
      if (k === i) sg.setAttribute('aria-current', 'true'); else sg.removeAttribute('aria-current');
    });
    if (i !== h.cur) {
      h.cur = i;
      h.n.textContent = pad(i + 1) + ' / ' + pad(ch.length);
      h.c.textContent = ch[i].n;
      h.c.style.animation = 'none'; void h.c.offsetWidth; h.c.style.animation = '';
    }
    var moved = t > this.intro + 0.3;
    if (moved !== this._moved) { this._moved = moved; this.root.classList.toggle('moved', moved); }
    var done = t >= this.to - 0.05;
    if (done !== this._done) { this._done = done; this.root.classList.toggle('done', done); }
  };

  function start() {
    var list = [].slice.call(doc.querySelectorAll('.reel[data-reel]'));
    if (!list.length) return;
    var reels = [];
    list.forEach(function (root) {
      var C = REG[root.dataset.reel];
      if (!C || !root.querySelector('.reel-cv') || !root.querySelector('.reel-cv').getContext) return;
      try { reels.push(new Reel(root, C)); } catch (e) { if (window.console) console.error(e); }
    });
    var rt;
    window.addEventListener('resize', function () {
      clearTimeout(rt);
      rt = setTimeout(function () { reels.forEach(function (R) { R.layout(); R.wake(); }); }, 120);
    });
    doc.addEventListener('visibilitychange', function () { if (!doc.hidden) reels.forEach(function (R) { R.wake(); }); });
    window.EdReel.live = reels;
  }

  window.EdReel = { define: function (name, C) { REG[name] = C; }, E: E, pr: pr };
  var go = function () { (doc.fonts && doc.fonts.ready ? doc.fonts.ready : Promise.resolve()).then(start, start); };
  if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', go); else go();
})();
