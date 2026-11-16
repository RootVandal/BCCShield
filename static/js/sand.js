// Chladni-plate "sand": grains jitter in proportion to plate vibration and collect on nodal lines.
// Brightness accumulates per pixel, so dense bands glow while stray grains stay faint.
(function () {
  // [n, m, sign]: v = cos(nπx)cos(mπy) + sign·cos(mπx)cos(nπy), blended with a radial ring mode.
  const MODES = [[1, 3, 1, 0.45], [3, 4, 1, 0.15], [2, 5, 1, 0.2], [4, 5, -1, 0.1], [3, 6, 1, 0.15], [2, 3, 1, 0.3], [5, 6, 1, 0.1], [1, 4, 1, 0.25]];
  const P = Math.PI;
  const reduceMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function makeLut(color, gain, maxA) {
    const lut = new Uint32Array(64);
    for (let c = 1; c < 64; c++) {
      const a = Math.round(Math.min(maxA, 1 - Math.exp(-c * gain)) * 255);
      lut[c] = (a << 24) | (color[2] << 16) | (color[1] << 8) | color[0]; // little-endian ABGR
    }
    return lut;
  }

  function startSand(canvas, opts = {}) {
    const ctx = canvas.getContext("2d");
    const density = opts.density ?? 1;
    const color = opts.color ?? [214, 210, 200];
    const hold = opts.hold ?? 6500;
    const lut = makeLut(color, opts.gain ?? 0.22, opts.alpha ?? 0.9);
    const reduce = reduceMotion();
    let W, H, N, px, py, img, buf, cnt, aspect;
    let mi = 0, from = MODES[0], to = MODES[0], tSwitch = performance.now();

    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      W = canvas.width = Math.floor(innerWidth * dpr);
      H = canvas.height = Math.floor(innerHeight * dpr);
      aspect = W / H;
      N = Math.floor(Math.min(130000, (W * H) / 13) * density);
      px = new Float32Array(N); py = new Float32Array(N);
      for (let i = 0; i < N; i++) { px[i] = Math.random() * 2 - 1; py[i] = Math.random() * 2 - 1; }
      img = ctx.createImageData(W, H); buf = new Uint32Array(img.data.buffer); cnt = new Uint8Array(W * H);
    }

    function plate(md, x, y) {
      const [n, m, s, ring] = md;
      const r = Math.sqrt(x * x + y * y);
      const v = Math.cos(n * P * x) * Math.cos(m * P * y) + s * Math.cos(m * P * x) * Math.cos(n * P * y);
      return (1 - ring) * v * 0.5 + ring * Math.cos(2.6 * P * r + 0.6);
    }

    function step(now, draw) {
      const since = now - tSwitch;
      if (since > hold) { mi = (mi + 1) % MODES.length; from = to; to = MODES[mi]; tSwitch = now; }
      const mix = Math.min(1, (now - tSwitch) / 2600);
      const k = mix * mix * (3 - 2 * mix);
      const shake = 1 + 1.4 * Math.sin(P * mix); // plate rings harder while it changes pitch
      const sx = aspect > 1 ? aspect * 0.85 : 0.85, sy = aspect > 1 ? 0.85 : 0.85 / aspect;
      for (let i = 0; i < N; i++) {
        let x = px[i], y = py[i];
        const X = x * sx, Y = y * sy;
        const v = (1 - k) * plate(from, X, Y) + k * plate(to, X, Y);
        const a = Math.min(Math.abs(v) * 1.6, 1) * 0.03 * shake + 0.0011;
        x += (Math.random() * 2 - 1) * a; y += (Math.random() * 2 - 1) * a;
        if (x < -1) x = -0.999; else if (x > 1) x = 0.999;
        if (y < -1) y = -0.999; else if (y > 1) y = 0.999;
        px[i] = x; py[i] = y;
      }
      if (!draw) return;
      cnt.fill(0);
      for (let i = 0; i < N; i++) {
        const idx = (((py[i] + 1) * 0.5 * H) | 0) * W + (((px[i] + 1) * 0.5 * W) | 0);
        if (cnt[idx] < 63) cnt[idx]++;
      }
      for (let j = 0; j < cnt.length; j++) buf[j] = lut[cnt[j]];
      ctx.putImageData(img, 0, 0);
    }

    function loop(now) { step(now, true); if (!reduce && !document.hidden) requestAnimationFrame(loop); }
    function warm() { // settle onto the first figure so the page never opens on plain noise
      tSwitch = performance.now() - 2600;
      for (let s = 0; s < 400; s++) step(tSwitch + 2600, false);
      tSwitch = performance.now() - 2600;
    }
    resize(); warm();
    addEventListener("resize", () => { resize(); warm(); step(performance.now(), true); });
    document.addEventListener("visibilitychange", () => { if (!document.hidden && !reduce) requestAnimationFrame(loop); });
    if (reduce) step(performance.now(), true); else requestAnimationFrame(loop);
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
