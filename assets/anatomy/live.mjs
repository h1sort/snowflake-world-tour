// Live behaviour: an idle tour that cycles a passing ticket and a rejected one,
// pointer and keyboard to take away (or give back) a piece of evidence.
// Inlined after the kit, geo.mjs, model.mjs and parts.mjs; it is not an ES module on its own.

const stage = document.querySelector(".iso-stage");
const svgEl = stage.querySelector("svg");
const readout = document.querySelector("[data-readout]");
const live = document.querySelector(".sr");
const still = matchMedia("(prefers-reduced-motion: reduce)");
const part = (name) => svgEl.querySelector('[data-part="' + name + '"]');
const E = {
  car: part("car"), ticket: part("ticket"), oldTicket: part("oldTicket"), drawer: part("drawer"), pad: part("pad"), pinsLow: part("pinsLow"),
  pinsUp: part("pinsUp"), needle: part("needle"), ramLow: part("ramLow"), ramTop: part("ramTop"), keyA: part("keyA"), keyB: part("keyB"),
  shutter: part("shutter"), paddle: part("paddle"), slip: part("slip"),
  wirePermit: part("wirePermit"), wireA: part("wireA"), wireB: part("wireB"),
  ink: part("ticket").querySelector('[data-part="ink"]'), stamp: part("ticket").querySelector('[data-part="stamp"]'),
};
const holes = [0, 1, 2, 3].map((i) => ({ hole: part("ticket").querySelector('[data-part="hole' + i + '"]'), blank: part("ticket").querySelector('[data-part="blank' + i + '"]') }));
const query = new URLSearchParams(location.search);
const frozenAt = query.has("t") ? Number(query.get("t")) : null;
if (query.has("bare") || location.hash === "#bare") document.body.classList.add("bare");
if (query.has("w")) {
  const w = Number(query.get("w"));
  svgEl.style.width = w + "px";
  svgEl.style.height = Math.round((w * H) / W) + "px";
  document.querySelector(".iso-plate").style.width = w + "px";
}

const TOUR_MISSING = [2];
const run = {
  t: 0,
  missing: query.has("miss") ? query.get("miss").split(",").filter(Boolean).map((n) => Number(n) - 1) : [],
  prior: null,
  index: 0,
  manual: query.has("miss"),
  shown: null,
  blendFrom: null,
  blendAt: 0,
  clock: 0,
  quietAt: 0,
};
let frame = 0, last = 0, visible = false, resumeTimer = 0, lastText = "", lastSpoken = "";

const mixNumber = (a, b, x) => a + (b - a) * x;
function blendStates(from, to, x) {
  const out = { ...to };
  for (const key of Object.keys(to)) {
    const a = from[key], b = to[key];
    if (typeof b === "number" && typeof a === "number") out[key] = mixNumber(a, b, x);
    else if (Array.isArray(b) && Array.isArray(a) && typeof b[0] === "number" && a.length === b.length) out[key] = b.map((v, i) => mixNumber(a[i], v, x));
  }
  return out;
}

function restart(missing, keepPrior) {
  run.missing = missing;
  if (!keepPrior) run.prior = null;
  run.t = 0;
  run.blendFrom = run.shown;
  run.blendAt = run.clock;
}

function wire(el, on) {
  const w = el.firstElementChild;
  if (!w) return;
  if (on) {
    w.setAttribute("data-on", "");
    w.firstElementChild.setAttribute("data-flow", "");
  } else {
    w.removeAttribute("data-on");
    w.firstElementChild.removeAttribute("data-flow");
  }
}

const cache = {};
function setHTML(name, html) {
  if (cache[name] === html) return;
  cache[name] = html;
  E[name].innerHTML = html;
}
function setAttr(el, name, value) {
  const key = el.dataset.part + "|" + name;
  if (cache[key] === value) return;
  cache[key] = value;
  el.setAttribute(name, value);
}

function draw(s) {
  const pushed = Math.max(0, PADDLE.y0 + PADDLE.d + PUSH * s.pushed + TICKET.hd);
  const drop = -3.8 * ramp(pushed, 22, 44) - 2.7 * ramp(pushed, 49, 54);
  const tx = s.pushed > 0.001 ? S3 : s.cx;
  setAttr(E.car, "transform", translateAlong(P, [s.cx, 0, 0]));
  setAttr(E.ticket, "transform", translateAlong(P, [tx, pushed, drop]));
  setAttr(E.ticket, "opacity", s.ticketAlpha.toFixed(3));
  const cls = "ticket" + (s.rejected ? " rej" : "");
  const tk = E.ticket.firstElementChild;
  if (tk.getAttribute("class") !== cls) tk.setAttribute("class", cls);
  setAttr(E.oldTicket, "opacity", s.oldBin.toFixed(3));
  setAttr(E.ink, "opacity", s.ink.toFixed(3));
  setAttr(E.stamp, "opacity", s.stamp.toFixed(3));
  holes.forEach((h, i) => {
    const gone = run.missing.includes(i);
    h.hole.style.display = gone ? "none" : "";
    h.blank.style.display = gone ? "" : "none";
  });
  setHTML("drawer", PARTS.drawerSvg(s.drawer));
  setHTML("pad", PARTS.readingPad(s.pad));
  setHTML("pinsLow", PARTS.gaugeLower(s.pins));
  setHTML("pinsUp", PARTS.gaugeUpper(s.pins));
  setAttr(E.needle, "d", PARTS.needleD(s.dial));
  setHTML("ramLow", PARTS.ramLower(s.ram));
  setHTML("ramTop", PARTS.ramTop(s.ram));
  setHTML("keyA", PARTS.keyBow(0, s.keyA));
  setHTML("keyB", PARTS.keyBow(1, s.keyB));
  setHTML("shutter", PARTS.shutter(s.shutter));
  setHTML("paddle", PARTS.paddle(s.gate));
  const slipOut = s.slip > 0.001;
  setAttr(E.slip, "transform", translateAlong(P, [SLIP.stroke * (slipOut ? s.slip : 1), 0, 0]));
  setAttr(E.slip, "opacity", (slipOut ? 1 : s.oldSlip).toFixed(3));
  wire(E.wirePermit, s.permit > 0.5);
  wire(E.wireA, s.keyA > 0.5);
  wire(E.wireB, s.keyB > 0.5);
  if (s.text !== lastText) {
    lastText = s.text;
    readout.textContent = s.text;
  }
}

function describe(s) {
  return s.text;
}

function step(dt) {
  const calm = still.matches;
  if (frozenAt !== null) {
    run.t = frozenAt;
  } else if (calm) {
    run.t = run.missing.length ? TIMES.gate[1] : TIMES.ramDown[1] - 0.05;
  } else {
    run.t += dt;
    run.clock += dt;
    const length = lengthOf(run.missing);
    if (run.t >= length) {
      run.prior = run.missing.length ? "reject" : "pass";
      run.index++;
      if (!run.manual) run.missing = run.index % 2 === 1 ? TOUR_MISSING : [];
      run.t = 0;
    }
  }
  let s = stateAt(run.t, run.missing, run.prior);
  if (run.blendFrom && !calm) {
    const x = Math.min(1, (run.clock - run.blendAt) / 0.7);
    if (x < 1) s = blendStates(run.blendFrom, s, x * x * (3 - 2 * x));
    else run.blendFrom = null;
  }
  run.shown = s;
  draw(s);
  if (s.text !== lastSpoken && (s.phase !== run.lastPhase)) {
    run.lastPhase = s.phase;
  }
}

function tick(now) {
  const dt = last ? Math.min((now - last) / 1000, 1 / 30) : 1 / 60;
  last = now;
  step(dt);
  frame = visible && frozenAt === null && !still.matches ? requestAnimationFrame(tick) : 0;
}
const go = () => {
  if (!frame && visible) {
    last = 0;
    frame = requestAnimationFrame(tick);
  }
};

// Taking a piece of evidence away from the ticket (or giving it back) restarts the cycle with that setting.
function toggle(index) {
  const next = run.missing.includes(index) ? run.missing.filter((n) => n !== index) : [...run.missing, index].sort();
  run.manual = true;
  clearTimeout(resumeTimer);
  resumeTimer = setTimeout(() => {
    run.manual = false;
  }, 12000);
  restart(next, false);
  const word = next.length ? "falta la evidencia " + (next[0] + 1) : "evidencia completa";
  live.textContent = "Siguiente solicitud: " + word;
  if (frozenAt !== null || still.matches) step(0);
  go();
}
function reset() {
  run.manual = false;
  clearTimeout(resumeTimer);
  restart([], false);
  live.textContent = "Siguiente solicitud: evidencia completa";
  if (frozenAt !== null || still.matches) step(0);
  go();
}

stage.addEventListener("keydown", (event) => {
  if (event.key >= "1" && event.key <= "4") {
    event.preventDefault();
    toggle(Number(event.key) - 1);
  } else if (event.key === " " || event.key === "Enter") {
    event.preventDefault();
    toggle(2);
  } else if (event.key === "Escape") {
    event.preventDefault();
    reset();
  }
});
stage.addEventListener("pointerdown", (event) => {
  const box = svgEl.getBoundingClientRect();
  const x = ((event.clientX - box.left) / box.width) * W;
  const y = ((event.clientY - box.top) / box.height) * H;
  let best = -1, bestD = 22;
  for (let i = 0; i < 4; i++) {
    const [px, py] = iso([S2 + HOLE_DX[i], HOLE_Y, 40], P);
    const d = Math.hypot(px - x, py - y);
    if (d < bestD) { best = i; bestD = d; }
  }
  if (best >= 0) toggle(best);
});
new IntersectionObserver((entries) => {
  visible = entries[entries.length - 1].isIntersecting;
  if (visible) go();
}, { rootMargin: "120px 0px" }).observe(stage);

stage.setAttribute("aria-description", "Pulsa 1 a 4 para quitar la evidencia de un pin");
step(0);
if (frozenAt === null && !still.matches) {
  // start inside the first cycle so the page never opens on an empty bench
  visible = true;
  go();
}
