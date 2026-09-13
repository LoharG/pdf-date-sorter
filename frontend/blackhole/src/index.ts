import { mountBlackHole, BlackHoleOptions } from "./blackhole";

declare global {
  interface Window {
    __BLACKHOLE_OPTS__?: Partial<BlackHoleOptions>;
  }
}

function boot() {
  const host = document.getElementById("bh-host");
  const canvas = document.getElementById("bh-canvas") as HTMLCanvasElement | null;
  if (!host || !canvas) return;

  const opts = window.__BLACKHOLE_OPTS__ || {};
  const { ready } = mountBlackHole(host, canvas, opts);

  ready.then((ok) => {
    // Tell the parent Streamlit page our rendered height so the iframe box
    // sizes correctly (components.v1.html sizes by the `height` kwarg, but
    // this also lets us report a WebGL failure for debugging without ever
    // affecting anything outside this iframe).
    host.dataset.ready = ok ? "true" : "false";
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}
