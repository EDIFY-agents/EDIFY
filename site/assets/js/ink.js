/* EDIFY ink: flat type, a liquid mask, and the same type inflated under it.
   One WebGL2 fragment shader. Every frame is a pure function of t, so the page
   plays it live (with the pointer as one more drop of ink) and the renderer in
   assets/motion/ink/ captures the same frames into the site's clips.

   A shape (a word, the mark, a grid) is drawn once into a 2D canvas. From that
   silhouette the CPU builds two fields:
     - the signed distance to the flat shape (crisp flat type), and
     - a Poisson "pressure" field over the shape grown by G: solve lap(h) = -1
       inside, h = 0 outside. Its level sets are the balloon at every inflation,
       so a letter puffs up outward from its skeleton instead of scaling.
   The ink is a smooth union of tapered capsules, choreographed per scene on the
   CPU and warped on the GPU. Inside the ink the flat type disappears and the
   inflated type shows; how deep a point sits in the ink sets how full it is. */
(function (root) {
  'use strict';

  var TAU = Math.PI * 2;
  var MAXC = 64;

  /* ---------- colour ---------- */

  var C = {
    void: [7, 9, 12], paper: [242, 241, 238], text: [232, 236, 242], ink: [20, 22, 26],
    blue: [49, 125, 217], oxide: [196, 72, 58], plate: [20, 27, 36]
  };
  var PAL = {
    night:  { bg: C.void,  flat: C.text,  ink: C.text,  mat: 0 },
    day:    { bg: C.paper, flat: C.ink,   ink: C.ink,   mat: 0 },
    latex:  { bg: C.paper, flat: C.ink,   ink: C.ink,   mat: 1 },
    blue:   { bg: C.void,  flat: C.blue,  ink: C.blue,  mat: 1 },
    ghost:  { bg: C.void,  flat: C.plate, ink: C.void,  mat: 0 },
    oxide:  { bg: C.void,  flat: C.oxide, ink: C.void,  mat: 0 },
    chrome: { bg: C.void,  flat: C.text,  ink: C.void,  mat: 2 }
  };

  /* ---------- easing and small maths ---------- */

  var E = {
    out: function (x) { return 1 - Math.pow(1 - x, 3); },
    emph: function (x) { return x < 0.5 ? 16 * x * x * x * x * x : 1 - Math.pow(-2 * x + 2, 5) / 2; },
    expo: function (x) { return x >= 1 ? 1 : 1 - Math.pow(2, -10 * x); },
    inout: function (x) { return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; }
  };
  var cl = function (x, a, b) { return x < a ? a : x > b ? b : x; };
  var lerp = function (a, b, k) { return a + (b - a) * k; };
  var fract = function (x) { return x - Math.floor(x); };
  var smooth = function (a, b, x) { x = cl((x - a) / (b - a), 0, 1); return x * x * (3 - 2 * x); };

  /* ---------- shapes: white silhouettes drawn into a 2D canvas ---------- */

  var FONT = '"Instrument Sans", Helvetica, Arial, sans-serif';

  // lines of type fitted into a box given as fractions of the frame
  function type(lines, o) {
    o = o || {};
    lines = [].concat(lines);
    return function (ctx, W, H) {
      var box = o.box || [0.06, 0.2, 0.94, 0.8];
      var bw = (box[2] - box[0]) * W, bh = (box[3] - box[1]) * H;
      var lh = o.lh || 0.86, test = 200, track = o.track == null ? -0.04 : o.track;
      ctx.font = (o.weight || 700) + ' ' + test + 'px ' + FONT;
      if ('letterSpacing' in ctx) ctx.letterSpacing = (track * test) + 'px';
      var wmax = 0, asc = 0, dsc = 0;
      lines.forEach(function (s) {
        var m = ctx.measureText(s);
        wmax = Math.max(wmax, m.actualBoundingBoxLeft + m.actualBoundingBoxRight);
        asc = Math.max(asc, m.actualBoundingBoxAscent); dsc = Math.max(dsc, m.actualBoundingBoxDescent);
      });
      var capH = asc + dsc;
      var blockH = capH + (lines.length - 1) * test * lh;
      var k = Math.min(bw / wmax, bh / blockH, (o.maxCap || 1) * H / capH);
      var size = test * k;
      ctx.font = (o.weight || 700) + ' ' + size + 'px ' + FONT;
      if ('letterSpacing' in ctx) ctx.letterSpacing = (track * size) + 'px';
      ctx.fillStyle = '#fff';
      ctx.textBaseline = 'alphabetic';
      var y0 = (box[1] + box[3]) / 2 * H - blockH * k / 2 + asc * k;
      lines.forEach(function (s, i) {
        var m = ctx.measureText(s);
        var w = m.actualBoundingBoxLeft + m.actualBoundingBoxRight;
        var x = o.align === 'left' ? box[0] * W + m.actualBoundingBoxLeft : (box[0] + box[2]) / 2 * W - w / 2 + m.actualBoundingBoxLeft;
        ctx.fillText(s, x, y0 + i * size * lh);
      });
    };
  }

  // the ratified mark: five strokes at 9 on 100, spine over the flats at the knockouts
  function mark(o) {
    o = o || {};
    return function (ctx, W, H) {
      var s = (o.size || 0.7) * Math.min(W, H) / 100;
      var ox = (o.cx == null ? 0.5 : o.cx) * W - 50 * s, oy = (o.cy == null ? 0.5 : o.cy) * H - 50 * s;
      var sw = (o.stroke || 9) * s;
      ctx.save();
      ctx.translate(ox, oy);
      ctx.lineJoin = 'miter'; ctx.miterLimit = 6; ctx.lineCap = 'butt';
      ctx.strokeStyle = '#fff'; ctx.lineWidth = sw;
      ctx.beginPath();
      [[6, 28], [44, 6], [66, 94], [30, 74], [94, 52]].forEach(function (p, i) { ctx[i ? 'lineTo' : 'moveTo'](p[0] * s, p[1] * s); });
      ctx.closePath(); ctx.stroke();
      ctx.globalCompositeOperation = 'destination-out';
      ctx.lineWidth = sw * 1.7;
      ctx.beginPath(); ctx.moveTo(50.5 * s, 32 * s); ctx.lineTo(54.9 * s, 49.4 * s); ctx.moveTo(56.4 * s, 55.5 * s); ctx.lineTo(60.7 * s, 72.9 * s); ctx.stroke();
      ctx.globalCompositeOperation = 'source-over';
      ctx.lineWidth = sw;
      ctx.beginPath(); ctx.moveTo(44 * s, 6 * s); ctx.lineTo(66 * s, 94 * s); ctx.stroke();
      ctx.restore();
    };
  }

  // a grid of rounded cells: the test suite, one square per assertion
  function cells(cols, rows, o) {
    o = o || {};
    return function (ctx, W, H) {
      var box = o.box || [0.1, 0.16, 0.9, 0.84];
      var bw = (box[2] - box[0]) * W, bh = (box[3] - box[1]) * H;
      var pitch = Math.min(bw / cols, bh / rows), sz = pitch * (o.fill || 0.62), r = sz * (o.round || 0.22);
      var x0 = (box[0] + box[2]) / 2 * W - pitch * cols / 2, y0 = (box[1] + box[3]) / 2 * H - pitch * rows / 2;
      ctx.fillStyle = '#fff';
      for (var j = 0; j < rows; j++) for (var i = 0; i < cols; i++) {
        var x = x0 + i * pitch + (pitch - sz) / 2, y = y0 + j * pitch + (pitch - sz) / 2;
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(x, y, sz, sz, r); else ctx.rect(x, y, sz, sz);
        ctx.fill();
      }
    };
  }

  // the empty table: rows of em dashes, the only honest value before a run exists
  function dashes(cols, rows, o) {
    o = o || {};
    return function (ctx, W, H) {
      var box = o.box || [0.08, 0.18, 0.92, 0.82];
      var cw = (box[2] - box[0]) * W / cols, rh = (box[3] - box[1]) * H / rows;
      var len = cw * (o.len || 0.34), th = Math.min(rh * 0.3, len * 0.3);
      ctx.fillStyle = '#fff';
      for (var j = 0; j < rows; j++) for (var i = 0; i < cols; i++) {
        var cx = box[0] * W + (i + 0.5) * cw, cy = box[1] * H + (j + 0.5) * rh;
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(cx - len / 2, cy - th / 2, len, th, th * 0.12); else ctx.rect(cx - len / 2, cy - th / 2, len, th);
        ctx.fill();
      }
    };
  }

  /* ---------- fields: distance transform and Poisson inflation ---------- */

  var INF = 1e20;

  function edt1d(f, n, d, v, z) {
    var k = 0, q, s;
    v[0] = 0; z[0] = -INF; z[1] = INF;
    for (q = 1; q < n; q++) {
      s = ((f[q] + q * q) - (f[v[k]] + v[k] * v[k])) / (2 * q - 2 * v[k]);
      while (s <= z[k]) { k--; s = ((f[q] + q * q) - (f[v[k]] + v[k] * v[k])) / (2 * q - 2 * v[k]); }
      k++; v[k] = q; z[k] = s; z[k + 1] = INF;
    }
    for (k = 0, q = 0; q < n; q++) {
      while (z[k + 1] < q) k++;
      d[q] = (q - v[k]) * (q - v[k]) + f[v[k]];
    }
  }

  // squared Euclidean distance to the nearest cell where grid == 0
  function edt(grid, w, h) {
    var n = Math.max(w, h);
    var f = new Float64Array(n), d = new Float64Array(n), v = new Int32Array(n), z = new Float64Array(n + 1);
    var x, y;
    for (x = 0; x < w; x++) {
      for (y = 0; y < h; y++) f[y] = grid[y * w + x];
      edt1d(f, h, d, v, z);
      for (y = 0; y < h; y++) grid[y * w + x] = d[y];
    }
    for (y = 0; y < h; y++) {
      for (x = 0; x < w; x++) f[x] = grid[y * w + x];
      edt1d(f, w, d, v, z);
      for (x = 0; x < w; x++) grid[y * w + x] = d[x];
    }
    return grid;
  }

  function signedDistance(alpha, w, h) {
    var N = w * h, a = new Float64Array(N), b = new Float64Array(N), i;
    for (i = 0; i < N; i++) { var inside = alpha[i] > 0.5; a[i] = inside ? INF : 0; b[i] = inside ? 0 : INF; }
    edt(a, w, h); edt(b, w, h);
    var sdf = new Float32Array(N);
    for (i = 0; i < N; i++) {
      var al = alpha[i];
      if (al > 0.02 && al < 0.98) sdf[i] = 0.5 - al;
      else sdf[i] = al > 0.5 ? -(Math.sqrt(a[i]) - 0.5) : Math.sqrt(b[i]) - 0.5;
    }
    return sdf;
  }

  // lap(h) = -1 inside mask, h = 0 outside. Red-black SOR, coarse to fine.
  function inflate(mask, w, h) {
    var levels = [{ w: w, h: h, m: mask }];
    while (levels[levels.length - 1].w > 96 && levels[levels.length - 1].h > 64) {
      var L = levels[levels.length - 1], cw = L.w >> 1, ch = L.h >> 1, cm = new Uint8Array(cw * ch);
      for (var y = 0; y < ch; y++) for (var x = 0; x < cw; x++) {
        var s = L.m[(2 * y) * L.w + 2 * x] + L.m[(2 * y) * L.w + 2 * x + 1] + L.m[(2 * y + 1) * L.w + 2 * x] + L.m[(2 * y + 1) * L.w + 2 * x + 1];
        cm[y * cw + x] = s >= 3 ? 1 : 0;
      }
      levels.push({ w: cw, h: ch, m: cm });
    }
    var u = null;
    for (var l = levels.length - 1; l >= 0; l--) {
      var Lv = levels[l], W = Lv.w, Hh = Lv.h, m = Lv.m, hs = Math.pow(2, l), rhs = hs * hs;
      var cur = new Float32Array(W * Hh);
      if (u) {
        var pw = levels[l + 1].w, ph = levels[l + 1].h;
        for (var yy = 0; yy < Hh; yy++) for (var xx = 0; xx < W; xx++) {
          var sx = Math.min(pw - 1, xx >> 1), sy = Math.min(ph - 1, yy >> 1);
          cur[yy * W + xx] = m[yy * W + xx] ? u[sy * pw + sx] : 0;
        }
      }
      var iters = l === levels.length - 1 ? 500 : 90, om = 1.86;
      for (var it = 0; it < iters; it++) {
        for (var col = 0; col < 2; col++) {
          for (var j = 1; j < Hh - 1; j++) {
            var row = j * W;
            for (var i2 = 1 + ((j + col) & 1); i2 < W - 1; i2 += 2) {
              var id = row + i2;
              if (!m[id]) continue;
              var nb = cur[id - 1] + cur[id + 1] + cur[id - W] + cur[id + W];
              cur[id] += om * ((nb + rhs) * 0.25 - cur[id]);
            }
          }
        }
      }
      u = cur;
    }
    return u;
  }

  function buildField(draw, W, H, opts) {
    var s = Math.min(1, (opts.fieldMax || 1024) / Math.max(W, H));
    var fw = Math.max(8, Math.round(W * s)), fh = Math.max(8, Math.round(H * s));
    var cv = document.createElement('canvas');
    cv.width = fw; cv.height = fh;
    var ctx = cv.getContext('2d', { willReadFrequently: true });
    ctx.clearRect(0, 0, fw, fh);
    ctx.save(); ctx.scale(fw / W, fh / H);
    draw(ctx, W, H);
    ctx.restore();
    var px = ctx.getImageData(0, 0, fw, fh).data, N = fw * fh, alpha = new Float32Array(N), i;
    for (i = 0; i < N; i++) alpha[i] = px[i * 4 + 3] / 255;
    var sdf = signedDistance(alpha, fw, fh);
    var maxIn = 0;
    for (i = 0; i < N; i++) if (-sdf[i] > maxIn) maxIn = -sdf[i];
    var G = (opts.grow == null ? 0.34 : opts.grow) * maxIn;
    // every connected piece (a letter, a dot, a cell) is its own balloon: inflate each
    // one alone, then keep the fuller skin wherever two overlap, as if one sits in front
    var H1 = new Float32Array(N), lab = new Int32Array(N), stack = new Int32Array(N), pad = Math.ceil(G + 3);
    var x, y, nl = 0;
    for (var start = 0; start < N; start++) {
      if (alpha[start] <= 0.5 || lab[start]) continue;
      nl++;
      var sp = 0, x0 = fw, y0 = fh, x1 = 0, y1 = 0, area = 0;
      stack[sp++] = start; lab[start] = nl;
      while (sp) {
        var c = stack[--sp], cx = c % fw, cy = (c / fw) | 0;
        area++;
        if (cx < x0) x0 = cx; if (cx > x1) x1 = cx; if (cy < y0) y0 = cy; if (cy > y1) y1 = cy;
        if (cx > 0 && alpha[c - 1] > 0.5 && !lab[c - 1]) { lab[c - 1] = nl; stack[sp++] = c - 1; }
        if (cx < fw - 1 && alpha[c + 1] > 0.5 && !lab[c + 1]) { lab[c + 1] = nl; stack[sp++] = c + 1; }
        if (cy > 0 && alpha[c - fw] > 0.5 && !lab[c - fw]) { lab[c - fw] = nl; stack[sp++] = c - fw; }
        if (cy < fh - 1 && alpha[c + fw] > 0.5 && !lab[c + fw]) { lab[c + fw] = nl; stack[sp++] = c + fw; }
      }
      if (area < 6) continue;
      var bx0 = Math.max(0, x0 - pad), by0 = Math.max(0, y0 - pad), bx1 = Math.min(fw - 1, x1 + pad), by1 = Math.min(fh - 1, y1 + pad);
      var lw = bx1 - bx0 + 1, lh = by1 - by0 + 1, la = new Float32Array(lw * lh);
      for (y = 0; y < lh; y++) for (x = 0; x < lw; x++) {
        var gi = (by0 + y) * fw + bx0 + x, a = alpha[gi];
        if (lab[gi] === nl) la[y * lw + x] = a;
        else if (a > 0 && a <= 0.5) {
          var gx0 = bx0 + x, gy0 = by0 + y;
          if ((gx0 > 0 && lab[gi - 1] === nl) || (gx0 < fw - 1 && lab[gi + 1] === nl) || (gy0 > 0 && lab[gi - fw] === nl) || (gy0 < fh - 1 && lab[gi + fw] === nl)) la[y * lw + x] = a;
        }
      }
      var lsdf = signedDistance(la, lw, lh), lm = new Uint8Array(lw * lh);
      for (y = 1; y < lh - 1; y++) for (x = 1; x < lw - 1; x++) lm[y * lw + x] = lsdf[y * lw + x] < G ? 1 : 0;
      var lhgt = inflate(lm, lw, lh), lmax = 1e-6;
      for (i = 0; i < lw * lh; i++) if (lhgt[i] > lmax) lmax = lhgt[i];
      for (y = 0; y < lh; y++) for (x = 0; x < lw; x++) {
        var v = Math.pow(lhgt[y * lw + x] / lmax, 0.8), gi2 = (by0 + y) * fw + bx0 + x;
        if (v > H1[gi2]) H1[gi2] = v;
      }
    }
    // a light blur melts the staircase at the grown edge and softens the seams
    var H2 = new Float32Array(N);
    for (var pass = 0; pass < 2; pass++) {
      for (y = 1; y < fh - 1; y++) for (x = 1; x < fw - 1; x++) {
        var id = y * fw + x;
        H2[id] = (H1[id] * 4 + H1[id - 1] + H1[id + 1] + H1[id - fw] + H1[id + fw]) / 8;
      }
      var t = H1; H1 = H2; H2 = t;
    }
    var out = new Float32Array(N * 4);
    for (y = 0; y < fh; y++) for (x = 0; x < fw; x++) {
      var k = y * fw + x;
      var gx = (H1[y * fw + Math.min(fw - 1, x + 1)] - H1[y * fw + Math.max(0, x - 1)]) * 0.5;
      var gy = (H1[Math.min(fh - 1, y + 1) * fw + x] - H1[Math.max(0, y - 1) * fw + x]) * 0.5;
      out[k * 4] = sdf[k]; out[k * 4 + 1] = H1[k]; out[k * 4 + 2] = gx; out[k * 4 + 3] = gy;
    }
    return { data: out, w: fw, h: fh, scale: fw / W, maxIn: maxIn, grow: G };
  }

  /* ---------- shader ---------- */

  var VS = '#version 300 es\nin vec2 a;void main(){gl_Position=vec4(a,0.,1.);}';

  var FS = [
    '#version 300 es',
    'precision highp float;',
    'uniform vec2 R;',            // canvas size in px
    'uniform sampler2D F;',       // r: flat sdf, g: pressure H, ba: dH (field px)
    'uniform float FS;',          // field px per canvas px
    'uniform float ZS;',          // balloon height scale, field px
    'uniform float GR;',          // how far the balloon grows past the flat shape, field px
    'uniform float TH;',          // loop phase, 0..2pi
    'uniform vec4 CA[' + MAXC + '];',
    'uniform vec4 CB[' + MAXC + '];',
    'uniform int NC;',
    'uniform vec4 P0;',           // smin k, warp amp, warp freq, edge grain
    'uniform vec4 P1;',           // tau deep, tau edge, depth span, bob
    'uniform vec4 P2;',           // wrinkle amp, film shift, shadow, ambient
    'uniform vec3 CBG;',
    'uniform vec3 CFL;',
    'uniform vec3 CIN;',
    'uniform int MAT;',
    'uniform vec4 P3;',           // technical: grid, construction line, ink tolerance line, grid pitch
    'uniform vec4 P4;',           // technical: contour lines on the skin, contour count
    'out vec4 o;',

    'float h12(vec2 p){vec3 p3=fract(vec3(p.xyx)*.1031);p3+=dot(p3,p3.yzx+33.33);return fract((p3.x+p3.y)*p3.z);}',
    'vec3 nd(vec2 x){vec2 i=floor(x),f=fract(x);vec2 u=f*f*f*(f*(f*6.-15.)+10.);vec2 du=30.*f*f*(f*(f-2.)+1.);',
    ' float a=h12(i),b=h12(i+vec2(1,0)),c=h12(i+vec2(0,1)),d=h12(i+vec2(1,1));',
    ' float k1=b-a,k2=c-a,k4=a-b-c+d;return vec3(a+k1*u.x+k2*u.y+k4*u.x*u.y,du*vec2(k1+k4*u.y,k2+k4*u.x));}',
    'float smin(float a,float b,float k){float h=max(k-abs(a-b),0.)/k;return min(a,b)-h*h*k*.25;}',
    'float cap(vec2 p,vec2 a,vec2 b,float ra,float rb){vec2 pa=p-a,ba=b-a;float h=clamp(dot(pa,ba)/max(dot(ba,ba),1e-8),0.,1.);return length(pa-ba*h)-mix(ra,rb,h);}',

    // the ink: capsules, smooth union, a periodic warp, a static grain on the edge
    'float ink(vec2 p){',
    ' float w=P0.y,f=P0.z;',
    ' vec2 q=p+w*vec2(sin(p.y*f+TH+1.3)+.5*sin(p.y*f*2.3-2.*TH+.4)+.25*sin(p.x*f*3.1+3.*TH),',
    '                 sin(p.x*f*.9-TH+2.1)+.5*sin(p.x*f*2.1+2.*TH+1.7)+.25*sin(p.y*f*2.9-3.*TH));',
    ' q+=w*.35*vec2(sin(q.y*f*4.3+2.*TH),sin(q.x*f*3.7-TH));',
    ' float d=1e3;',
    ' for(int i=0;i<' + MAXC + ';i++){if(i>=NC)break;d=smin(d,cap(q,CA[i].xy,CB[i].xy,CA[i].z,CB[i].z),P0.x);}',
    ' d+=P0.w*(nd(p*38.).x-.5)+P0.w*.35*(nd(p*120.).x-.5);',
    ' return d;}',

    'vec3 ramp(float t){t=fract(t);',
    ' vec3 c0=vec3(.04,.10,.32),c1=vec3(.10,.32,.86),c2=vec3(.28,.56,1.),c3=vec3(.50,.42,.98),c4=vec3(.80,.87,1.),c5=vec3(.18,.42,.96);',
    ' if(t<.2)return mix(c0,c1,t/.2);if(t<.42)return mix(c1,c2,(t-.2)/.22);if(t<.6)return mix(c2,c3,(t-.42)/.18);',
    ' if(t<.78)return mix(c3,c4,(t-.6)/.18);return mix(c4,c5,(t-.78)/.22);}',

    // a studio: a big softbox top left, a strip right, a floor bounce, a ceiling
    'float env(vec3 r){',
    ' float e=.1+.3*smoothstep(.95,.1,length(r.xy));',
    ' e+=1.6*smoothstep(.55,.0,length((r.xy-vec2(-.42,-.5))*vec2(1.,1.4)));',
    ' e+=.95*smoothstep(.11,.0,abs(r.x-.64))*smoothstep(.95,-.35,r.y);',
    ' e+=.38*smoothstep(.35,.95,r.y);',
    ' e+=.5*smoothstep(.07,.0,abs(length(r.xy)-.93));',
    ' return e;}',

    'void main(){',
    ' vec2 px=vec2(gl_FragCoord.x,R.y-gl_FragCoord.y);',
    ' vec2 p=(px-.5*R)/R.y;',
    ' vec2 uv=px/R;',
    ' vec4 s=texture(F,uv);',
    ' float fl=clamp(.5-s.r/FS,0.,1.);',
    // the technical layer, from the films: the site grille on the ground, a construction
    // line a few pixels outside the flat shape, a tolerance line outside the ink
    ' vec3 hair=dot(CBG,vec3(.333))>.5?vec3(.08,.09,.1):vec3(.91,.93,.96);',
    ' float gp=max(16.,R.y*P3.w);',
    ' vec2 gq=abs(fract((px-.5*R)/gp+.5)-.5)*gp;',
    ' float gline=1.-smoothstep(.0,1.,min(gq.x,gq.y));',
    ' vec3 col=mix(CBG,hair,gline*P3.x);',
    ' float cons=1.-smoothstep(.0,1.,abs(s.r/FS-R.y*.008));',
    ' col=mix(col,mix(CFL,hair,.35),cons*P3.y);',
    ' col=mix(col,CFL,fl);',
    ' float d=ink(p);',
    ' float im=clamp(.5-d*R.y,0.,1.);',
    ' float tl=(1.-smoothstep(0.,1.1,abs(d*R.y-R.y*.0105)))*P3.z;',
    ' vec3 tc=dot(CBG,vec3(.333))>.5?vec3(.12,.36,.78):vec3(.45,.64,.98);',
    ' if(im<=0.){col=mix(col,tc,tl);o=vec4(col+(h12(px)-.5)/255.,1.);return;}',
    // inflation: deep in the ink the letters are full, near its edge they sag
    ' float depth=-d;',
    ' float tau=mix(P1.y,P1.x,smoothstep(0.,P1.z,depth));',
    ' vec2 bob=vec2(0.,P1.w*sin(TH+p.x*2.2));',
    ' vec4 b=texture(F,uv+bob);',
    ' float L=b.g-tau;',
    ' vec2 g=b.ba;',
    ' float gl=max(length(g),1e-5);',
    ' float bm=clamp(.5+(L/gl)/FS,0.,1.);',
    // the ground under the balloons: ink, with a contact shade and a soft drop shadow
    ' vec3 gnd=CIN;',
    ' float sh=0.;',
    ' for(int k=1;k<=3;k++){vec4 ss=texture(F,uv+bob+vec2(-.55,-.8)*float(k)*.0065*vec2(R.y/R.x,1.));sh+=smoothstep(-.02,.12,ss.g-tau);}',
    ' float ao=exp(-max(s.r-GR,0.)/(ZS*.5));',
    ' gnd*=1.-P2.z*(.55*sh/3.+.45*ao)*(1.-bm);',
    ' col=mix(col,gnd,im);',
    ' if(bm>0.){',
    '  float z=sqrt(max(L,0.)+.0015);',
    '  vec2 gz=ZS*.5*g/z;',
    // wrinkles: pleats that run from the edge inward, stronger where the skin is slack
    '  vec2 gd=g/gl,tg=vec2(-gd.y,gd.x);',
    '  vec2 q=px*FS;',
    '  float slack=1.-smoothstep(.0,.3,L);',
    '  float fr=1.05/ZS;vec2 wr=vec2(0.);float aw=1.;',
    '  for(int i=0;i<2;i++){vec2 c=vec2(dot(q,tg)*fr*2.6,dot(q,gd)*fr*.5)+float(i)*17.3;vec3 n3=nd(c);wr+=aw*(n3.y*fr*2.6*tg+n3.z*fr*.5*gd);fr*=2.1;aw*=.45;}',
    '  vec3 cr=nd(q*1.1/ZS);vec3 cr2=nd(q*2.6/ZS+9.1);',
    '  vec2 crump=(cr.yz*1.1+cr2.yz*2.6*.35)/ZS;',
    '  float spine=smoothstep(.002,.012,gl);',
    '  gz+=P2.x*ZS*(wr*(MAT==1?.7*slack*slack:.06+.9*slack*slack)*spine+crump*(MAT==1?.0:.3));',
    '  gz=clamp(gz,vec2(-30.),vec2(30.));',
    '  vec3 n=normalize(vec3(-gz,1.));',
    '  vec3 r=vec3(2.*n.z*n.xy,2.*n.z*n.z-1.);',
    '  float e=env(r);',
    '  vec3 bc;',
    '  if(MAT==1){',
    '   vec3 Lk=normalize(vec3(-.45,-.62,.64));',
    '   float wrp=clamp((dot(n,Lk)+.2)/1.2,0.,1.);',
    '   float sp=pow(max(dot(normalize(Lk+vec3(0,0,1)),n),0.),30.);',
    '   float cav=smoothstep(.0,.3,L+.03);',
    '   bc=vec3(.95,.955,.965)*(.3+.7*wrp)*(.72+.28*cav)+vec3(.4)*sp+vec3(.06,.08,.13)*pow(1.-n.z,2.)*.6;',
    '  }else{',
    '   float film=.62*(1.-n.z)+P2.y+.1*sin(p.x*3.+p.y*2.5+TH)+.1*cr.x;',
    '   vec3 base=MAT==2?mix(vec3(.05,.06,.075),ramp(film),.35):ramp(film);',
    '   bc=base*(.34+1.05*e)+vec3(1.)*pow(max(e-.5,0.),2.)*.9;',
    '   bc+=ramp(film+.33)*pow(1.-n.z,3.)*.45;',
    '   bc*=.55+.45*smoothstep(-.05,.2,L);',
    '  }',
    '  bc*=P2.w+(1.-P2.w)*smoothstep(-.02,.12,L+.02);',
    // contour lines of the pressure field: the skin read as a height map
    '  float cn=b.g*P4.y,cw=max(fwidth(cn),1e-4),cf=fract(cn);',
    '  float cl=(1.-smoothstep(0.,cw*1.3,min(cf,1.-cf)))*smoothstep(.0,.04,L);',
    '  bc=mix(bc,MAT==1?vec3(.3,.42,.66):vec3(.86,.92,1.),cl*P4.x);',
    '  col=mix(col,bc,bm*im);',
    ' }',
    ' o=vec4(col+(h12(px)-.5)/255.,1.);',
    '}'
  ].join('\n');

  /* ---------- the choreography kit ---------- */

  // A is handed to a scene's ink(t, A) each frame. Positions are in frame units:
  // y runs -0.5 (top) to 0.5 (bottom), x runs -A.ax to A.ax, so a radius of 0.1 is a
  // tenth of the frame's height at any aspect. Every periodic call takes an integer
  // number of turns per loop, which is what makes a clip seamless.
  function Kit() { this.a = new Float32Array(MAXC * 4); this.b = new Float32Array(MAXC * 4); this.n = 0; }
  Kit.prototype.begin = function (t, T, ax, amp) {
    this.n = 0; this.t = t; this.T = T; this.ax = ax; this.amp = amp == null ? 1 : amp;
    this.th = TAU * t / T; this.u = fract(t / T);
  };
  Kit.prototype.cap = function (x1, y1, r1, x2, y2, r2) {
    if (this.n >= MAXC) return;
    var m = this.amp, i = this.n++ * 4;
    this.a[i] = x1; this.a[i + 1] = y1; this.a[i + 2] = Math.max(0, r1 * m) - (1 - m) * 0.02;
    this.b[i] = x2; this.b[i + 1] = y2; this.b[i + 2] = Math.max(0, r2 * m) - (1 - m) * 0.02;
  };
  Kit.prototype.blob = function (x, y, r) { this.cap(x, y, r, x, y, r); };
  // s(k, phase): sine with k whole turns per loop
  Kit.prototype.s = function (k, ph) { return Math.sin(k * this.th + (ph || 0)); };
  Kit.prototype.c = function (k, ph) { return Math.cos(k * this.th + (ph || 0)); };
  // a chain of tapered capsules along fn(s) -> [x, y], radius rf(s), s in [0, 1]
  Kit.prototype.curve = function (fn, n, rf) {
    var prev = fn(0), rp = rf(0);
    for (var i = 1; i <= n; i++) {
      var s = i / n, p = fn(s), r = rf(s);
      this.cap(prev[0], prev[1], rp, p[0], p[1], r);
      prev = p; rp = r;
    }
  };
  // a tapered brush stroke: thick in the middle, pointed at the ends (or at one end)
  Kit.prototype.taper = function (s, a, b) { return Math.pow(Math.max(0, Math.sin(Math.PI * cl(s, 0, 1))), a == null ? 0.7 : a) * (b == null ? 1 : b); };

  /* ---------- scenes ---------- */

  // each scene: T (loop seconds), shape, palette, look parameters, and ink(t, A)
  var SCENES = {};
  // the technical layer every scene carries unless it says otherwise
  var TECH = { grid: 0.06, cons: 0.28, tol: 0.5, pitch: 0.052, contour: 0.15, lines: 15 };

  // home stage: the wordmark, the ink, the foil. Built to sit under DOM type at top left.
  SCENES.hero = {
    T: 16, pal: 'night',
    shape: type('EDIFY', { box: [0.035, 0.36, 0.965, 0.86], track: -0.035, maxCap: 0.44 }),
    grow: 0.4, k: 0.085, warp: 0.022, warpF: 5.2, grain: 0.0022,
    tau: [0.02, 0.32, 0.06], bob: 0.0035, wrinkle: 0.55, film: 0.02, shadow: 0.34, amb: 0.35,
    ink: function (A) {
      var ax = A.ax, u = A.u;
      // one pool that travels the whole wordmark, left to right and home again
      var px = Math.sin(TAU * u - 1.9) * 0.62 * ax, py = 0.1 + 0.07 * A.s(2, 0.4);
      A.cap(px - 0.12, py + 0.05, 0.2 + 0.03 * A.s(3), px + 0.14, py - 0.06, 0.16 + 0.03 * A.s(2, 1.1));
      // a second pool, counter-phase, lower
      var qx = Math.sin(TAU * u + 1.2) * 0.58 * ax, qy = 0.26 + 0.05 * A.s(1, 2.2);
      A.cap(qx - 0.1, qy, 0.17 + 0.025 * A.s(2, 2.3), qx + 0.16, qy + 0.05, 0.12);
      // the long stroke from the top edge, sweeping like the pendulum of a brush
      var sw = 0.42 * ax + 0.22 * ax * A.s(1, 0.3);
      A.curve(function (s) {
        return [sw + (0.1 - 0.35 * s) * ax * 0.5 + 0.06 * Math.sin(s * 5 + A.th), -0.62 + s * 0.95];
      }, 8, function (s) { return 0.012 + 0.07 * Math.pow(s, 1.4) + 0.012 * Math.sin(s * 9 - A.th * 2); });
      // a stroke that leaves the pool toward the bottom edge
      A.curve(function (s) {
        return [px + (-0.05 - 0.28 * s) * ax * 0.6 + 0.04 * Math.sin(s * 6 + A.th * 2), py + 0.1 + s * 0.5];
      }, 6, function (s) { return 0.09 * (1 - s) + 0.018 + 0.01 * Math.sin(s * 11 + A.th); });
      // the upper-left swoosh: the one that reaches into the headline, briefly
      var reach = 0.5 + 0.5 * A.s(1, 2.6);
      A.curve(function (s) {
        return [px - s * 0.62 * ax * reach, py - 0.08 - s * 0.36 * reach + 0.05 * Math.sin(s * 4 - A.th)];
      }, 7, function (s) { return 0.05 * A.taper(s * 0.8 + 0.2, 0.9) + 0.006; });
      // satellites: drops that orbit the pools, touch, and snap off
      for (var i = 0; i < 5; i++) {
        var ph = i * 1.37, orb = 0.26 + 0.07 * Math.sin(ph * 3);
        var ox = (i % 2 ? qx : px) + orb * Math.cos(A.th * (i % 2 ? -1 : 1) + ph) * 1.2;
        var oy = (i % 2 ? qy : py) + orb * 0.55 * Math.sin(A.th * (i % 2 ? -1 : 1) * 2 + ph);
        A.blob(ox, oy, 0.022 + 0.012 * Math.sin(ph * 5));
      }
    }
  };

  // the mark, inflated: replaces the P1 plate beside the hero terminal
  SCENES.mark = {
    T: 10, pal: 'night',
    shape: mark({ size: 0.72, stroke: 9.5 }),
    grow: 0.45, k: 0.1, warp: 0.03, warpF: 4.5, grain: 0.0022,
    tau: [0.02, 0.5, 0.09], bob: 0.003, wrinkle: 0.6, film: 0.06, shadow: 0.34, amb: 0.35,
    ink: function (A) {
      var ax = A.ax;
      // a single slow tide that breathes over the mark from the lower right
      var r = 0.3 + 0.08 * A.s(1, 0.5);
      A.cap(0.15 * ax + 0.25 * A.c(1), 0.12 + 0.12 * A.s(1), r, -0.1 * ax + 0.2 * A.c(1, 1.8), -0.15 + 0.1 * A.s(2, 0.7), r * 0.72);
      A.curve(function (s) { return [(-0.9 + 1.9 * s) * ax, 0.42 - 0.9 * s * s + 0.05 * Math.sin(s * 7 + A.th)]; }, 8,
        function (s) { return 0.02 + 0.06 * A.taper(s, 0.6) * (0.7 + 0.3 * A.s(1, s * 3)); });
      for (var i = 0; i < 4; i++) A.blob((0.55 - i * 0.3) * ax + 0.05 * A.s(2, i), -0.3 + 0.1 * A.c(1, i * 2), 0.03 + 0.01 * i);
    }
  };

  // runtimes: one folder name each, one ink behaviour each
  function runtime(word, pal, behave, extra) {
    var sc = {
      T: 8, pal: pal,
      shape: type(word, { box: [0.08, 0.3, 0.92, 0.7], track: -0.03, maxCap: 0.36 }),
      grow: 0.34, k: 0.07, warp: 0.02, warpF: 6, grain: 0.0022,
      tau: [0.02, 0.45, 0.07], bob: 0.003, wrinkle: 0.6, film: 0.0, shadow: 0.34, amb: 0.35,
      ink: behave
    };
    for (var k in extra) sc[k] = extra[k];
    return sc;
  }
  var B = {
    // drips from the top edge: a bead gathers, stretches, lets go and falls through
    drip: function (A) {
      var ax = A.ax;
      A.cap(-ax * 1.2, -0.62, 0.2, ax * 1.2, -0.62, 0.2);
      for (var i = 0; i < 3; i++) {
        var u = fract(A.u + i / 3), x = (-0.55 + i * 0.55) * ax + 0.04 * Math.sin(i * 4 + A.th);
        var y = -0.46 + E.inout(cl(u / 0.55, 0, 1)) * 0.55 + (u > 0.55 ? Math.pow((u - 0.55) / 0.45, 2) * 1.3 : 0);
        var r = 0.1 + 0.05 * Math.sin(Math.PI * cl(u / 0.55, 0, 1));
        A.cap(x, -0.44, 0.05 * (1 - smooth(0.45, 0.62, u)), x, y, r);
      }
    },
    // one wave front that crosses left to right, wraps off-screen and comes again
    sweep: function (A) {
      var ax = A.ax, x = lerp(-ax * 2.2, ax * 2.2, A.u);
      A.curve(function (s) { return [x + 0.12 * Math.sin(s * 8 + A.th * 2) - (s - 0.5) * 0.2, -0.65 + 1.3 * s]; }, 9,
        function (s) { return 0.28 + 0.05 * Math.sin(s * 11 - A.th * 3); });
      A.blob(x - 0.5 * ax, 0.1 * A.s(2), 0.2);
      A.blob(x + 0.36, -0.2 + 0.1 * A.s(3), 0.07);
      A.blob(x + 0.5, 0.25 + 0.08 * A.c(2), 0.045);
    },
    // a pointer's path: one drop draws a lemniscate over the word, leaving a thinning trail
    trace: function (A) {
      var ax = A.ax;
      for (var i = 0; i < 12; i++) {
        var th = A.th - i * 0.11, th2 = A.th - (i + 1) * 0.11;
        var P = function (a) { return [Math.sin(a) * 0.72 * ax, Math.sin(2 * a) * 0.2]; };
        var p1 = P(th), p2 = P(th2);
        A.cap(p1[0], p1[1], 0.2 * Math.pow(1 - i / 12, 1.2) + 0.015, p2[0], p2[1], 0.2 * Math.pow(1 - (i + 1) / 12, 1.2) + 0.015);
      }
    },
    // two pools that meet in the middle, bridge, and pull apart
    twins: function (A) {
      var ax = A.ax, g = 0.28 + 0.26 * (0.5 + 0.5 * A.c(1));
      A.blob(-g * ax, 0.02 * A.s(2), 0.27 + 0.03 * A.s(2, 1));
      A.blob(g * ax, -0.02 * A.s(2), 0.27 + 0.03 * A.s(2, 2));
      A.blob(0, 0.3 * A.s(1, 0.8), 0.05);
      A.blob(0, -0.3 * A.s(1, 0.8), 0.04);
    },
    // bubbles rise from the floor, meet, and leave through the top
    rise: function (A) {
      var ax = A.ax;
      A.cap(-ax * 1.2, 0.64, 0.2, ax * 1.2, 0.64, 0.2);
      for (var i = 0; i < 8; i++) {
        var u = fract(A.u * (i % 3 === 0 ? 2 : 1) + i / 8), x = (-0.8 + (i * 0.43) % 1.6) * ax + 0.06 * Math.sin(u * 9 + i);
        var r = 0.13 + 0.1 * ((i * 37) % 5) / 5;
        A.blob(x, lerp(0.75, -0.75, u), r);
      }
    },
    // a tide: the floor rises in a slow wave and ebbs, the crest runs sideways
    tide: function (A) {
      var ax = A.ax, lvl = 0.05 + 0.2 * A.c(1);
      A.curve(function (s) { var x = (-1.25 + 2.5 * s) * ax; return [x, lvl + 0.07 * Math.sin(x * 5 - A.th * 2) + 0.04 * Math.sin(x * 11 + A.th * 3)]; }, 14,
        function () { return 0.14; });
      A.cap(-ax * 1.3, lvl + 0.45, 0.4, ax * 1.3, lvl + 0.45, 0.4);
      A.blob(0.5 * ax * A.s(1, 1), lvl - 0.24 + 0.05 * A.s(3), 0.04);
      A.blob(-0.4 * ax * A.s(1, 2), lvl - 0.3 + 0.05 * A.s(2), 0.03);
    }
  };
  SCENES['rt-claude'] = runtime('.claude', 'night', B.drip);
  SCENES['rt-codex'] = runtime('.codex', 'day', B.sweep, { k: 0.05 });
  SCENES['rt-cursor'] = runtime('.cursor', 'night', B.trace, { k: 0.12 });
  SCENES['rt-gemini'] = runtime('.gemini', 'latex', B.twins, { k: 0.16 });
  SCENES['rt-github'] = runtime('.github', 'blue', B.rise, { k: 0.1 });
  SCENES['rt-windsurf'] = runtime('.windsurf', 'day', B.tide, { k: 0.08 });

  // how it works: three documents, three human reads, filled one after another
  SCENES.spec = {
    T: 9, pal: 'night',
    shape: type(['spec', 'plan', 'tasks'], { box: [0.12, 0.1, 0.88, 0.9], lh: 0.98, align: 'left', track: -0.04 }),
    grow: 0.32, k: 0.08, warp: 0.02, warpF: 6, grain: 0.0022,
    tau: [0.02, 0.45, 0.07], bob: 0.003, wrinkle: 0.6, film: 0.08, shadow: 0.34, amb: 0.35,
    ink: function (A) {
      var ax = A.ax;
      // each line's ink runs in from the left, holds across its word, and leaves right
      for (var i = 0; i < 3; i++) {
        var u = fract(A.u - i / 3), y = -0.31 + i * 0.31;
        var head = lerp(-1.3 * ax, 1.7 * ax, E.inout(cl(u / 0.62, 0, 1)));
        var tail = lerp(-1.7 * ax, 1.7 * ax, E.inout(cl((u - 0.38) / 0.62, 0, 1)));
        A.cap(tail, y + 0.01 * A.s(3, i), 0.13, head, y + 0.02 * A.s(2, i), 0.19);
        A.blob(head + 0.08, y - 0.1, 0.06);
        A.blob(tail + 0.2, y + 0.14, 0.05);
      }
    }
  };

  // how it works, build: the red suite, and the same suite passing
  SCENES.build = {
    T: 8, pal: 'oxide',
    shape: cells(6, 4, { box: [0.1, 0.14, 0.9, 0.86], fill: 0.6, round: 0.2 }),
    grow: 0.4, k: 0.06, warp: 0.03, warpF: 5, grain: 0.0022,
    tau: [0.03, 0.5, 0.08], bob: 0.003, wrinkle: 0.35, film: 0.1, shadow: 0, amb: 0.45,
    ink: function (A) {
      var ax = A.ax, x = lerp(-ax * 2.6, ax * 2.6, A.u);
      A.curve(function (s) { return [x + 0.1 * Math.sin(s * 7 + A.th * 3) - (s - 0.5) * 0.35, -0.7 + 1.4 * s]; }, 10,
        function (s) { return 0.62 + 0.06 * Math.sin(s * 9 - A.th * 2); });
    }
  };

  // benchmarks: the empty table, and the dashes are the only thing in it
  SCENES.empty = {
    T: 10, pal: 'ghost',
    shape: dashes(3, 4, { box: [0.08, 0.08, 0.92, 0.92], len: 0.46 }),
    grow: 0.45, k: 0.12, warp: 0.03, warpF: 4, grain: 0.0022,
    tau: [0.02, 0.5, 0.08], bob: 0.004, wrinkle: 0.5, film: 0.04, shadow: 0, amb: 0.35,
    ink: function (A) {
      var ax = A.ax;
      A.cap(-0.6 * ax + 0.4 * A.s(1), 0.1 * A.c(1), 0.26, 0.2 * ax + 0.35 * A.s(1, 1.2), -0.1 * A.s(2), 0.2);
      A.blob(0.7 * ax * A.c(1, 2), 0.25 * A.s(1, 1), 0.18);
    }
  };

  // home, try it: the command, as wide as the band
  SCENES.init = {
    T: 12, pal: 'ghost',
    shape: type('edify init', { box: [0.05, 0.22, 0.95, 0.8], track: -0.035 }),
    grow: 0.32, k: 0.1, warp: 0.025, warpF: 4, grain: 0.0022,
    tau: [0.02, 0.45, 0.07], bob: 0.003, wrinkle: 0.55, film: 0.02, shadow: 0, amb: 0.35,
    ink: function (A) {
      var ax = A.ax, x = Math.sin(A.th - 1) * 0.7 * ax;
      A.cap(x - 0.25, 0.05 * A.s(2), 0.3, x + 0.25, -0.05 * A.s(2, 1), 0.24);
      A.blob(-x * 0.8, 0.28 * A.c(1), 0.12);
    }
  };

  // pricing: nothing to pay, inflated
  SCENES.free = {
    T: 12, pal: 'ghost',
    shape: type('$0', { box: [0.52, 0.08, 0.96, 0.92] }),
    grow: 0.34, k: 0.1, warp: 0.025, warpF: 4, grain: 0.0022,
    tau: [0.02, 0.45, 0.08], bob: 0.004, wrinkle: 0.55, film: 0.05, shadow: 0, amb: 0.35,
    ink: function (A) {
      var ax = A.ax;
      A.cap(0.45 * ax + 0.2 * A.s(1), 0.15 * A.c(1), 0.3, 0.5 * ax + 0.25 * A.c(1, 1), -0.1 + 0.12 * A.s(2), 0.22);
    }
  };

  // contact: two pools, one from each side, that reach for each other across the word, touch,
  // hold a bridge for a beat and let go. A conversation, inflated.
  SCENES.contact = {
    T: 14, pal: 'night',
    shape: type('Contact', { box: [0.035, 0.36, 0.965, 0.86], track: -0.035, maxCap: 0.44 }),
    grow: 0.4, k: 0.09, warp: 0.022, warpF: 5.2, grain: 0.0022,
    tau: [0.02, 0.32, 0.06], bob: 0.0035, wrinkle: 0.55, film: 0.03, shadow: 0.34, amb: 0.35,
    ink: function (A) {
      var ax = A.ax, g = 0.5 + 0.5 * A.c(1);                  // 1 apart, 0 touching
      var lx = -ax * (0.18 + 0.52 * g), rx = ax * (0.18 + 0.52 * g), y = 0.14 + 0.05 * A.s(2, 0.6);
      A.cap(lx - 0.22 * ax, y + 0.06, 0.2 + 0.02 * A.s(3), lx, y - 0.02, 0.17 + 0.02 * A.s(2, 1));
      A.cap(rx, y + 0.03, 0.16 + 0.02 * A.s(2, 2), rx + 0.24 * ax, y - 0.05, 0.2 + 0.02 * A.s(3, 1.4));
      // the reach: each pool sends a tapering arm toward the other; when they meet they bridge
      var reach = 1 - g;
      A.curve(function (s) { return [lerp(lx, lx + (rx - lx) * 0.55 * (0.35 + 0.65 * reach), s), y - 0.02 + 0.05 * Math.sin(s * 5 + A.th)]; }, 7,
        function (s) { return 0.1 * (1 - s) * (0.5 + 0.5 * reach) + 0.02; });
      A.curve(function (s) { return [lerp(rx, rx - (rx - lx) * 0.55 * (0.35 + 0.65 * reach), s), y + 0.01 + 0.05 * Math.sin(s * 5 - A.th)]; }, 7,
        function (s) { return 0.1 * (1 - s) * (0.5 + 0.5 * reach) + 0.02; });
      // a stroke from the top edge, like the hero's brush, slower
      var sw = -0.35 * ax + 0.2 * ax * A.s(1, 1.3);
      A.curve(function (s) { return [sw + 0.08 * Math.sin(s * 4 + A.th), -0.62 + s * 0.8]; }, 7,
        function (s) { return 0.01 + 0.055 * Math.pow(s, 1.3); });
      // drops that pass between the two, both ways
      for (var i = 0; i < 4; i++) {
        var u = fract(A.u * (i % 2 ? 1 : 2) + i / 4), dir = i % 2 ? -1 : 1;
        A.blob(dir * lerp(-0.8, 0.8, u) * ax, y - 0.22 + 0.06 * Math.sin(u * 9 + i), 0.02 + 0.014 * Math.sin(Math.PI * u));
      }
    }
  };

  // the readout each clip carries in its corners: series number and what it shows.
  // Backgrounds and the stage carry none (the page's own type does that job there).
  [['mark', '01', 'the mark'], ['rt-claude', '02', '.claude/commands/'], ['rt-codex', '03', '.codex/prompts/'],
   ['rt-cursor', '04', '.cursor/commands/'], ['rt-gemini', '05', '.gemini/commands/'], ['rt-github', '06', '.github/prompts/'],
   ['rt-windsurf', '07', '.windsurf/workflows/'], ['spec', '08', 'specs/<feature>/'], ['build', '09', 'red to green']
  ].forEach(function (h) { SCENES[h[0]].hud = { n: h[1], label: h[2] }; });

  /* ---------- the player ---------- */

  function compile(gl, type, src) {
    var sh = gl.createShader(type);
    gl.shaderSource(sh, src); gl.compileShader(sh);
    if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(sh));
    return sh;
  }

  function supported() {
    try { var c = document.createElement('canvas'); return !!(c.getContext('webgl2')); } catch (e) { return false; }
  }

  function create(canvas, name, opts) {
    opts = opts || {};
    var sc = typeof name === 'string' ? SCENES[name] : name;
    if (!sc) return Promise.reject(new Error('no scene ' + name));
    var gl = canvas.getContext('webgl2', { antialias: false, alpha: false, depth: false, stencil: false, premultipliedAlpha: false, preserveDrawingBuffer: !!opts.capture, powerPreference: 'high-performance' });
    if (!gl) return Promise.reject(new Error('webgl2'));
    var pal = PAL[sc.pal] || PAL.night;
    var prog = gl.createProgram();
    gl.attachShader(prog, compile(gl, gl.VERTEX_SHADER, VS));
    gl.attachShader(prog, compile(gl, gl.FRAGMENT_SHADER, FS));
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) return Promise.reject(new Error(gl.getProgramInfoLog(prog)));
    gl.useProgram(prog);
    var buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    var loc = gl.getAttribLocation(prog, 'a');
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    var U = {};
    ['R', 'F', 'FS', 'ZS', 'GR', 'TH', 'CA', 'CB', 'NC', 'P0', 'P1', 'P2', 'P3', 'P4', 'CBG', 'CFL', 'CIN', 'MAT'].forEach(function (k) { U[k] = gl.getUniformLocation(prog, k); });
    var tex = gl.createTexture();
    var kit = new Kit();
    var field = null;
    var ptr = { on: false, x: 0, y: 0, tx: 0, ty: 0, r: 0, trail: [] };
    var P = {
      T: sc.T, scene: sc, canvas: canvas, gl: gl, amp: opts.intro ? 0 : 1, introAt: -1,
      renderAt: renderAt, build: build, resize: resize, pointer: pointer, intro: intro, destroy: destroy
    };

    function norm(c) { return [c[0] / 255, c[1] / 255, c[2] / 255]; }

    function build() {
      var W = canvas.width, H = canvas.height;
      field = buildField(sc.shape, W, H, { grow: sc.grow, fieldMax: opts.fieldMax });
      gl.bindTexture(gl.TEXTURE_2D, tex);
      gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA16F, field.w, field.h, 0, gl.RGBA, gl.FLOAT, field.data);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    }

    function resize(w, h) {
      if (w === canvas.width && h === canvas.height && field) return;
      canvas.width = w; canvas.height = h;
      build();
    }

    // live only: the pointer is one more drop of ink, with a trail that thins behind it
    function pointer(x, y, on) {
      ptr.on = on;
      if (x != null) { ptr.tx = x; ptr.ty = y; if (!ptr.trail.length) { ptr.x = x; ptr.y = y; } }
    }

    function intro(now) { P.introAt = now; P.amp = 0; }

    function renderAt(t, now) {
      if (!field) build();
      var W = canvas.width, H = canvas.height, ax = W / H / 2;
      if (P.introAt >= 0 && now != null) {
        var k = cl((now - P.introAt) / 1900, 0, 1);
        P.amp = E.expo(k);
        if (k >= 1) P.introAt = -1;
      }
      kit.begin(((t % sc.T) + sc.T) % sc.T, sc.T, ax, P.amp);
      sc.ink(kit);
      if (opts.live) {
        ptr.x += (ptr.tx - ptr.x) * 0.2; ptr.y += (ptr.ty - ptr.y) * 0.2;
        ptr.r += ((ptr.on ? 1 : 0) - ptr.r) * (ptr.on ? 0.08 : 0.05);
        ptr.trail.unshift([ptr.x, ptr.y]);
        if (ptr.trail.length > 14) ptr.trail.length = 14;
        if (ptr.r > 0.01) {
          var n = ptr.trail.length, amp = kit.amp; kit.amp = 1;
          for (var i = 0; i < n - 1; i++) {
            var a = ptr.trail[i], b = ptr.trail[i + 1], f1 = 1 - i / n, f2 = 1 - (i + 1) / n;
            kit.cap(a[0], a[1], (0.085 * Math.pow(f1, 0.9) + 0.004) * ptr.r, b[0], b[1], (0.085 * Math.pow(f2, 0.9) + 0.004) * ptr.r);
          }
          kit.amp = amp;
        }
      }
      gl.viewport(0, 0, W, H);
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, tex);
      gl.uniform1i(U.F, 0);
      gl.uniform2f(U.R, W, H);
      gl.uniform1f(U.FS, field.scale);
      gl.uniform1f(U.ZS, field.maxIn * (sc.puff || 2.2));
      gl.uniform1f(U.GR, field.grow);
      gl.uniform1f(U.TH, kit.th);
      gl.uniform4fv(U.CA, kit.a);
      gl.uniform4fv(U.CB, kit.b);
      gl.uniform1i(U.NC, kit.n);
      gl.uniform4f(U.P0, sc.k, sc.warp, sc.warpF, sc.grain);
      gl.uniform4f(U.P1, sc.tau[0], sc.tau[1], sc.tau[2], sc.bob);
      gl.uniform4f(U.P2, sc.wrinkle, sc.film, sc.shadow, sc.amb);
      gl.uniform3fv(U.CBG, norm(pal.bg));
      gl.uniform3fv(U.CFL, norm(pal.flat));
      gl.uniform3fv(U.CIN, norm(pal.ink));
      gl.uniform1i(U.MAT, pal.mat);
      var tech = sc.tech || {}, dt = TECH;
      var tv = function (k) { return tech[k] == null ? dt[k] : tech[k]; };
      gl.uniform4f(U.P3, tv('grid'), tv('cons'), tv('tol'), tv('pitch'));
      gl.uniform4f(U.P4, tv('contour'), tv('lines'), 0, 0);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    }

    function destroy() {
      gl.deleteTexture(tex); gl.deleteBuffer(buf); gl.deleteProgram(prog);
      var lose = gl.getExtension('WEBGL_lose_context'); if (lose) lose.loseContext();
    }

    var fonts = document.fonts && document.fonts.load ? document.fonts.load('700 200px "Instrument Sans"') : Promise.resolve();
    return fonts.catch(function () {}).then(function () { build(); return P; });
  }

  root.EdInk = { tech: TECH, create: create, supported: supported, scenes: SCENES, palettes: PAL, shapes: { type: type, mark: mark, cells: cells, dashes: dashes } };
})(window);
