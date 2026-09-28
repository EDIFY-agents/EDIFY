/* EDIFY public site — motion and small behaviours.
   A plain-JS port of the Component in EDIFY Site.dc.html: boot, reveal system,
   canvas field, plate gallery, velocity marquee, stacked cards, meter, typed
   terminals, tabbed matrix, bars and counters, all driven by one rAF loop.
   The page reads fully without this file: nothing is hidden until JS hides it. */
(function () {
  'use strict';

  var doc = document;
  var root = doc.documentElement;
  var reduced = window.matchMedia('(prefers-reduced-motion:reduce)').matches;
  var small = window.innerWidth < 560;
  var $ = function (s, r) { return (r || doc).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || doc).querySelectorAll(s)); };

  var S = {
    counters: [], pending: [], skew: 0, vel: 0, lastY: window.scrollY,
    marqueeOffset: 0, dir: 1, frameTimes: [], meterT: 0, hidden: false, rafDead: false, n: 0
  };

  /* ---------- menu, copy buttons, year ---------- */

  function setupChrome() {
    var menu = $('#ed-menu');
    $$('[data-menu-toggle]').forEach(function (b) {
      b.addEventListener('click', function () {
        if (!menu) return;
        var open = !menu.classList.contains('open');
        menu.classList.toggle('open', open);
        doc.body.style.overflow = open ? 'hidden' : '';
        $$('[data-menu-toggle]').forEach(function (x) { x.setAttribute('aria-expanded', String(open)); });
      });
    });
    window.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && menu && menu.classList.contains('open')) $('[data-menu-toggle]').click();
    });
    // back from the page a menu link opened: the cached page must not come back with the menu open
    window.addEventListener('pageshow', function (e) {
      if (e.persisted && menu && menu.classList.contains('open')) $('[data-menu-toggle]').click();
    });

    $$('[data-copy]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var text = btn.getAttribute('data-copy');
        var done = function () {
          var was = btn.textContent;
          btn.textContent = 'copied';
          btn.classList.add('done');
          setTimeout(function () { btn.textContent = was; btn.classList.remove('done'); }, 1400);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, function () {});
        else {
          var t = doc.createElement('textarea'); t.value = text; doc.body.appendChild(t); t.select();
          try { doc.execCommand('copy'); done(); } catch (e) {}
          t.remove();
        }
      });
    });

    $$('[data-year]').forEach(function (el) { el.textContent = String(new Date().getFullYear()); });
  }

  /* ---------- logo spine redraw on hover ---------- */

  function setupLogo() {
    var lock = $('.lockup');
    if (!lock || reduced) return;
    var spine = lock.querySelector('[data-nav-spine]');
    lock.addEventListener('pointerenter', function () {
      if (!spine) return;
      var L = spine.getTotalLength();
      spine.style.transition = 'none';
      spine.style.strokeDasharray = L;
      spine.style.strokeDashoffset = L;
      void spine.getBoundingClientRect();
      spine.style.transition = 'stroke-dashoffset var(--d-el) var(--e-emph)';
      spine.style.strokeDashoffset = '0';
    });
  }

  /* ---------- reveal system ---------- */

  function prep(el) {
    var kind = el.dataset.rv;
    if (kind === 'card') el.style.opacity = '0';
    else if (kind === 'eye') { el.style.setProperty('--ew', '0px'); el.style.opacity = '0'; }
    else if (kind === 'media') el.style.clipPath = 'inset(0 0 100% 0)';
    else if (kind === 'rule') { el.style.transform = 'scaleX(0)'; el.style.transformOrigin = 'center'; }
    else if (kind === 'claim') $$('.ln > span', el).forEach(function (s) { s.style.transformOrigin = '0 100%'; s.style.transform = 'translate3d(0,115%,0) rotate(3deg)'; });
    else if (kind === 'num') {
      el.dataset.text = el.textContent;
      el.textContent = (el.dataset.prefix || '') + '0' + (el.dataset.suffix || '');
      var src = el.parentNode.querySelector('.num-s');
      if (src) src.style.opacity = '0';
    }
  }

  function reveal(el) {
    if (el.dataset.in === '1') return;
    el.dataset.in = '1';
    var kind = el.dataset.rv;
    var step = el.dataset.step === 'tight' ? 40 : 60;
    var d = Math.min(parseInt(el.dataset.i || '0', 10), 12) * step;
    var clear = function () { el.style.willChange = ''; };
    if (kind === 'eye') {
      el.style.transition = 'opacity var(--d-el) var(--e-edify) 120ms';
      void el.offsetWidth;
      el.style.opacity = '1';
      el.style.setProperty('--ew', '22px');
    } else if (kind === 'card') {
      el.style.willChange = 'opacity, filter, transform';
      el.style.animation = (small ? 'blurFadeUpSm' : 'blurFadeUp') + ' var(--d-section) var(--e-out) ' + d + 'ms both';
      el.addEventListener('animationend', function () { clear(); el.style.opacity = '1'; }, { once: true });
    } else if (kind === 'media') {
      el.style.willChange = 'clip-path';
      el.style.transition = 'clip-path var(--d-section) var(--e-emph) ' + d + 'ms';
      void el.offsetWidth;
      el.style.clipPath = 'inset(0 0 0% 0)';
      el.addEventListener('transitionend', clear, { once: true });
      // the picture inside settles as the frame opens: from a little large to exactly whole
      var pic = el.querySelector('video,img');
      if (pic && el.animate) pic.animate([{ transform: 'scale(1.1)' }, { transform: 'scale(1)' }], { duration: 1400, delay: d, easing: 'cubic-bezier(0.16,1,0.3,1)', fill: 'backwards' });
    } else if (kind === 'rule') {
      el.style.willChange = 'transform';
      el.style.transition = 'transform var(--d-section) var(--e-out)';
      void el.offsetWidth;
      el.style.transform = 'scaleX(1)';
      el.addEventListener('transitionend', clear, { once: true });
    } else if (kind === 'claim') {
      var lines = $$('.ln > span', el);
      void el.offsetWidth;
      lines.forEach(function (s, n) {
        s.style.willChange = 'transform';
        s.style.transition = 'transform 1100ms var(--e-out) ' + (n * 95) + 'ms';
        s.style.transform = 'translate3d(0,0,0) rotate(0deg)';
        s.addEventListener('transitionend', function () { s.style.willChange = ''; }, { once: true });
      });
    } else if (kind === 'num') {
      var src = el.parentNode.querySelector('.num-s');
      if (S.rafDead) {
        el.textContent = el.dataset.text;
        if (src) { src.style.transition = 'opacity var(--d-el) var(--e-edify)'; src.style.opacity = '1'; }
      } else {
        S.counters.push({ el: el, target: parseFloat(el.dataset.value || '0'), dec: parseInt(el.dataset.dec || '0', 10), t0: 0, dur: 900, delay: d, src: src });
      }
    }
  }

  function setupReveal() {
    // eyebrows draw their hairline in as they arrive
    $$('.eyebrow:not(.bare):not([data-rv])').forEach(function (e) { e.setAttribute('data-rv', 'eye'); });
    var els = $$('[data-rv]');
    if (reduced) { S.pending = []; return; }
    els.forEach(prep);
    S.pending = els;
    sweep();
  }

  function sweep() {
    var vh = window.innerHeight;
    if (S.pending.length) {
      var rest = [];
      for (var i = 0; i < S.pending.length; i++) {
        var el = S.pending[i];
        if (el.getBoundingClientRect().top < vh * 0.92) reveal(el); else rest.push(el);
      }
      S.pending = rest;
    }
    if (!S.barsDone) {
      var bars = $$('[data-bar]');
      if (bars.length && bars[0].getBoundingClientRect().top < vh * 0.88 && bars[0].offsetParent) {
        S.barsDone = true;
        if (!reduced) bars.forEach(function (b, i) {
          b.style.transform = 'scaleX(0)';
          b.style.willChange = 'transform';
          void b.offsetWidth;
          b.style.transition = 'transform var(--d-section) var(--e-edify) ' + (i * 60) + 'ms';
          b.style.transform = 'scaleX(1)';
          b.addEventListener('transitionend', function () { b.style.willChange = ''; }, { once: true });
        });
      }
    }
    S.terms.forEach(function (t) {
      if (!t.done && t.host.getBoundingClientRect().top < vh * 0.85 && t.host.offsetParent) { t.done = true; runTerminal(t); }
    });
  }

  /* ---------- terminals: the lines are real output, already in the HTML ---------- */

  function setupTerminals() {
    S.terms = $$('[data-term]').map(function (host) {
      var lines = $$('.l', host);
      if (!reduced) lines.forEach(function (l) { l.style.opacity = '0'; });
      return { host: host, lines: lines, done: reduced };
    });
  }

  function runTerminal(t) {
    var caret = doc.createElement('span');
    caret.className = 'caret';
    var step = function (i) {
      if (i >= t.lines.length) { var last = t.lines[t.lines.length - 1]; if (last) last.appendChild(caret); return; }
      var ln = t.lines[i];
      ln.style.transition = 'opacity 160ms linear';
      ln.style.opacity = '1';
      var c = ln.classList;
      var wait = ln.textContent.trim() === '' ? 60 : (c.contains('cmd') ? 380 : (c.contains('dim') ? 220 : 150));
      setTimeout(function () { step(i + 1); }, wait);
    };
    step(0);
  }

  /* ---------- tabs (matrix) ---------- */

  function setupTabs() {
    $$('[data-tabs]').forEach(function (group) {
      var btns = $$('[role="tab"]', group);
      var body = $('#' + group.getAttribute('data-tabs'));
      btns.forEach(function (b, i) {
        b.addEventListener('click', function () { select(i); });
        b.addEventListener('keydown', function (e) {
          if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
            e.preventDefault();
            var n = (i + (e.key === 'ArrowRight' ? 1 : btns.length - 1)) % btns.length;
            select(n); btns[n].focus();
          }
        });
      });
      function select(i) {
        if (btns[i].getAttribute('aria-selected') === 'true') return;
        btns.forEach(function (b, n) {
          b.setAttribute('aria-selected', String(n === i));
          b.tabIndex = n === i ? 0 : -1;
          var p = doc.getElementById(b.getAttribute('aria-controls'));
          if (p) p.hidden = n !== i;
        });
        if (!body || reduced) return;
        body.style.animation = 'none';
        void body.offsetWidth;
        body.style.willChange = 'clip-path';
        body.style.animation = 'edWipe var(--d-el) var(--e-edify) both';
        body.addEventListener('animationend', function () { body.style.willChange = ''; }, { once: true });
        var panel = doc.getElementById(btns[i].getAttribute('aria-controls'));
        $$('.row', panel).forEach(function (r, n) {
          r.style.opacity = '0';
          r.style.transition = 'opacity var(--d-el) var(--e-edify) ' + (n * 40) + 'ms';
          void r.offsetWidth;
          r.style.opacity = '1';
        });
      }
    });
  }

  /* ---------- FAQ: one open at a time is not enforced; smooth reveal only ---------- */

  function setupFaq() {
    if (reduced) return;
    $$('.faq details').forEach(function (d) {
      d.addEventListener('toggle', function () {
        if (!d.open) return;
        var a = d.querySelector('.ans');
        if (a) { a.style.animation = 'none'; void a.offsetWidth; a.style.animation = 'blurFadeUpSm var(--d-el) var(--e-out) both'; }
      });
    });
  }

  /* ---------- boot ---------- */

  function setupBoot() {
    if (!root.hasAttribute('data-boot')) return;
    clearTimeout(window.__edBootFallback);
    S.bootStart = performance.now();
    var grid = $('.boot-grid');
    if (grid) { grid.style.transition = 'opacity 700ms var(--e-out)'; void grid.offsetWidth; grid.style.opacity = '1'; }
    $$('[data-boot-draw]').forEach(function (draw, i) {
      var L = draw.getTotalLength();
      draw.style.strokeDasharray = L;
      draw.style.strokeDashoffset = L;
      draw.style.transition = 'stroke-dashoffset 1500ms var(--e-emph) ' + (i * 260) + 'ms';
      void draw.getBoundingClientRect();
      draw.style.strokeDashoffset = '0';
    });
    var word = $('.boot-word');
    if (word) {
      word.style.transition = 'opacity 800ms var(--e-out) 900ms, letter-spacing 1200ms var(--e-emph) 900ms';
      word.style.letterSpacing = '0.24em';
      void word.offsetWidth;
      word.style.opacity = '1';
      word.style.letterSpacing = '0.02em';
    }
    var log = $('#ed-boot-log');
    var steps = ['reading every file', 'building the map', 'mirroring skills into each runtime', 'next: /spec'];
    if (log) steps.forEach(function (s, i) {
      setTimeout(function () {
        if (S.booted) return;
        var d = doc.createElement('div');
        d.textContent = s;
        d.style.cssText = 'opacity:0;transition:opacity 240ms linear;color:' + (i === steps.length - 1 ? 'var(--ed-blue-bright)' : 'var(--ed-text-3)');
        log.appendChild(d);
        void d.offsetWidth;
        d.style.opacity = '1';
        while (log.children.length > 3) log.removeChild(log.firstChild);
      }, 420 + i * 460);
    });
    S.bootCap = setTimeout(function () { endBoot(); }, 2600);
    var skip = function () { endBoot(); };
    window.addEventListener('keydown', skip, { once: true });
    window.addEventListener('pointerdown', skip, { once: true });
    Promise.all([
      doc.fonts ? doc.fonts.ready : Promise.resolve(),
      new Promise(function (res) { S.firstFrameResolve = res; setTimeout(res, 1200); })
    ]).then(function () {
      var wait = Math.max(0, 2000 - (performance.now() - S.bootStart));
      S.bootReady = setTimeout(endBoot, wait);
    });
  }

  function endBoot() {
    if (S.booted) return;
    S.booted = true;
    clearTimeout(S.bootCap);
    clearTimeout(S.bootReady);
    try { sessionStorage.setItem('ed:boot', '1'); } catch (e) {}
    var ov = $('#ed-boot'), bm = $('#ed-boot-mark'), nm = $('.lockup svg');
    var done = function () { root.removeAttribute('data-boot'); if (nm) nm.style.opacity = ''; };
    if (!ov || !bm || !nm) { done(); return; }
    $$('.boot-hide,.boot-word,.boot-grid', ov).forEach(function (e) { e.style.transition = 'opacity 260ms linear'; e.style.opacity = '0'; });
    var bg = $('.boot-bg', ov);
    if (bg) { bg.style.transition = 'opacity var(--d-flip) var(--e-in-out)'; bg.style.opacity = '0'; }
    var a = bm.getBoundingClientRect(), b = nm.getBoundingClientRect();
    nm.style.opacity = '0';
    var anim = bm.animate ? bm.animate(
      [{ transform: 'none' }, { transform: 'translate(' + (b.left - a.left) + 'px, ' + (b.top - a.top) + 'px) scale(' + (b.width / a.width) + ')' }],
      { duration: 700, easing: 'cubic-bezier(0.22,1,0.36,1)', fill: 'forwards' }) : null;
    if (anim && anim.finished) anim.finished.then(done).catch(done); else setTimeout(done, 700);
  }

  /* ---------- gallery ---------- */

  function setupGallery() {
    var track = $('#ed-track');
    S.frames = [];
    if (!track) return;
    var frames = S.frames = $$('[data-frame]', track);
    var count = $('#ed-gallery-count'), bar = $('#ed-gallery-bar');
    var fine = window.matchMedia('(hover:hover) and (pointer:fine)').matches;
    var pad = function (n) { return ('0' + n).slice(-2); };
    var sync = function () {
      var max = track.scrollWidth - track.clientWidth;
      var p = max > 0 ? track.scrollLeft / max : 0;
      var idx = Math.min(frames.length, Math.max(1, Math.round(p * (frames.length - 1)) + 1));
      if (count) count.textContent = pad(idx) + ' / ' + pad(frames.length);
      if (bar) bar.style.width = (100 / frames.length + p * (100 - 100 / frames.length)) + '%';
    };
    track.addEventListener('scroll', sync, { passive: true });
    sync();
    frames.forEach(function (f) {
      var img = f.querySelector('img,video');
      var on = function () { if (img) img.style.filter = 'grayscale(0)'; };
      var off = function () { if (img) img.style.filter = 'grayscale(1)'; };
      f.addEventListener('focus', function () {
        on();
        f.style.borderColor = 'var(--ed-blue)';
        f.style.background = 'var(--ed-plate)';
        var r = f.getBoundingClientRect(), t = track.getBoundingClientRect();
        track.scrollLeft += (r.left - t.left) - (t.width - r.width) / 2;
      });
      f.addEventListener('blur', function () { off(); f.style.borderColor = ''; f.style.background = ''; f.dataset.mag = ''; });
      f.addEventListener('pointerenter', on);
      f.addEventListener('pointerleave', function () { off(); f.dataset.mag = ''; });
      f.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); expand(f); } });
      f.addEventListener('click', function () { expand(f); });
      if (fine && !reduced) f.addEventListener('pointermove', function (e) {
        var r = f.getBoundingClientRect();
        var dx = (e.clientX - r.left) / r.width - 0.5, dy = (e.clientY - r.top) / r.height - 0.5;
        f.dataset.mag = 'translate3d(' + (dx * 14) + 'px,' + (dy * 14) + 'px,0) rotateX(' + (-dy * 6) + 'deg) rotateY(' + (dx * 6) + 'deg)';
      });
    });
    track.style.perspective = '1200px';
  }

  function expand(frame) {
    var body = frame.lastElementChild;
    if (!body) return;
    frame.setAttribute('aria-expanded', frame.dataset.open === '1' ? 'false' : 'true');
    if (frame.dataset.open === '1') {
      frame.dataset.open = '';
      frame.style.flexBasis = '';
      var extra = frame.querySelector('[data-detail]');
      if (extra) extra.remove();
      return;
    }
    frame.dataset.open = '1';
    var first = frame.getBoundingClientRect();
    frame.style.flexBasis = 'clamp(320px,52vw,660px)';
    var last = frame.getBoundingClientRect();
    if (!reduced && frame.animate) {
      frame.style.willChange = 'transform';
      var anim = frame.animate(
        [{ transform: 'scaleX(' + (first.width / last.width) + ')', transformOrigin: 'left center' }, { transform: 'scaleX(1)', transformOrigin: 'left center' }],
        { duration: 420, easing: 'cubic-bezier(0.22,1,0.36,1)' });
      if (anim && anim.finished) anim.finished.then(function () { frame.style.willChange = ''; }).catch(function () {});
    }
    var d = doc.createElement('div');
    d.setAttribute('data-detail', '');
    d.textContent = frame.getAttribute('data-detail-text') || 'Click again to collapse.';
    body.appendChild(d);
  }

  /* ---------- canvas field: grille on the home hero, particle field elsewhere ---------- */

  function setupField() {
    var c = $('#ed-field');
    S.canvas = c || null;
    if (!c) return;
    S.ctx = c.getContext('2d');
    S.mode = c.dataset.mode || 'grille';
    S.spin = 0;
    sizeField();
    var base = S.mode === 'field' ? 1500 : 620;
    var n = S.pcount = Math.round(window.innerWidth < 560 ? base * 0.45 : base);
    S.pts = new Float32Array(n * 4);
    for (var i = 0; i < n; i++) spawnPt(i);
    S.fieldVisible = true;
    if (reduced) drawField(0, 0);
  }

  function sizeField() {
    var c = S.canvas;
    if (!c) return;
    var r = c.getBoundingClientRect();
    S.W = Math.max(1, Math.round(r.width));
    S.H = Math.max(1, Math.round(r.height));
    var d = Math.min(2, window.devicePixelRatio || 1);
    d = Math.max(1, Math.min(d, 4096 / Math.max(S.W, S.H), Math.sqrt(4200000 / (S.W * S.H))));
    c.width = Math.round(S.W * d);
    c.height = Math.round(S.H * d);
    S.ctx.setTransform(c.width / S.W, 0, 0, c.height / S.H, 0, 0);
    var vh = window.innerHeight;
    S.cx = S.W > 980 ? S.W * 0.7 : S.W * 0.5;
    S.cy = Math.min(S.H * 0.5, vh * 0.5);
    S.R = Math.round(Math.min(S.W * 0.4, vh * 0.46) * 0.46);
    var lab = $('#ed-ceiling-label');
    if (lab) { lab.style.top = (S.cy - S.R - 14) + 'px'; lab.style.left = S.cx + 'px'; }
  }

  function spawnPt(i) {
    var a = Math.random() * Math.PI * 2;
    var R = S.R || 100;
    var r = R * (2.4 + Math.random() * 3.2);
    var s = Math.sqrt(0.55 * R / r) * (0.7 + Math.random() * 0.6);
    S.pts[i * 4] = Math.cos(a) * r;
    S.pts[i * 4 + 1] = Math.sin(a) * r;
    S.pts[i * 4 + 2] = -Math.sin(a) * s;
    S.pts[i * 4 + 3] = Math.cos(a) * s;
  }

  function warp(x, y) {
    var dx = x - S.cx, dy = y - S.cy;
    var r = Math.sqrt(dx * dx + dy * dy);
    if (r < 0.001) return [x, y];
    var R = S.R, rr;
    if (r <= R) rr = r; else { var o = r - R; rr = R + o / (1 + o / (R * 2.0)); }
    var k = rr / r;
    return [S.cx + dx * k, S.cy + dy * k];
  }

  function drawField(t, v) {
    var ctx = S.ctx;
    if (!ctx) return;
    var W = S.W, H = S.H, R = S.R, i, x, y;
    S.spin = (S.spin || 0) + 0.0006 + (v || 0) * 0.00035;
    if (S.mode === 'field') {
      ctx.globalCompositeOperation = 'source-over';
      ctx.fillStyle = 'rgba(7,9,12,0.20)';
      ctx.fillRect(0, 0, W, H);
    } else {
      ctx.clearRect(0, 0, W, H);
      var pitch = 56, grid = new Path2D(), off = (S.spin * 40) % pitch, span = 4.4 * R;
      var yTop = Math.max(-H * 0.2, S.cy - span), yBot = Math.min(H * 1.2, S.cy + span), started, p;
      for (x = -pitch * 2 - off; x < W + pitch * 2; x += pitch) {
        started = false;
        for (y = yTop; y <= yBot; y += 14) { p = warp(x, y); if (!started) { grid.moveTo(p[0], p[1]); started = true; } else grid.lineTo(p[0], p[1]); }
      }
      for (y = S.cy - Math.ceil(span / pitch) * pitch + off; y < S.cy + span; y += pitch) {
        started = false;
        for (x = -W * 0.15; x <= W * 1.15; x += 14) { p = warp(x, y); if (!started) { grid.moveTo(p[0], p[1]); started = true; } else grid.lineTo(p[0], p[1]); }
      }
      ctx.lineWidth = 1;
      ctx.strokeStyle = 'rgba(232,236,242,0.05)';
      ctx.stroke(grid);
      ctx.save();
      ctx.beginPath();
      ctx.arc(S.cx, S.cy, R * 2.7, 0, Math.PI * 2);
      ctx.clip();
      ctx.strokeStyle = 'rgba(90,147,245,0.055)';
      ctx.stroke(grid);
      ctx.restore();
    }
    if (S.mode === 'field') ctx.globalCompositeOperation = 'lighter';
    var n = S.pcount, soft = R * R * 0.25;
    for (i = 0; i < n; i++) {
      var o = i * 4;
      x = S.pts[o]; y = S.pts[o + 1];
      var vx = S.pts[o + 2], vy = S.pts[o + 3];
      var r2 = x * x + y * y, r = Math.sqrt(r2) || 1;
      var a = -(R * 0.9) / (r2 + soft);
      vx += a * (x / r) * 6; vy += a * (y / r) * 6;
      x += vx; y += vy;
      if (r < R * 0.98) { spawnPt(i); continue; }
      S.pts[o] = x; S.pts[o + 1] = y; S.pts[o + 2] = vx; S.pts[o + 3] = vy;
      var px = S.cx + x, py = S.cy + y;
      if (px < -20 || px > W + 20 || py < -20 || py > H + 20) continue;
      var near = Math.max(0, 1 - (r - R) / (R * 2.6));
      if (S.mode === 'field') {
        ctx.fillStyle = 'rgba(90,147,245,' + (0.07 + near * 0.26) + ')';
        ctx.fillRect(px, py, 1.5, 1.5);
      } else {
        var sp = Math.sqrt(vx * vx + vy * vy) || 1;
        ctx.strokeStyle = 'rgba(232,236,242,' + (0.06 + near * 0.26) + ')';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(px, py);
        ctx.lineTo(px + (vx / sp) * 3.4, py + (vy / sp) * 3.4);
        ctx.stroke();
      }
    }
    ctx.globalCompositeOperation = 'source-over';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(S.cx, S.cy, R, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(90,147,245,' + (0.5 + 0.18 * Math.sin(t / 900)) + ')';
    ctx.stroke();
    ctx.setLineDash([2, 6]);
    ctx.beginPath();
    ctx.arc(S.cx, S.cy, Math.round(R * 1.34), 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(232,236,242,0.10)';
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.moveTo(S.cx - R - 13, S.cy); ctx.lineTo(S.cx - R + 13, S.cy);
    ctx.moveTo(S.cx + R - 13, S.cy); ctx.lineTo(S.cx + R + 13, S.cy);
    ctx.strokeStyle = 'rgba(90,147,245,0.55)';
    ctx.stroke();
    if (S.firstFrameResolve) { var f = S.firstFrameResolve; S.firstFrameResolve = null; f(); }
  }

  /* ---------- measure ---------- */

  function measure() {
    var inner = $('#ed-marquee-inner');
    if (inner) { var s = inner.querySelector('.strip'); S.stripW = s ? s.getBoundingClientRect().width : 0; }
    S.stackCards = $$('.stack-card');
    S.stackCards.forEach(function (c, i) { c.style.top = (66 + 20 + i * 12) + 'px'; c.style.zIndex = String(i + 1); });
    S.meterCard = $('#ed-meter-card');
    S.meterFill = $('#ed-meter-fill');
    S.meterValue = $('#ed-meter-value');
    S.meterPhase = $('#ed-meter-phase');
    S.meterFile = $('#ed-meter-file');
    S.phaseCells = $$('[data-phase]');
  }

  /* meter: the six phases, and the file each one leaves behind */
  var PHASES = [
    { name: 'brief', file: 'your words', note: 'a paragraph, not a prompt' },
    { name: 'spec', file: 'specs/&lt;f&gt;/spec.md', note: 'ends at a human' },
    { name: 'plan', file: 'specs/&lt;f&gt;/plan.md', note: 'ends at a human' },
    { name: 'tasks', file: 'specs/&lt;f&gt;/tasks.md', note: 'ends at a human' },
    { name: 'build', file: 'a diff + green suite', note: 'cheapest model that follows' },
    { name: 'verify', file: 'verification.md', note: 'a session that wrote no code' }
  ];

  function tickMeter() {
    if (!S.meterFill || !S.meterCard) return;
    var cr = S.meterCard.getBoundingClientRect();
    if (!(cr.bottom > 0 && cr.top < window.innerHeight)) return;
    S.meterT += 0.0032;
    var cycle = S.meterT % 6, phase = Math.floor(cycle), local = cycle - phase;
    var rise = 1 - Math.pow(1 - Math.min(1, local / 0.7), 3);
    var val = ((phase + rise) / 6) * 100;
    S.meterFill.style.width = val.toFixed(1) + '%';
    if (S._phase !== phase) {
      S._phase = phase;
      var ph = PHASES[phase];
      S.meterValue.innerHTML = (phase + 1) + '<small>/6</small>';
      S.meterPhase.textContent = ph.name;
      S.meterFile.innerHTML = ph.file + '<br><span>' + ph.note + '</span>';
      S.phaseCells.forEach(function (c, i) {
        c.style.color = i === phase ? 'var(--ed-text-1)' : (i < phase ? 'var(--ed-text-3)' : 'var(--ed-text-4)');
        c.style.background = i === phase ? 'var(--ed-plate)' : 'var(--ed-panel)';
      });
    }
  }

  function staticScroll() {
    if (S.stackCards && S.stackCards.length > 1 && window.innerWidth > 720) {
      for (var i = 0; i < S.stackCards.length - 1; i++) {
        var cur = S.stackCards[i], nxt = S.stackCards[i + 1];
        var cr = cur.getBoundingClientRect(), nr = nxt.getBoundingClientRect();
        var overlap = Math.max(0, Math.min(1, (cr.bottom - nr.top) / Math.max(1, cr.height)));
        cur.style.transform = 'scale(' + (1 - overlap * 0.04).toFixed(4) + ')';
        cur.style.opacity = String(1 - overlap * 0.45);
      }
    }
  }

  // the hairline under the header fills as the page is read
  function progress(y) {
    if (!S.header) S.header = $('.site-header');
    var max = doc.documentElement.scrollHeight - window.innerHeight;
    var k = max > 0 ? Math.min(1, Math.max(0, y / max)) : 0;
    if (S.header && Math.abs(k - (S.pk == null ? -1 : S.pk)) > 0.001) { S.pk = k; S.header.style.setProperty('--sp', k.toFixed(4)); }
  }

  function noRaf() {
    S.rafDead = true;
    if (S.canvas) drawField(0, 0);
    S.counters.forEach(function (c) {
      c.el.textContent = c.el.dataset.text;
      if (c.src) { c.src.style.transition = 'opacity var(--d-el) var(--e-edify)'; c.src.style.opacity = '1'; }
    });
    S.counters = [];
  }

  /* ---------- the one rAF loop ---------- */

  function tick(t) {
    if (S.hidden) return;
    S.n++;
    if (S.n % 3 === 0) {
      sweep();
      if (S.canvas) {
        var cr = S.canvas.getBoundingClientRect();
        S.fieldVisible = cr.bottom > 0 && cr.top < window.innerHeight;
        if (Math.abs(Math.round(cr.width) - S.W) > 1 || Math.abs(Math.round(cr.height) - S.H) > 1) sizeField();
      }
    }
    var y = window.scrollY, raw = y - S.lastY;
    progress(y);
    S.lastY = y;
    S.vel += (Math.max(-60, Math.min(60, raw)) - S.vel) * 0.12;
    var v = S.vel;

    if (S.canvas && S.fieldVisible) {
      var t0 = performance.now();
      drawField(t, v);
      if (S.frameTimes.length < 30) {
        S.frameTimes.push(performance.now() - t0);
        if (S.frameTimes.length === 30) {
          var avg = S.frameTimes.reduce(function (a, b) { return a + b; }, 0) / 30;
          if (avg > 9 && S.pcount > 300) S.pcount = Math.round(S.pcount * 0.4);
        }
      }
    }

    if (S.frames && S.frames.length) {
      var target = Math.max(-12, Math.min(12, v * 0.35));
      S.skew += (target - S.skew) * 0.1;
      if (Math.abs(S.skew) < 0.02) S.skew = 0;
      var sy = 1 - Math.abs(S.skew) * 0.004;
      for (var i = 0; i < S.frames.length; i++) {
        var f = S.frames[i];
        f.style.transform = (f.dataset.mag || '') + ' skewX(' + S.skew.toFixed(3) + 'deg) scaleY(' + sy.toFixed(4) + ')';
      }
    }

    var inner = $('#ed-marquee-inner');
    if (inner && S.stripW) {
      if (Math.abs(v) > 0.4) S.dir = v > 0 ? 1 : -1;
      S.marqueeOffset = (S.marqueeOffset + 0.35 * S.dir + v * 0.8) % S.stripW;
      if (S.marqueeOffset < 0) S.marqueeOffset += S.stripW;
      inner.style.transform = 'translate3d(' + (-S.marqueeOffset) + 'px,0,0)';
    }

    tickMeter();
    staticScroll();

    for (var k = S.counters.length - 1; k >= 0; k--) {
      var c = S.counters[k];
      if (!c.t0) { c.t0 = t + c.delay; continue; }
      var e = t - c.t0;
      if (e < 0) continue;
      var q = Math.min(1, e / c.dur);
      var val = c.target * (1 - Math.pow(1 - q, 3));
      c.el.textContent = (c.el.dataset.prefix || '') + (c.dec ? val.toFixed(c.dec) : Math.round(val).toLocaleString('en-US')) + (c.el.dataset.suffix || '');
      if (q >= 1) {
        c.el.textContent = c.el.dataset.text;
        if (c.src) (function (src) { setTimeout(function () { src.style.transition = 'opacity var(--d-el) var(--e-edify)'; src.style.opacity = '1'; }, 200); })(c.src);
        S.counters.splice(k, 1);
      }
    }
  }

  /* ---------- films: header loops and page films ----------
     Loops carry no autoplay attribute, so without this file, under reduced motion
     or with save-data on, the poster is what shows. Otherwise a loop plays muted
     only while it is on screen and the tab is visible. */

  var play = function (v) { var p = v.play(); if (p && p.catch) p.catch(function () {}); };
  var stillMotion = function () { var conn = navigator.connection; return reduced || !!(conn && conn.saveData); };

  // a loop (header loop or clip) plays muted, from the first frame it is on screen, and
  // repeats; it pauses when it scrolls away or the tab hides
  function watchLoop(v) {
    v.muted = true;
    v.loop = true;
    v.playsInline = true;
    if (stillMotion() || v.dataset.watched) return;
    v.dataset.watched = '1';
    if (!('IntersectionObserver' in window)) { v.dataset.on = '1'; play(v); return; }
    new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        v.dataset.on = e.isIntersecting ? '1' : '';
        if (e.isIntersecting && !doc.hidden) play(v); else v.pause();
      });
    }, { threshold: 0.05, rootMargin: '120px 0px' }).observe(v);
  }

  function setupFilms() {
    var loops = $$('video[data-loop]');
    loops.forEach(watchLoop);
    if (!stillMotion() && loops.length) doc.addEventListener('visibilitychange', function () {
      $$('video[data-loop]').forEach(function (v) {
        if (doc.hidden) v.pause();
        else if (v.dataset.on === '1') play(v);
      });
    });

    $$('[data-film]').forEach(setupFilm);
  }

  var esc = function (x) { return String(x).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };

  /* a page film. It waits until its section has arrived (most of the frame on screen),
     opens its frame and shows its details, then rolls from the first frame and repeats
     for as long as it stays there. Leaving resets it, so every arrival starts at 0:00.
     There is no player chrome; a click, Enter or Space pauses and resumes it. */
  function setupFilm(fig) {
    var v = $('video', fig);
    if (!v) return;
    var pad = function (n) { return ('0' + n).slice(-2); };
    var clock = function (t) { t = Math.max(0, Math.floor(t || 0)); return Math.floor(t / 60) + ':' + pad(t % 60); };
    var dur = parseFloat(fig.dataset.dur) || 0;
    var ch = [];
    try { ch = JSON.parse(fig.dataset.chapters || '[]'); } catch (e) {}
    if (!ch.length) ch = [[0, fig.dataset.name || 'Film']];
    var marks = ch.map(function (c) { return +c[0]; });

    // the frame holds the video and, for the arrival, the title card over it
    var frame = doc.createElement('div');
    frame.className = 'film-frame';
    v.parentNode.insertBefore(frame, v);
    frame.appendChild(v);
    var card = doc.createElement('div');
    card.className = 'film-card';
    card.setAttribute('aria-hidden', 'true');
    card.innerHTML = '<span class="k">EDIFY / Film ' + esc(fig.dataset.no || '') + ' &middot; ' + esc(fig.dataset.name || '') +
      ' &middot; ' + dur + ' s &middot; no sound &middot; loops</span><span class="t">' + esc(ch[0][1]) + '</span><ol>' +
      ch.map(function (c, i) { return '<li style="--i:' + i + '"><b>' + pad(i + 1) + '</b><span>' + esc(c[1]) + '</span><em>' + clock(c[0]) + '</em></li>'; }).join('') + '</ol>';
    frame.appendChild(card);

    // the readout under the frame: which chapter, how far through each, the time
    var ro = doc.createElement('div');
    ro.className = 'film-ro';
    ro.innerHTML = '<span class="n"></span><span class="c"></span><span class="tk">' + ch.map(function (c, i) {
      var end = i + 1 < ch.length ? ch[i + 1][0] : dur;
      return '<button type="button" style="flex:' + Math.max(0.5, end - c[0]).toFixed(2) + '" aria-label="Chapter ' + (i + 1) + ', ' + esc(c[1]) + ', at ' + clock(c[0]) + '"><i></i></button>';
    }).join('') + '</span><span class="tc"></span>';
    frame.insertAdjacentElement('afterend', ro);
    var segs = $$('.tk button', ro), nEl = $('.n', ro), cEl = $('.c', ro), tc = $('.tc', ro), cur = -1;

    function update() {
      var t = v.currentTime || 0, D = isFinite(v.duration) && v.duration ? v.duration : dur, i = 0;
      for (var k = 0; k < marks.length; k++) if (t + 0.05 >= marks[k]) i = k;
      segs.forEach(function (sg, k) {
        var a = marks[k], z = k + 1 < marks.length ? marks[k + 1] : D;
        sg.style.setProperty('--f', (t >= z ? 1 : t <= a ? 0 : (t - a) / (z - a)).toFixed(3));
        if (k === i) sg.setAttribute('aria-current', 'true'); else sg.removeAttribute('aria-current');
      });
      if (i !== cur) {
        cur = i;
        nEl.textContent = pad(i + 1) + ' / ' + pad(ch.length);
        cEl.textContent = ch[i][1];
        if (!reduced) { cEl.style.animation = 'none'; void cEl.offsetWidth; cEl.style.animation = 'edWipe var(--d-el) var(--e-edify) both'; }
      }
      tc.textContent = clock(t) + ' / ' + clock(D);
    }
    var raf = 0;
    var spin = function () { update(); raf = v.paused ? 0 : requestAnimationFrame(spin); };
    v.addEventListener('playing', function () { fig.setAttribute('data-playing', ''); if (!raf) raf = requestAnimationFrame(spin); });
    v.addEventListener('seeked', update);
    v.addEventListener('loadedmetadata', update);
    update();

    var arrived = false, timer = 0;
    var toStart = function () { try { if (v.readyState >= 1 && v.currentTime) v.currentTime = 0; } catch (e) {} };
    v.addEventListener('pause', function () {
      fig.removeAttribute('data-playing');
      if (!v._ours && arrived) { v._held = true; fig.setAttribute('data-held', ''); }   // the viewer paused it: leave it paused
      v._ours = false;
    });
    // endless: loop is set, and if a server cannot seek, the end starts it over anyway
    v.addEventListener('ended', function () {
      if (v._held || !arrived) return;
      if (v.seekable && v.seekable.length) { v.currentTime = 0; play(v); }
      else { v.load(); play(v); }
    });
    var toggle = function () {
      if (v.paused) { v._held = false; fig.removeAttribute('data-held'); fig.classList.add('rolling'); play(v); }
      else v.pause();
    };
    v.addEventListener('click', toggle);
    v.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } });
    segs.forEach(function (sg, i) {
      sg.addEventListener('click', function () {
        var go = function () { v._held = false; fig.removeAttribute('data-held'); fig.classList.add('rolling'); v.currentTime = marks[i]; play(v); update(); };
        if (v.readyState >= 1) go();
        else { v.preload = 'auto'; v.addEventListener('loadedmetadata', go, { once: true }); v.load(); }
      });
    });

    if (!v.hasAttribute('data-auto') || stillMotion() || !('IntersectionObserver' in window)) return;
    v.muted = true;
    fig.classList.add('waiting');

    function arrive() {
      if (arrived) return;
      arrived = true;
      toStart(); update();
      fig.classList.remove('waiting');
      fig.classList.add('arrive');
      clearTimeout(timer);
      // the details hold for a beat, then clear as the film rolls from 0:00
      timer = setTimeout(function () {
        fig.classList.add('rolling');
        if (!v._held && !doc.hidden) { toStart(); play(v); }
      }, 1700);
    }
    function depart() {
      if (!arrived) return;
      arrived = false;
      clearTimeout(timer);
      fig.classList.remove('arrive', 'rolling');
      fig.classList.add('waiting');
      v._held = false; fig.removeAttribute('data-held');
      if (!v.paused) { v._ours = true; v.pause(); }
      toStart(); update();
    }
    // load ahead, so the first frame is there when the section arrives
    new IntersectionObserver(function (es) {
      if (es[0].isIntersecting && v.preload !== 'auto') { v.preload = 'auto'; v.load(); }
    }, { rootMargin: '700px 0px' }).observe(frame);
    // once the film is here, show its own first frame rather than the poster (a frame from
    // the middle), so what waits is exactly what will roll
    v.addEventListener('loadeddata', function () { if (!v.currentTime) v.removeAttribute('poster'); }, { once: true });
    new IntersectionObserver(function (es) {
      var e = es[0], r = e.boundingClientRect, vh = window.innerHeight;
      var here = e.isIntersecting && (e.intersectionRatio >= 0.72 || (r.top <= vh * 0.2 && r.bottom >= vh * 0.62));
      if (here) arrive();
      else if (!e.isIntersecting || e.intersectionRatio < 0.25) depart();
    }, { threshold: [0, 0.1, 0.25, 0.4, 0.55, 0.62, 0.72, 0.85, 1] }).observe(frame);
    doc.addEventListener('visibilitychange', function () {
      if (doc.hidden && !v.paused) { v._ours = true; v.pause(); }
      else if (!doc.hidden && arrived && fig.classList.contains('rolling') && !v._held) play(v);
    });
  }

  /* ---------- the stage: live ink on the home hero ----------
     ink.js draws the stage live when WebGL2 is there and motion is welcome, and the
     pointer becomes one more drop of ink. If the GPU cannot hold the frame rate the
     canvas steps down in resolution, then hands over to the rendered loop. */

  function setupInk() {
    var cv = $('canvas[data-ink]');
    if (!cv) return;
    var stage = cv.closest('[data-stage]') || cv.parentNode;
    var vid = $('video.stage-media', stage);
    if (stillMotion() || !window.EdInk || !EdInk.supported()) { cv.remove(); return; }
    if (vid) vid.removeAttribute('data-loop');
    var fallback = function () {
      if (S.ink) { S.ink.dead = true; try { S.ink.p.destroy(); } catch (e) {} }
      cv.remove();
      stage.classList.remove('live');
      if (vid) { vid.setAttribute('data-loop', ''); watchLoop(vid); }
    };
    var dpr = Math.min(window.devicePixelRatio || 1, 1.5), q = 1;
    var size = function () {
      var r = stage.getBoundingClientRect(), k = Math.min(dpr * q, 2560 / Math.max(1, r.width));
      return [Math.max(2, Math.round(r.width * k)), Math.max(2, Math.round(r.height * k))];
    };
    var wh = size();
    cv.width = wh[0]; cv.height = wh[1];
    EdInk.create(cv, cv.dataset.ink, { live: true, intro: true }).then(function (p) {
      var I = S.ink = { p: p, on: true, t0: performance.now(), times: [], waitBoot: true, dead: false, n: 0,
        dial: $('[data-dial]', stage), ph: $('[data-ph]', stage), xy: $('[data-xy]', stage) };
      var sgn = function (v) { return (v < 0 ? '\u2212' : '+') + Math.abs(v).toFixed(3); };
      new IntersectionObserver(function (es) { I.on = es[0].isIntersecting; if (I.on) frame(performance.now()); }, { threshold: 0 }).observe(stage);
      var toFrame = function (e) {
        var r = stage.getBoundingClientRect();
        return [(e.clientX - r.left - r.width / 2) / r.height, (e.clientY - r.top - r.height / 2) / r.height];
      };
      stage.addEventListener('pointermove', function (e) {
        var f = toFrame(e);
        p.pointer(f[0], f[1], true);
        if (I.xy) I.xy.textContent = 'x ' + sgn(f[0]) + '  y ' + sgn(-f[1]);
        if (!I.touched) { I.touched = true; setTimeout(function () { stage.classList.add('touched'); }, 1600); }
      });
      stage.addEventListener('pointerleave', function () { p.pointer(null, null, false); });
      stage.addEventListener('pointerup', function (e) { if (e.pointerType !== 'mouse') p.pointer(null, null, false); });
      window.addEventListener('resize', function () {
        clearTimeout(I.rt);
        I.rt = setTimeout(function () { var s2 = size(); p.resize(s2[0], s2[1]); }, 220);
      });
      var running = false;
      function frame(now) {
        if (I.dead || running) return;
        running = true;
        requestAnimationFrame(function step(t) {
          if (I.dead || !I.on || doc.hidden) { running = false; I.last = 0; return; }
          // the ink blooms once the boot overlay has handed over
          if (I.waitBoot && !root.hasAttribute('data-boot')) { I.waitBoot = false; p.intro(t); }
          p.renderAt((t - I.t0) / 1000, t);
          if (I.dial) {
            var ang = (((t - I.t0) / 1000) % p.T) / p.T * 360;
            I.dial.setAttribute('transform', 'rotate(' + ang.toFixed(1) + ')');
            if (I.n++ % 4 === 0) I.ph.textContent = '\u03b8 ' + ('00' + Math.floor(ang)).slice(-3) + '\u00b0';
          }
          // scroll: the stage falls behind the page a little and the ink stays put
          var r = stage.getBoundingClientRect();
          if (r.top <= 0) cv.style.transform = 'translate3d(0,' + (-r.top * 0.35).toFixed(1) + 'px,0) scale(' + (1 + Math.min(0.06, -r.top / r.height * 0.06)).toFixed(4) + ')';
          else cv.style.transform = '';
          // WebGL is asynchronous, so the GPU's cost shows as the gap between frames
          if (I.last && I.times.length < 90) {
            I.times.push(t - I.last);
            if (I.times.length === 90) {
              var sorted = I.times.slice(30).sort(function (x, y) { return x - y; }), med = sorted[sorted.length >> 1];
              if (med > 24 && q > 0.6) { q *= 0.66; var s3 = size(); p.resize(s3[0], s3[1]); I.times = []; }
              else if (med > 24) { fallback(); running = false; return; }
            }
          }
          I.last = t;
          if (!cv.classList.contains('on')) { cv.classList.add('on'); stage.classList.add('live'); }
          requestAnimationFrame(step);
        });
      }
      doc.addEventListener('visibilitychange', function () { if (!doc.hidden) frame(performance.now()); });
      frame(performance.now());
    }).catch(fallback);
  }

  /* ---------- the motion page: every scene, live, one at a time ---------- */

  function setupPlayground() {
    var box = $('[data-playground]');
    if (!box) return;
    var cv = $('canvas', box), chips = $$('[data-scene]', box), cap = $('[data-cap]', box);
    if (stillMotion() || !window.EdInk || !EdInk.supported()) { box.classList.add('off'); return; }
    var cur = null, on = true, t0 = performance.now(), pending = null;
    var size = function () {
      var r = cv.getBoundingClientRect(), k = Math.min(window.devicePixelRatio || 1, 1.5);
      return [Math.max(2, Math.round(r.width * k)), Math.max(2, Math.round(r.height * k))];
    };
    function pick(i) {
      var name = chips[i].dataset.scene;
      chips.forEach(function (c, n) { c.setAttribute('aria-pressed', String(n === i)); });
      if (cap) cap.textContent = chips[i].dataset.note || name;
      // a fresh canvas per scene: a WebGL context cannot be handed to a new program cleanly
      var fresh = cv.cloneNode(false);
      cv.replaceWith(fresh); cv = fresh;
      var wh = size(); cv.width = wh[0]; cv.height = wh[1];
      if (cur) { try { cur.destroy(); } catch (e) {} cur = null; }
      pending = name;
      EdInk.create(cv, name, { live: true, intro: true }).then(function (p) {
        if (pending !== name) { p.destroy(); return; }
        cur = p; t0 = performance.now(); p.intro(t0);
        cv.addEventListener('pointermove', function (e) { var r = cv.getBoundingClientRect(); p.pointer((e.clientX - r.left - r.width / 2) / r.height, (e.clientY - r.top - r.height / 2) / r.height, true); });
        cv.addEventListener('pointerleave', function () { p.pointer(null, null, false); });
      }).catch(function () { box.classList.add('off'); });
    }
    chips.forEach(function (c, i) { c.addEventListener('click', function () { pick(i); }); });
    new IntersectionObserver(function (es) { on = es[0].isIntersecting; }, { threshold: 0 }).observe(box);
    (function loop(t) {
      if (cur && on && !doc.hidden) cur.renderAt((t - t0) / 1000, t);
      requestAnimationFrame(loop);
    })(performance.now());
    pick(0);
  }

  /* ---------- contact: the form writes the message, the visitor picks where it goes ----------
     The site has no backend. A discussion is prefilled on GitHub (public, so the email is left
     out), an email opens the visitor's own mail app (only when the form carries data-email),
     and the message can be copied. Nothing is sent from the page. */

  var TOPICS = { partner: 'Design partner', team: 'Team plan', enterprise: 'Enterprise', question: 'Question', other: 'Hello' };

  function setupContact() {
    var form = $('[data-contact]');
    if (!form) return;
    var err = $('[data-cf-err]', form), state = $('[data-cf-state]', form), note = $('[data-cf-note]', form);
    var mail = form.getAttribute('data-email') || '';
    var emailBtn = $('[data-route="email"]', form);
    if (mail && emailBtn) emailBtn.hidden = false;
    var pick = function (topic) {
      var r = $('input[name="topic"][value="' + topic + '"]', form);
      if (r) r.checked = true;
      $$('.chan[data-topic]').forEach(function (c) { c.classList.toggle('picked', c.dataset.topic === topic); });
    };
    try { var q = new URLSearchParams(location.search).get('topic'); if (q && TOPICS[q]) pick(q); } catch (e) {}
    $$('input[name="topic"]', form).forEach(function (r) { r.addEventListener('change', function () { pick(r.value); }); });
    $$('.chan[data-topic]').forEach(function (c) {
      c.addEventListener('click', function (e) {
        e.preventDefault();
        pick(c.dataset.topic);
        try { history.replaceState(null, '', '?topic=' + c.dataset.topic + '#write'); } catch (x) {}
        var w = $('#write');
        if (w) w.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth' });
        setTimeout(function () { var n = form.elements.name; if (n) n.focus({ preventScroll: true }); }, reduced ? 0 : 700);
      });
    });
    var route = mail ? 'email' : 'discussion';
    $$('button[type="submit"]', form).forEach(function (b) { b.addEventListener('click', function () { route = b.dataset.route; }); });
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var f = form.elements, topic = (form.querySelector('input[name="topic"]:checked') || {}).value || 'other';
      var name = f.name.value.trim(), org = f.org.value.trim(), email = f.email.value.trim(), msg = f.message.value.trim();
      var bad = [];
      [['name', name], ['message', msg]].forEach(function (x) { var ok = !!x[1]; f[x[0]].parentNode.classList.toggle('bad', !ok); if (!ok) bad.push(x[0]); });
      var mailOk = !email || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
      f.email.parentNode.classList.toggle('bad', !mailOk);
      if (!mailOk) bad.push('a valid email');
      if (route === 'email' && !email) { f.email.parentNode.classList.add('bad'); bad.push('an email to reply to'); }
      if (bad.length) { err.hidden = false; err.textContent = 'Missing: ' + bad.join(', ') + '.'; return; }
      err.hidden = true;
      var title = TOPICS[topic] + ': ' + (org || name);
      var head = 'Topic: ' + TOPICS[topic] + '\nFrom: ' + name + (org ? ', ' + org : '');
      var done = function (label) { form.classList.add('sent'); if (state) state.textContent = label; };
      if (route === 'discussion') {
        var cat = topic === 'question' ? 'q-a' : 'general';
        var url = 'https://github.com/EDIFY-agents/claude-skills/discussions/new?category=' + cat +
          '&title=' + encodeURIComponent(title) + '&body=' + encodeURIComponent(head + '\n\n' + msg);
        window.open(url, '_blank', 'noopener');
        done('opened on GitHub');
      } else if (route === 'email' && mail) {
        location.href = 'mailto:' + mail + '?subject=' + encodeURIComponent('[EDIFY] ' + title) + '&body=' + encodeURIComponent(head + '\nReply to: ' + email + '\n\n' + msg);
        done('handed to your mail app');
        if (note) note.textContent = 'Your mail app should open with the message addressed to ' + mail + '. If nothing opened, copy the message and send it there.';
      } else {
        var text = head + (email ? '\nReply to: ' + email : '') + '\n\n' + msg;
        var ok = function () { done('copied'); if (note) note.textContent = 'Copied. Paste it wherever suits you: a discussion, an issue, or an email.'; };
        if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(ok, function () {});
        else { var t = doc.createElement('textarea'); t.value = text; doc.body.appendChild(t); t.select(); try { doc.execCommand('copy'); ok(); } catch (x) {} t.remove(); }
      }
    });
  }

  /* ---------- buttons lean toward the pointer, a few pixels ---------- */

  function setupMagnet() {
    if (reduced || !window.matchMedia('(hover:hover) and (pointer:fine)').matches) return;
    $$('.btn').forEach(function (b) {
      b.setAttribute('data-mag', '');
      b.addEventListener('pointermove', function (e) {
        var r = b.getBoundingClientRect();
        var dx = (e.clientX - r.left) / r.width - 0.5, dy = (e.clientY - r.top) / r.height - 0.5;
        b.style.transform = 'translate3d(' + (dx * 8).toFixed(1) + 'px,' + (dy * 6).toFixed(1) + 'px,0)';
      });
      b.addEventListener('pointerleave', function () { b.style.transform = ''; });
    });
  }

  /* ---------- start ---------- */

  function start() {
    setupChrome();
    setupLogo();
    setupTerminals();
    setupTabs();
    setupFaq();
    setupField();
    setupGallery();
    setupInk();
    setupPlayground();
    setupContact();
    setupFilms();
    setupMagnet();
    measure();
    setupReveal();
    doc.addEventListener('visibilitychange', function () { S.hidden = doc.hidden; });
    window.addEventListener('resize', function () {
      clearTimeout(S.rt);
      S.rt = setTimeout(function () { small = window.innerWidth < 560; sizeField(); measure(); }, 150);
    });
    window.addEventListener('scroll', function () { sweep(); if (S.rafDead) { staticScroll(); progress(window.scrollY); } }, { passive: true });
    if (!reduced) {
      var loop = function (t) { tick(t); requestAnimationFrame(loop); };
      requestAnimationFrame(loop);
      setTimeout(function () { if (!S.n) noRaf(); }, 1400);
    } else {
      noRaf();
      if (S.meterValue) { S.meterFill.style.width = '100%'; }
    }
    setupBoot();
  }

  if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', start);
  else start();
})();
