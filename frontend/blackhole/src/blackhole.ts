// Ported from the supplied BlackHoleHeroSection React component to a plain
// mount/cleanup function — it barely used React to begin with (one useEffect
// holding imperative canvas/WebGL code via refs). Running inside a sandboxed
// iframe (via Streamlit's components.v1.html) means there is no other DOM to
// coordinate with, so the imperative-function shape is the natural one here,
// not a workaround.
//
// Hardening applied on top of the reference implementation, each corresponding
// to a gap called out in the task spec:
//   1. True idle when paused/reduced-motion: the reference kept calling the
//      full multi-pass render() every rAF tick even while `paused`, only
//      skipping the clock advance. That burns GPU for a static image. Here,
//      once idle, the rAF loop itself stops; a fixed batch of jittered
//      settle() passes draws the final still, and nothing more runs until an
//      external event (resize, tab refocus, motion-preference change) wakes
//      it.
//   2. Live reduced-motion: the reference read prefers-reduced-motion once at
//      mount into a const. This listens for changes for as long as the
//      component is mounted.
//   3. Visibility tracking: the reference had IntersectionObserver and the
//      document visibilitychange handler both write the same `visible`
//      variable, so whichever fires last wins — a tab refocus can stomp an
//      "off-screen" result from the intersection observer. Tracked
//      separately here and combined with AND.
//   4. Framebuffer-failure fallback: the reference's makeTarget() already
//      detected an incomplete framebuffer and returned null, but resize()
//      never checked for that, so a real allocation failure would render
//      nothing, forever, silently. Now surfaces as the same static-fallback
//      path as a missing WebGL context.
//   5. Everything else (context loss/restore, GPU resource cleanup, the
//      history-buffer alpha=1 special case on the first frame, the shader
//      math) is unchanged from the reference — inspected, not found broken.

import {
  VERT,
  SCENE_FRAG,
  BLEND_FRAG,
  BRIGHT_FRAG,
  BLUR_FRAG,
  COMPOSITE_FRAG,
} from "./shaders";

export interface BlackHoleOptions {
  distance: number;
  elevation: number;
  azimuth: number;
  orbitSpeed: number;
  roll: number;
  fov: number;
  diskInner: number;
  diskOuter: number;
  diskThickness: number;
  diskDensity: number;
  brightness: number;
  spinSpeed: number;
  grain: number;
  doppler: number;
  hotColor: string;
  midColor: string;
  coolColor: string;
  starBrightness: number;
  glow: number;
  exposure: number;
  vignette: number;
  steps: number;
  resolution: number;
  maxDpr: number;
  focus: [number, number];
  scrim: "none" | "left" | "right" | "top" | "bottom";
  scrimStrength: number;
  paused: boolean;
}

export const DEFAULT_OPTIONS: BlackHoleOptions = {
  distance: 24,
  elevation: -5.5,
  azimuth: 0,
  orbitSpeed: 0,
  roll: -20,
  fov: 42,
  diskInner: 3,
  diskOuter: 15,
  diskThickness: 0.26,
  diskDensity: 1,
  brightness: 1,
  spinSpeed: 0.06,
  grain: 0.48,
  doppler: 0.35,
  hotColor: "#FFF3DE",
  midColor: "#FFB36B",
  coolColor: "#8E3A0B",
  starBrightness: 0.5,
  glow: 1,
  exposure: 0.9,
  vignette: 0.28,
  steps: 300,
  resolution: 0.7,
  maxDpr: 1.75,
  focus: [0.72, 0.46],
  scrim: "none",
  scrimStrength: 0.9,
  paused: false,
};

const RAD = Math.PI / 180;

function hexToLinear(hex: string): [number, number, number] {
  const h = hex.trim().replace("#", "");
  const full =
    h.length === 3 ? h[0] + h[0] + h[1] + h[1] + h[2] + h[2] : h.slice(0, 6);
  const n = parseInt(full, 16);
  const srgb = [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
  return srgb.map((v) =>
    v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)
  ) as [number, number, number];
}

type Prog = {
  program: WebGLProgram;
  u: Record<string, WebGLUniformLocation | null>;
};

type Target = {
  fb: WebGLFramebuffer;
  tex: WebGLTexture;
  w: number;
  h: number;
};

export type MountResult = {
  cleanup: () => void;
  /** Resolves true once we know whether WebGL actually came up. */
  ready: Promise<boolean>;
};

export function mountBlackHole(
  host: HTMLElement,
  canvas: HTMLCanvasElement,
  optsIn: Partial<BlackHoleOptions>
): MountResult {
  const opts: BlackHoleOptions = { ...DEFAULT_OPTIONS, ...optsIn };
  let resolveReady: (ok: boolean) => void = () => {};
  const ready = new Promise<boolean>((res) => {
    resolveReady = res;
  });

  let reducedMQ: MediaQueryList | null = null;
  let reduced =
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const glOpts: WebGLContextAttributes = {
    alpha: false,
    antialias: false,
    depth: false,
    stencil: false,
    powerPreference: "high-performance",
    preserveDrawingBuffer: false,
  };
  const gl = (canvas.getContext("webgl2", glOpts) ||
    canvas.getContext("webgl", glOpts)) as
    | WebGL2RenderingContext
    | WebGLRenderingContext
    | null;

  function giveUp(why: string) {
    host.dataset.webgl = why;
    canvas.style.display = "none";
    resolveReady(false);
  }

  if (!gl) {
    giveUp("unsupported");
    return { cleanup: () => {}, ready };
  }

  const dbg = gl.getExtension("WEBGL_debug_renderer_info");
  const renderer = dbg
    ? String(gl.getParameter((dbg as any).UNMASKED_RENDERER_WEBGL) || "")
    : "";
  const software = /swiftshader|llvmpipe|softpipe|software|microsoft basic/i.test(
    renderer
  );
  const isGL2 =
    typeof WebGL2RenderingContext !== "undefined" &&
    gl instanceof WebGL2RenderingContext;

  function compile(type: number, src: string): WebGLShader | null {
    const sh = gl!.createShader(type);
    if (!sh) return null;
    gl!.shaderSource(sh, src);
    gl!.compileShader(sh);
    if (!gl!.getShaderParameter(sh, gl!.COMPILE_STATUS)) {
      console.error(
        "blackhole: shader failed —",
        gl!.getShaderInfoLog(sh) || "no log (context lost?)"
      );
      gl!.deleteShader(sh);
      return null;
    }
    return sh;
  }

  function link(fragSrc: string): Prog | null {
    const vs = compile(gl!.VERTEX_SHADER, VERT);
    const fs = compile(gl!.FRAGMENT_SHADER, fragSrc);
    if (!vs || !fs) return null;
    const program = gl!.createProgram();
    if (!program) return null;
    gl!.attachShader(program, vs);
    gl!.attachShader(program, fs);
    gl!.bindAttribLocation(program, 0, "aPos");
    gl!.linkProgram(program);
    gl!.deleteShader(vs);
    gl!.deleteShader(fs);
    if (!gl!.getProgramParameter(program, gl!.LINK_STATUS)) {
      console.error(gl!.getProgramInfoLog(program));
      return null;
    }
    const u: Record<string, WebGLUniformLocation | null> = {};
    const n = gl!.getProgramParameter(program, gl!.ACTIVE_UNIFORMS) as number;
    for (let i = 0; i < n; i++) {
      const info = gl!.getActiveUniform(program, i);
      if (info) u[info.name] = gl!.getUniformLocation(program, info.name);
    }
    return { program, u };
  }

  let hdr = true;
  let texType: number = gl.UNSIGNED_BYTE;
  let internal: number = gl.RGBA;
  if (isGL2) {
    const g2 = gl as WebGL2RenderingContext;
    const ok =
      g2.getExtension("EXT_color_buffer_half_float") ||
      g2.getExtension("EXT_color_buffer_float");
    if (ok) {
      texType = g2.HALF_FLOAT;
      internal = g2.RGBA16F;
    } else hdr = false;
  } else {
    const hf = gl.getExtension("OES_texture_half_float");
    const cb = gl.getExtension("EXT_color_buffer_half_float");
    if (hf && cb) texType = (hf as any).HALF_FLOAT_OES;
    else hdr = false;
  }
  if (!hdr) {
    texType = gl.UNSIGNED_BYTE;
    internal = gl.RGBA;
  }
  const linearOK =
    isGL2 || !!gl.getExtension("OES_texture_half_float_linear") || !hdr;
  const filter = linearOK ? gl.LINEAR : gl.NEAREST;
  const pack = hdr ? 1 : 0.12;

  function makeTarget(w: number, h: number): Target | null {
    const tex = gl!.createTexture();
    const fb = gl!.createFramebuffer();
    if (!tex || !fb) return null;
    gl!.bindTexture(gl!.TEXTURE_2D, tex);
    gl!.texImage2D(gl!.TEXTURE_2D, 0, internal, w, h, 0, gl!.RGBA, texType, null);
    gl!.texParameteri(gl!.TEXTURE_2D, gl!.TEXTURE_MIN_FILTER, filter);
    gl!.texParameteri(gl!.TEXTURE_2D, gl!.TEXTURE_MAG_FILTER, filter);
    gl!.texParameteri(gl!.TEXTURE_2D, gl!.TEXTURE_WRAP_S, gl!.CLAMP_TO_EDGE);
    gl!.texParameteri(gl!.TEXTURE_2D, gl!.TEXTURE_WRAP_T, gl!.CLAMP_TO_EDGE);
    gl!.bindFramebuffer(gl!.FRAMEBUFFER, fb);
    gl!.framebufferTexture2D(
      gl!.FRAMEBUFFER,
      gl!.COLOR_ATTACHMENT0,
      gl!.TEXTURE_2D,
      tex,
      0
    );
    const status = gl!.checkFramebufferStatus(gl!.FRAMEBUFFER);
    gl!.bindFramebuffer(gl!.FRAMEBUFFER, null);
    if (status !== gl!.FRAMEBUFFER_COMPLETE) {
      gl!.deleteTexture(tex);
      gl!.deleteFramebuffer(fb);
      return null;
    }
    return { fb, tex, w, h };
  }

  let sceneProg: Prog | null = null;
  let blendProg: Prog | null = null;
  let brightProg: Prog | null = null;
  let blurProg: Prog | null = null;
  let compProg: Prog | null = null;
  let vbo: WebGLBuffer | null = null;
  let scene: Target | null = null;
  let histA: Target | null = null;
  let histB: Target | null = null;
  let bloomA: Target | null = null;
  let bloomB: Target | null = null;
  let settled = 0;

  let width = 0;
  let height = 0;
  let sceneW = 0;
  let sceneH = 0;

  function build(): boolean {
    sceneProg = link(SCENE_FRAG);
    blendProg = link(BLEND_FRAG);
    brightProg = link(BRIGHT_FRAG);
    blurProg = link(BLUR_FRAG);
    compProg = link(COMPOSITE_FRAG);
    if (!sceneProg || !blendProg || !brightProg || !blurProg || !compProg)
      return false;

    vbo = gl!.createBuffer();
    gl!.bindBuffer(gl!.ARRAY_BUFFER, vbo);
    gl!.bufferData(
      gl!.ARRAY_BUFFER,
      new Float32Array([-1, -1, 3, -1, -1, 3]),
      gl!.STATIC_DRAW
    );
    gl!.enableVertexAttribArray(0);
    gl!.vertexAttribPointer(0, 2, gl!.FLOAT, false, 0, 0);
    gl!.disable(gl!.DEPTH_TEST);
    gl!.disable(gl!.BLEND);
    return true;
  }

  function dropTargets() {
    for (const t of [scene, histA, histB, bloomA, bloomB]) {
      if (!t) continue;
      gl!.deleteTexture(t.tex);
      gl!.deleteFramebuffer(t.fb);
    }
    scene = null;
    histA = null;
    histB = null;
    bloomA = null;
    bloomB = null;
    settled = 0;
  }

  /** Returns false if any render target failed to allocate. */
  function resize(): boolean {
    const rect = host.getBoundingClientRect();
    const dpr = software
      ? 1
      : Math.min(window.devicePixelRatio || 1, Math.max(1, opts.maxDpr));
    const cssW = Math.max(1, Math.round(rect.width));
    const cssH = Math.max(1, Math.round(rect.height));
    const scale = software ? 0.34 : Math.min(1, Math.max(0.4, opts.resolution));
    const w = Math.max(2, Math.round(cssW * dpr));
    const h = Math.max(2, Math.round(cssH * dpr));
    const sw = Math.max(2, Math.round(w * scale));
    const sh = Math.max(2, Math.round(h * scale));
    if (w === width && h === height && sw === sceneW && sh === sceneH) return true;
    width = w;
    height = h;
    sceneW = sw;
    sceneH = sh;
    canvas.width = w;
    canvas.height = h;
    canvas.style.width = cssW + "px";
    canvas.style.height = cssH + "px";
    dropTargets();
    scene = makeTarget(sw, sh);
    histA = makeTarget(sw, sh);
    histB = makeTarget(sw, sh);
    const bw = Math.max(2, sw >> 2);
    const bh = Math.max(2, sh >> 2);
    bloomA = makeTarget(bw, bh);
    bloomB = makeTarget(bw, bh);
    return !!(scene && histA && histB && bloomA && bloomB);
  }

  let clock = reduced ? 6 : 0;
  let lastFrame = 0;
  let running = true;
  let docVisible = !document.hidden;
  let intersecting = true;
  let raf = 0;
  let idle = false;

  function effectiveVisible() {
    return docVisible && intersecting;
  }

  function pass(prog: Prog, target: Target | null) {
    gl!.useProgram(prog.program);
    gl!.bindFramebuffer(gl!.FRAMEBUFFER, target ? target.fb : null);
    gl!.viewport(0, 0, target ? target.w : width, target ? target.h : height);
  }

  function draw() {
    gl!.drawArrays(gl!.TRIANGLES, 0, 3);
  }

  function bind(tex: WebGLTexture, unit: number) {
    gl!.activeTexture(gl!.TEXTURE0 + unit);
    gl!.bindTexture(gl!.TEXTURE_2D, tex);
  }

  const HALTON: Array<[number, number]> = [
    [0.5, 0.333],
    [0.25, 0.667],
    [0.75, 0.111],
    [0.125, 0.444],
    [0.625, 0.778],
    [0.375, 0.222],
    [0.875, 0.556],
    [0.0625, 0.889],
  ];

  function render(t: number) {
    if (!sceneProg || !blendProg || !brightProg || !blurProg || !compProg) return;
    if (!scene || !histA || !histB || !bloomA || !bloomB) return;
    const C = opts;

    const az = (C.azimuth + C.orbitSpeed * t) * RAD;
    const el = Math.max(-88, Math.min(88, C.elevation)) * RAD;
    const dist = Math.max(2.2, C.distance);
    const ce = Math.cos(el);
    const camX = dist * ce * Math.cos(az);
    const camY = dist * Math.sin(el);
    const camZ = dist * ce * Math.sin(az);

    const fx = -camX / dist,
      fy = -camY / dist,
      fz = -camZ / dist;
    let rx = fz,
      ry = 0,
      rz = -fx;
    const rl = Math.hypot(rx, ry, rz) || 1;
    rx /= rl;
    ry /= rl;
    rz /= rl;
    let ux = ry * fz - rz * fy;
    let uy = rz * fx - rx * fz;
    let uz = rx * fy - ry * fx;
    const cr = Math.cos(C.roll * RAD);
    const sr = Math.sin(C.roll * RAD);
    const RX = rx * cr + ux * sr,
      RY = ry * cr + uy * sr,
      RZ = rz * cr + uz * sr;
    const UX = -rx * sr + ux * cr,
      UY = -ry * sr + uy * cr,
      UZ = -rz * sr + uz * cr;

    const hot = hexToLinear(C.hotColor);
    const mid = hexToLinear(C.midColor);
    const cool = hexToLinear(C.coolColor);
    const outer = Math.max(C.diskInner + 0.5, C.diskOuter);

    pass(sceneProg, scene);
    const u = sceneProg.u;
    gl!.uniform2f(u.uRes!, scene.w, scene.h);
    gl!.uniform1f(u.uTime!, t);
    gl!.uniform3f(u.uCamPos!, camX, camY, camZ);
    gl!.uniform3f(u.uRight!, RX, RY, RZ);
    gl!.uniform3f(u.uUp!, UX, UY, UZ);
    gl!.uniform3f(u.uFwd!, fx, fy, fz);
    gl!.uniform1f(
      u.uTanHalf!,
      Math.tan((Math.max(8, Math.min(110, C.fov)) * 0.5 * RAD))
    );
    gl!.uniform2f(u.uFocus!, C.focus[0], 1 - C.focus[1]);
    gl!.uniform1f(
      u.uSteps!,
      software ? 130 : Math.max(60, Math.min(460, Math.round(C.steps)))
    );
    gl!.uniform1f(u.uSkyR!, Math.max(dist * 1.35, outer * 2.4));
    gl!.uniform1f(u.uDiskIn!, Math.max(1.05, C.diskInner));
    gl!.uniform1f(u.uDiskOut!, outer);
    gl!.uniform1f(u.uThick!, Math.max(0.02, C.diskThickness));
    gl!.uniform1f(u.uDensity!, Math.max(0, C.diskDensity));
    gl!.uniform1f(u.uSpin!, C.spinSpeed * 6.2831853);
    gl!.uniform1f(u.uGrain!, Math.max(0.02, C.grain));
    gl!.uniform1f(u.uBright!, Math.max(0, C.brightness));
    gl!.uniform1f(u.uDoppler!, Math.max(0, Math.min(1, C.doppler)));
    gl!.uniform3f(u.uHot!, hot[0], hot[1], hot[2]);
    gl!.uniform3f(u.uMid!, mid[0], mid[1], mid[2]);
    gl!.uniform3f(u.uCool!, cool[0], cool[1], cool[2]);
    gl!.uniform1f(u.uStars!, Math.max(0, C.starBrightness));
    gl!.uniform1f(u.uEncode!, hdr ? 0 : 1);
    const h = HALTON[settled % HALTON.length];
    gl!.uniform2f(u.uJitter!, h[0] - 0.5, h[1] - 0.5);
    gl!.uniform1f(u.uSeed!, (settled % 64) * 17.13);
    draw();

    const alpha = settled === 0 ? 1 : 0.14;
    pass(blendProg, histB);
    bind(scene.tex, 0);
    bind(histA.tex, 1);
    gl!.uniform1i(blendProg.u.uCur!, 0);
    gl!.uniform1i(blendProg.u.uPrev!, 1);
    gl!.uniform1f(blendProg.u.uAlpha!, alpha);
    draw();
    const shown = histB;
    const tmp = histA;
    histA = histB;
    histB = tmp;
    settled++;

    pass(brightProg, bloomA);
    bind(shown.tex, 0);
    gl!.uniform1i(brightProg.u.uTex!, 0);
    gl!.uniform2f(brightProg.u.uTexel!, 1 / shown.w, 1 / shown.h);
    gl!.uniform1f(brightProg.u.uDecode!, hdr ? 0 : 1);
    gl!.uniform1f(brightProg.u.uPack!, pack);
    gl!.uniform1f(brightProg.u.uThreshold!, 0.85);
    draw();

    const blurStep = (src: Target, dst: Target, dx: number, dy: number) => {
      pass(blurProg!, dst);
      bind(src.tex, 0);
      gl!.uniform1i(blurProg!.u.uTex!, 0);
      gl!.uniform2f(blurProg!.u.uStep!, dx / dst.w, dy / dst.h);
      draw();
    };
    blurStep(bloomA, bloomB, 1, 0);
    blurStep(bloomB, bloomA, 0, 1);
    blurStep(bloomA, bloomB, 2.6, 0);
    blurStep(bloomB, bloomA, 0, 2.6);

    pass(compProg, null);
    bind(shown.tex, 0);
    bind(bloomA.tex, 1);
    gl!.uniform1i(compProg.u.uScene!, 0);
    gl!.uniform1i(compProg.u.uBloom!, 1);
    gl!.uniform2f(compProg.u.uRes!, width, height);
    gl!.uniform1f(compProg.u.uDecode!, hdr ? 0 : 1);
    gl!.uniform1f(compProg.u.uPack!, pack);
    gl!.uniform1f(compProg.u.uGlow!, Math.max(0, C.glow) * 0.26);
    gl!.uniform1f(compProg.u.uExposure!, Math.max(0.05, C.exposure));
    gl!.uniform1f(compProg.u.uVignette!, Math.max(0, Math.min(1, C.vignette)));
    gl!.uniform1f(
      compProg.u.uScrimDir!,
      C.scrim === "left"
        ? 1
        : C.scrim === "right"
        ? 2
        : C.scrim === "top"
        ? 3
        : C.scrim === "bottom"
        ? 4
        : 0
    );
    gl!.uniform1f(compProg.u.uScrimAmt!, Math.max(0, Math.min(1, C.scrimStrength)));
    gl!.uniform1f(compProg.u.uSeed!, (t * 60) % 1000);
    draw();
  }

  function settle(passes: number) {
    for (let i = 0; i < passes; i++) render(clock);
  }

  function isIdleNow() {
    return opts.paused || reduced;
  }

  function stopLoop() {
    if (raf) cancelAnimationFrame(raf);
    raf = 0;
    idle = true;
  }

  function startLoop() {
    if (!running || raf) return;
    idle = false;
    lastFrame = 0;
    raf = requestAnimationFrame(tick);
  }

  function tick(now: number) {
    if (!running) return;
    if (!effectiveVisible()) {
      raf = requestAnimationFrame(tick);
      lastFrame = now;
      return;
    }
    if (isIdleNow()) {
      // Draw the settled still once, then go fully idle — no more rAF churn
      // for a frame nobody asked to change. Something waking us (resize,
      // visibility, motion-preference change) calls startLoop() again.
      settle(16);
      stopLoop();
      return;
    }
    raf = requestAnimationFrame(tick);
    const dt = lastFrame ? Math.min(0.05, (now - lastFrame) / 1000) : 0;
    lastFrame = now;
    clock += dt;
    render(clock);
  }

  if (!build()) {
    giveUp("build-failed");
    return { cleanup: () => {}, ready };
  }
  if (!resize()) {
    giveUp("framebuffer");
    return { cleanup: () => {}, ready };
  }
  settle(isIdleNow() ? 16 : 1);
  resolveReady(true);
  if (!isIdleNow()) {
    startLoop();
  } else {
    idle = true;
  }

  const ro = new ResizeObserver(() => {
    if (!resize()) {
      giveUp("framebuffer");
      return;
    }
    if (isIdleNow()) settle(16);
    else startLoop();
  });
  ro.observe(host);

  const io = new IntersectionObserver(
    (entries) => {
      intersecting = entries[0]?.isIntersecting ?? true;
      if (effectiveVisible() && !isIdleNow()) startLoop();
    },
    { threshold: 0 }
  );
  io.observe(host);

  const onVisibility = () => {
    docVisible = !document.hidden;
    if (effectiveVisible() && !isIdleNow()) startLoop();
  };

  const onReducedChange = (e: MediaQueryListEvent) => {
    reduced = e.matches;
    if (reduced) {
      settle(16);
      stopLoop();
    } else if (effectiveVisible() && !opts.paused) {
      startLoop();
    }
  };
  if (typeof window.matchMedia === "function") {
    reducedMQ = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (typeof reducedMQ.addEventListener === "function") {
      reducedMQ.addEventListener("change", onReducedChange);
    }
  }

  const onLost = (e: Event) => {
    e.preventDefault();
    running = false;
    stopLoop();
    canvas.style.display = "none";
  };
  const onRestored = () => {
    width = height = sceneW = sceneH = 0;
    if (!build()) {
      giveUp("lost");
      return;
    }
    canvas.style.display = "";
    host.dataset.webgl = "";
    if (!resize()) {
      giveUp("framebuffer");
      return;
    }
    running = true;
    settle(isIdleNow() ? 16 : 1);
    if (!isIdleNow()) startLoop();
  };

  document.addEventListener("visibilitychange", onVisibility);
  canvas.addEventListener("webglcontextlost", onLost);
  canvas.addEventListener("webglcontextrestored", onRestored);

  function cleanup() {
    running = false;
    stopLoop();
    ro.disconnect();
    io.disconnect();
    document.removeEventListener("visibilitychange", onVisibility);
    canvas.removeEventListener("webglcontextlost", onLost);
    canvas.removeEventListener("webglcontextrestored", onRestored);
    if (reducedMQ && typeof reducedMQ.removeEventListener === "function") {
      reducedMQ.removeEventListener("change", onReducedChange);
    }
    dropTargets();
    if (vbo) gl!.deleteBuffer(vbo);
    for (const p of [sceneProg, blendProg, brightProg, blurProg, compProg]) {
      if (p) gl!.deleteProgram(p.program);
    }
    // Context deliberately left alive — see the reference component's own
    // note: explicitly losing it here is a trap for any environment that
    // remounts onto the same canvas, and the browser reclaims everything
    // when the iframe itself is torn down regardless.
  }

  return { cleanup, ready };
}
