// Chladni-plate "sand": grains jitter in proportion to plate vibration and collect on nodal lines.
// Brightness accumulates per pixel, so dense bands glow while stray grains stay faint.
// The background runs in a Web Worker on an OffscreenCanvas (this same file is the worker script), so it never
// blocks clicks, typing or WebSocket updates. Browsers without OffscreenCanvas run it on the main thread.
(function () {
  // [n, m, sign]: v = cos(nπx)cos(mπy) + sign·cos(mπx)cos(nπy), blended with a radial ring mode.
  const MODES = [[1, 3, 1, 0.45], [3, 4, 1, 0.15], [2, 5, 1, 0.2], [4, 5, -1, 0.1], [3, 6, 1, 0.15], [2, 3, 1, 0.3], [5, 6, 1, 0.1], [1, 4, 1, 0.25]];
  const P = Math.PI;
  const IN_WORKER = typeof document === "undefined";
  const SELF_URL = IN_WORKER ? "" : (document.currentScript && document.currentScript.src) || "";
  const reduceMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function makeLut(color, gain, maxA) {
    const lut = new Uint32Array(64);
    for (let c = 1; c < 64; c++) {
      const a = Math.round(Math.min(maxA, 1 - Math.exp(-c * gain)) * 255);
      lut[c] = (a << 24) | (color[2] << 16) | (color[1] << 8) | color[0]; // little-endian ABGR
    }
    return lut;
  }

  // Plate shape v(x, y) for every mode, as per-axis cosine tables plus one radial table: a grain costs a few
  // array reads per frame instead of ten Math.cos calls. TS samples per axis is finer than a screen pixel.
  const TS = 8192, HS = (TS - 1) / 2;

  function buildTables(sx, sy) {
    const rmax = Math.sqrt(sx * sx + sy * sy) + 1e-6, rs = (TS - 1) / rmax;
    const ring = new Float32Array(TS);
    for (let j = 0; j < TS; j++) ring[j] = Math.cos(2.6 * P * (j / rs) + 0.6);
    const modes = MODES.map(([n, m, s, rg]) => {
      const ax = new Float32Array(TS), cx = new Float32Array(TS), by = new Float32Array(TS), dy = new Float32Array(TS);
      const g = (1 - rg) * 0.5;
      for (let i = 0; i < TS; i++) {
        const u = i / HS - 1, X = u * sx, Y = u * sy;
        ax[i] = g * Math.cos(n * P * X); cx[i] = s * g * Math.cos(m * P * X);
        by[i] = Math.cos(m * P * Y); dy[i] = Math.cos(n * P * Y);
      }
      return { ax, cx, by, dy, rg };
    });
    return { modes, ring, rs };
  }

  // The simulation itself. `canvas` is a <canvas> or an OffscreenCanvas; `env` says how to schedule work:
  // { reduce, hidden, slice } where slice is the time budget (ms) per frame for the start-up settling steps.
  function createSand(canvas, opts, env) {
    const ctx = canvas.getContext("2d");
    const density = opts.density ?? 1;
    const color = opts.color ?? [214, 210, 200];
    const hold = opts.hold ?? 6500;
    const lut = makeLut(color, opts.gain ?? 0.22, opts.alpha ?? 0.9);
    const reduce = !!env.reduce;
    const now = () => performance.now();
    const raf = typeof requestAnimationFrame === "function" ? (fn) => requestAnimationFrame(fn) : (fn) => setTimeout(fn, 16);
    let W = 0, H = 0, N = 0, dpr = 1, px, py, img, buf, cnt, prev, drawn = 0, sx = 1, sy = 1, tabs;
    let mi = 0, fi = 0, ti = 0, tSwitch = now();
    let ready = false, hidden = !!env.hidden, queued = false, warmLeft = 0;
    let ptX = 0, ptY = 0, ptDX = 0, ptDY = 0, ptT = -1e9, ptE = 0; // cursor: position, last move, time, energy 0..1

    function plateAbs(M, x, y) { // |v| of one mode at a grain position
      const ix = ((x + 1) * HS + 0.5) | 0, iy = ((y + 1) * HS + 0.5) | 0, X = x * sx, Y = y * sy;
      const v = M.ax[ix] * M.by[iy] + M.cx[ix] * M.dy[iy] + M.rg * tabs.ring[(Math.sqrt(X * X + Y * Y) * tabs.rs + 0.5) | 0];
      return v < 0 ? -v : v;
    }

    function resize(w, h, ratio) {
      dpr = ratio;
      W = canvas.width = Math.max(1, Math.floor(w * dpr));
      H = canvas.height = Math.max(1, Math.floor(h * dpr));
      const aspect = W / H;
      sx = aspect > 1 ? aspect * 0.85 : 0.85; sy = aspect > 1 ? 0.85 : 0.85 / aspect;
      tabs = buildTables(sx, sy);
      const n = Math.floor(Math.min(130000, (W * H) / 13) * density), ox = px, oy = py, on = N;
      px = new Float32Array(n); py = new Float32Array(n);
      const M = tabs.modes[ti];
      for (let i = 0; i < n; i++) {
        if (on) { const j = i < on ? i : (Math.random() * on) | 0; px[i] = ox[j]; py[i] = oy[j]; continue; } // keep the settled figure
        // First start: drop each grain on the quietest of a few random spots, so the very first frame
        // already shows the figure instead of plain noise.
        let bx = 0, by = 0, bv = 9;
        for (let c = 0; c < 6; c++) {
          const x = Math.random() * 2 - 1, y = Math.random() * 2 - 1, v = plateAbs(M, x, y);
          if (v < bv) { bv = v; bx = x; by = y; }
        }
        px[i] = bx; py[i] = by;
      }
      N = n;
      img = ctx.createImageData(W, H); buf = new Uint32Array(img.data.buffer); cnt = new Uint8Array(W * H);
      prev = new Int32Array(n); drawn = 0;
      if (!on || reduce) { warmLeft = 400; tSwitch = now() - 2600; } // settle fully onto the figure
      ready = true;
      schedule();
    }

    function setPointer(nx, ny) { // cursor position in -1..1 canvas coordinates
      const t = now(), dx = nx - ptX, dy = ny - ptY, speed = Math.sqrt(dx * dx * W * W + dy * dy * H * H) * 0.5;
      const moving = t - ptT < 120 && speed < 400 * dpr; // a pause or a jump is not a sweep
      ptDX = moving ? dx : 0; ptDY = moving ? dy : 0;
      ptE = moving ? Math.min(1, 0.3 + speed / (30 * dpr)) : 0;
      ptX = nx; ptY = ny; ptT = t;
    }

    function step(t, draw) {
      if (t - tSwitch > hold) { mi = (mi + 1) % MODES.length; fi = ti; ti = mi; tSwitch = t; }
      const mix = Math.min(1, (t - tSwitch) / 2600);
      const k = mix * mix * (3 - 2 * mix), k0 = 1 - k, blend = k < 1;
      const amp = 0.03 * (1 + 1.4 * Math.sin(P * mix)); // plate rings harder while it changes pitch
      const T = tabs.modes[ti], F = tabs.modes[fi], ring = tabs.ring, rs = tabs.rs;
      const tax = T.ax, tcx = T.cx, tby = T.by, tdy = T.dy, trg = T.rg;
      const fax = F.ax, fcx = F.cx, fby = F.by, fdy = F.dy, frg = F.rg;
      const hw = 0.5 * W, hh = 0.5 * H;
      let push = 0, pr2 = 1, dragX = 0, dragY = 0; // a moving cursor knocks nearby grains aside and drags them along
      if (draw && ptE > 0) {
        const fade = 1 - (now() - ptT) / 250;
        if (fade > 0) { const r = 85 * dpr, e = ptE * fade; pr2 = r * r; push = 18 * dpr * e; dragX = ptDX * 0.3 * e; dragY = ptDY * 0.3 * e; }
        else ptE = 0;
      }
      if (draw) { for (let i = 0; i < drawn; i++) { const j = prev[i]; cnt[j] = 0; buf[j] = 0; } } // wipe only last frame's grains
      for (let i = 0; i < N; i++) {
        let x = px[i], y = py[i];
        const ix = ((x + 1) * HS + 0.5) | 0, iy = ((y + 1) * HS + 0.5) | 0, X = x * sx, Y = y * sy;
        const rv = ring[(Math.sqrt(X * X + Y * Y) * rs + 0.5) | 0];
        let v = tax[ix] * tby[iy] + tcx[ix] * tdy[iy] + trg * rv;
        if (blend) v = k0 * (fax[ix] * fby[iy] + fcx[ix] * fdy[iy] + frg * rv) + k * v;
        if (v < 0) v = -v;
        v *= 1.6; if (v > 1) v = 1;
        const a = v * amp + 0.0011;
        x += (Math.random() * 2 - 1) * a; y += (Math.random() * 2 - 1) * a;
        if (push > 0) {
          const dx = (x - ptX) * hw, dy = (y - ptY) * hh, d2 = dx * dx + dy * dy;
          if (d2 < pr2) {
            const f = 1 - d2 / pr2, g = push * f * f / (Math.sqrt(d2) + 0.5);
            x += dx * g / hw + dragX * f; y += dy * g / hh + dragY * f;
          }
        }
        if (x < -1) x = -0.999; else if (x >= 1) x = 0.999;
        if (y < -1) y = -0.999; else if (y >= 1) y = 0.999;
        px[i] = x; py[i] = y;
        if (draw) {
          const idx = (((y + 1) * hh) | 0) * W + (((x + 1) * hw) | 0);
          prev[i] = idx;
          const c = cnt[idx];
          if (c < 63) { cnt[idx] = c + 1; buf[idx] = lut[c + 1]; }
        }
      }
      if (draw) { drawn = N; ctx.putImageData(img, 0, 0); }
    }

    function frame() {
      queued = false;
      if (!ready || hidden) return;
      if (warmLeft > 0) { // start-up: several quick steps per frame, drawn as they go, so the sand is there from the first frame
        const stamp = tSwitch + 2600, t0 = now(), slice = env.slice ?? 5;
        while (warmLeft > 1 && now() - t0 < slice) { step(stamp, false); warmLeft--; }
        warmLeft--;
        step(stamp, !reduce || warmLeft === 0); // reduced motion: show only the settled frame
        if (warmLeft === 0) tSwitch = now() - 2600;
        if (warmLeft > 0 || !reduce) schedule();
        return;
      }
      step(now(), true);
      if (!reduce) schedule();
    }
    function schedule() { if (!queued && ready && !hidden) { queued = true; raf(frame); } }

    return {
      resize,
      setPointer,
      setHidden(h) { hidden = !!h; if (!reduce || warmLeft > 0) schedule(); },
    };
  }

  // Inside a worker this file is only the simulation: the page hands over an OffscreenCanvas and sizes.
  if (IN_WORKER) {
    let sand = null;
    self.onmessage = (e) => {
      const d = e.data || {};
      if (d.type === "sand-init") {
        sand = createSand(d.canvas, d.opts || {}, { reduce: d.reduce, hidden: d.hidden, slice: 9 });
        sand.resize(d.w, d.h, d.dpr);
      } else if (sand && d.type === "sand-resize") sand.resize(d.w, d.h, d.dpr);
      else if (sand && d.type === "sand-hidden") sand.setHidden(d.hidden);
      else if (sand && d.type === "sand-pointer") sand.setPointer(d.x, d.y);
    };
    return;
  }

  function startSand(canvas, opts = {}) {
    const reduce = reduceMotion();
    const size = () => ({ w: innerWidth, h: innerHeight, dpr: Math.min(window.devicePixelRatio || 1, 1.5) });
    let sand = null, transferred = false;

    function inline() { // main-thread fallback: same simulation with a smaller time budget per frame
      if (transferred) { const fresh = canvas.cloneNode(false); canvas.replaceWith(fresh); canvas = fresh; transferred = false; }
      const s = size(), eng = createSand(canvas, opts, { reduce, hidden: document.hidden, slice: 5 });
      eng.resize(s.w, s.h, s.dpr);
      return { resize: (z) => eng.resize(z.w, z.h, z.dpr), hidden: (h) => eng.setHidden(h), pointer: (x, y) => eng.setPointer(x, y) };
    }

    if (SELF_URL && window.Worker && canvas.transferControlToOffscreen) {
      try {
        const off = canvas.transferControlToOffscreen();
        transferred = true;
        const worker = new Worker(SELF_URL);
        worker.onerror = () => { worker.terminate(); if (transferred) sand = inline(); };
        worker.postMessage({ type: "sand-init", canvas: off, opts, reduce, hidden: document.hidden, ...size() }, [off]);
        sand = {
          resize: (z) => worker.postMessage({ type: "sand-resize", ...z }),
          hidden: (h) => worker.postMessage({ type: "sand-hidden", hidden: h }),
          pointer: (x, y) => worker.postMessage({ type: "sand-pointer", x, y }),
        };
      } catch (_) { sand = null; }
    }
    if (!sand) sand = inline();

    let timer;
    addEventListener("resize", () => { clearTimeout(timer); timer = setTimeout(() => sand.resize(size()), 150); });
    document.addEventListener("visibilitychange", () => sand.hidden(document.hidden));
    if (reduce) return;
    let last = null, pending = false; // cursor position, sent at most once per frame
    addEventListener("pointermove", (e) => {
      last = e;
      if (pending) return;
      pending = true;
      requestAnimationFrame(() => { pending = false; sand.pointer((last.clientX / innerWidth) * 2 - 1, (last.clientY / innerHeight) * 2 - 1); });
    }, { passive: true });
  }

  // Grain logo: a cloud of particles that settles into a shape, scatters a little and re-forms as the next one.
  const SHAPES = {
    shield(c, s) {
      c.lineWidth = s * 0.13; c.lineJoin = "round";
      c.beginPath(); c.moveTo(s * .5, s * .1); c.lineTo(s * .18, s * .22); c.lineTo(s * .18, s * .46);
      c.bezierCurveTo(s * .18, s * .7, s * .32, s * .84, s * .5, s * .92);
      c.bezierCurveTo(s * .68, s * .84, s * .82, s * .7, s * .82, s * .46); c.lineTo(s * .82, s * .22); c.closePath(); c.stroke();
    },
    check(c, s) {
      SHAPES.shield(c, s);
      c.lineWidth = s * 0.09; c.lineCap = "round";
      c.beginPath(); c.moveTo(s * .36, s * .5); c.lineTo(s * .46, s * .6); c.lineTo(s * .65, s * .39); c.stroke();
    },
    square(c, s) {
      c.lineWidth = s * 0.15; const r = s * 0.12, a = s * .2, b = s * .8;
      c.beginPath(); c.roundRect(a, a, b - a, b - a, r); c.stroke();
    },
    clover(c, s) {
      c.lineWidth = s * 0.13;
      const q = s * .25, m = s * .5;
      c.beginPath();
      c.moveTo(m - q * .55, m - q * .9);
      c.quadraticCurveTo(m, m - q * 2.1, m + q * .55, m - q * .9);
      c.quadraticCurveTo(m + q * 2.1, m - q * 2.1, m + q * .9, m - q * .55);
      c.quadraticCurveTo(m + q * 2.1, m, m + q * .9, m + q * .55);
      c.quadraticCurveTo(m + q * 2.1, m + q * 2.1, m + q * .55, m + q * .9);
      c.quadraticCurveTo(m, m + q * 2.1, m - q * .55, m + q * .9);
      c.quadraticCurveTo(m - q * 2.1, m + q * 2.1, m - q * .9, m + q * .55);
      c.quadraticCurveTo(m - q * 2.1, m, m - q * .9, m - q * .55);
      c.quadraticCurveTo(m - q * 2.1, m - q * 2.1, m - q * .55, m - q * .9);
      c.closePath(); c.stroke();
    },
  };

  function sampleShape(name, S, M) {
    const off = document.createElement("canvas"); off.width = off.height = S;
    const c = off.getContext("2d"); c.strokeStyle = "#fff"; c.fillStyle = "#fff";
    SHAPES[name](c, S);
    const d = c.getImageData(0, 0, S, S).data, pts = [];
    for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) if (d[(y * S + x) * 4 + 3] > 140) pts.push(x, y);
    const out = new Float32Array(M * 2), n = pts.length / 2;
    for (let i = 0; i < M; i++) { const j = (Math.random() * n) | 0; out[i * 2] = pts[j * 2]; out[i * 2 + 1] = pts[j * 2 + 1]; }
    return out;
  }

  function startGrainLogo(canvas, opts = {}) {
    const size = opts.size ?? 96, dpr = Math.min(window.devicePixelRatio || 1, 2);
    const S = Math.round(size * dpr);
    canvas.width = canvas.height = S; canvas.style.width = canvas.style.height = size + "px";
    const ctx = canvas.getContext("2d");
    const order = opts.shapes ?? ["check", "square", "clover", "shield"];
    const M = opts.grains ?? 4200;
    const targets = order.map((n) => sampleShape(n, S, M));
    const lut = makeLut(opts.color ?? [236, 233, 225], 0.3, 1);
    const img = ctx.createImageData(S, S), buf = new Uint32Array(img.data.buffer), cnt = new Uint8Array(S * S);
    const p = new Float32Array(M * 2);
    for (let i = 0; i < M * 2; i++) p[i] = Math.random() * S;
    const hold = opts.hold ?? 2600;
    let si = 0, t0 = performance.now();
    const reduce = reduceMotion();

    function frame(now) {
      if (now - t0 > hold) { si = (si + 1) % order.length; t0 = now; }
      const age = (now - t0) / hold;
      const pull = 0.04 + 0.16 * Math.min(1, age * 2.5);
      const jit = (0.5 + 3 * Math.max(0, 0.3 - age)) * dpr;
      const tg = targets[si];
      cnt.fill(0);
      for (let i = 0; i < M; i++) {
        const ix = i * 2, iy = ix + 1;
        p[ix] += (tg[ix] - p[ix]) * pull + (Math.random() - 0.5) * jit;
        p[iy] += (tg[iy] - p[iy]) * pull + (Math.random() - 0.5) * jit;
        const x = p[ix] | 0, y = p[iy] | 0;
        if (x >= 0 && y >= 0 && x < S && y < S) { const k = y * S + x; if (cnt[k] < 63) cnt[k]++; }
      }
      for (let j = 0; j < cnt.length; j++) buf[j] = lut[cnt[j]];
      ctx.putImageData(img, 0, 0);
      if (!reduce) requestAnimationFrame(frame);
    }
    if (reduce) { p.set(targets[0]); frame(t0 + 10); } else requestAnimationFrame(frame);
  }

  window.startSand = startSand;
  window.startGrainLogo = startGrainLogo;
})();
