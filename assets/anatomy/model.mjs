// The machine's model: a pure function of time. Every number the figure shows comes from here.
// One cycle = one request ticket riding the carriage through the three stations.
// Needs HOME, S1, S2, S3, PIN_REACH, PIN_DEPTH from geo.mjs.

export const reachShare = () => PIN_REACH / (PIN_REACH + PIN_DEPTH);
export const ramp = (t, a, b) => {
  const x = Math.min(1, Math.max(0, (t - a) / (b - a)));
  return x * x * (3 - 2 * x);
};
const lerp = (a, b, x) => a + (b - a) * x;

// Event times in seconds from the start of a cycle. Pass and reject share everything until the press.
export const TIMES = {
  fadeIn: [0, 0.7],
  toS1: [0.5, 2.2],
  drawerOut: [2.3, 3.2],
  padDown: [3.1, 3.6],
  ink: [3.4, 3.9],
  padUp: [3.9, 4.4],
  drawerIn: [4.3, 5.1],
  toS2: [5.2, 7.0],
  pinStart: 7.1,
  pinSpan: 0.6,
  pinStagger: 0.16,
  permit: [8.6, 9.0],
  pinsUp: [9.0, 9.6],
  toS3: [9.8, 11.6],
  keyA: [11.8, 12.4],
  keyB: [12.6, 13.2],
  shutterOpen: [13.3, 13.8],
  ramDown: [13.9, 14.3],
  stamp: [14.2, 14.5],
  ramUp: [14.7, 15.3],
  shutterShut: [15.4, 15.8],
  slipOut: [15.4, 16.2],
  keysBack: [16.2, 16.8],
  backPass: [16.6, 18.4],
  endPass: 19.0,
  // reject branch
  gate: [12.4, 13.4],
  gateBack: [13.9, 14.8],
  backReject: [15.0, 16.8],
  endReject: 17.4,
};

export const verdictOf = (missing) => ({ count: 4 - missing.length, pass: missing.length === 0 });
export const lengthOf = (missing) => (missing.length === 0 ? TIMES.endPass : TIMES.endReject);

export function stateAt(t, missing, prior) {
  const T = TIMES;
  const v = verdictOf(missing);
  const r0 = reachShare();
  const s = { t, pass: v.pass, count: v.count, missing };

  s.ticketAlpha = ramp(t, ...T.fadeIn) * (v.pass ? 1 - ramp(t, T.endPass - 0.7, T.endPass) : 1);
  // carriage
  let cx = lerp(HOME, S1, ramp(t, ...T.toS1));
  cx = lerp(cx, S2, ramp(t, ...T.toS2));
  cx = lerp(cx, S3, ramp(t, ...T.toS3));
  const back = v.pass ? T.backPass : T.backReject;
  cx = lerp(cx, HOME, ramp(t, ...back));
  s.cx = cx;
  // station 1
  s.drawer = ramp(t, ...T.drawerOut) - ramp(t, ...T.drawerIn);
  s.pad = ramp(t, ...T.padDown) - ramp(t, ...T.padUp);
  s.ink = ramp(t, ...T.ink);
  // station 2
  s.pins = [0, 1, 2, 3].map((i) => {
    const a = T.pinStart + T.pinStagger * i;
    const goal = missing.includes(i) ? r0 : 1;
    return goal * ramp(t, a, a + T.pinSpan) * (1 - ramp(t, ...T.pinsUp));
  });
  // The dial holds its reading (a tally latch) after the pins lift.
  const seatedAt = (time) => {
    let sum = 0;
    for (let i = 0; i < 4; i++) {
      const a = T.pinStart + T.pinStagger * i;
      const goal = missing.includes(i) ? r0 : 1;
      const p = goal * ramp(time, a, a + T.pinSpan);
      sum += Math.min(1, Math.max(0, (p - r0) / (1 - r0)));
    }
    return sum;
  };
  s.dial = seatedAt(Math.min(t, T.pinsUp[0]));
  s.seated = Math.round(s.dial * 100) / 100;
  s.permit = v.pass ? ramp(t, ...T.permit) : 0;
  // station 3
  s.keyA = v.pass ? ramp(t, ...T.keyA) - ramp(t, ...T.keysBack) : 0;
  s.keyB = v.pass ? ramp(t, ...T.keyB) - ramp(t, ...T.keysBack) : 0;
  s.shutter = v.pass ? ramp(t, ...T.shutterOpen) - ramp(t, ...T.shutterShut) : 0;
  s.ram = v.pass ? ramp(t, ...T.ramDown) - ramp(t, ...T.ramUp) : 0;
  s.stamp = v.pass ? ramp(t, ...T.stamp) : 0;
  s.slip = v.pass ? ramp(t, ...T.slipOut) : 0;
  s.gate = v.pass ? 0 : ramp(t, ...T.gate) - ramp(t, ...T.gateBack);
  s.pushed = v.pass ? 0 : ramp(t, ...T.gate);
  s.rejected = !v.pass && t >= T.gate[0] + 0.15;
  // what the previous cycle left on the bench fades out while the next ticket arrives
  s.oldSlip = prior === "pass" ? 1 - ramp(t, 0.1, 1.1) : 0;
  s.oldBin = prior === "reject" ? 1 - ramp(t, 0.1, 1.1) : 0;
  s.text = textAt(t, missing, s);
  s.phase = phaseOf(t, v.pass);
  return s;
}

export function phaseOf(t, pass) {
  const T = TIMES;
  if (t < T.toS1[1]) return "carga";
  if (t < T.toS2[0]) return "contexto";
  if (t < T.toS2[1]) return "traslado";
  if (t < T.toS3[0]) return "juicio";
  if (t < T.toS3[1]) return "traslado";
  return "acción";
}

export function textAt(t, missing, s) {
  const T = TIMES;
  const v = verdictOf(missing);
  const n = (value) => `evidencia ${value}/4`;
  if (t < T.drawerOut[0]) return "solicitud · en el carril";
  if (t < T.toS2[0] + 0.9) return t < T.padDown[0] ? "contexto · cajón v3 abierto" : "contexto · definición v3 aprobada";
  // evidence counter: pins that have seated so far
  const seatedNow = s.pins.filter((p, i) => !missing.includes(i) && p > 0.985).length;
  const reached = seatedNow;
  if (t < T.permit[0]) return `${n(reached)} · comprobando`;
  if (t < T.toS3[0]) return v.pass ? `${n(4)} · pasa el calibre` : `${n(v.count)} · falta evidencia ${missing[0] + 1}`;
  if (t < T.toS3[1] + 0.2) return v.pass ? `${n(4)} · en camino a la prensa` : `${n(v.count)} · falta evidencia ${missing[0] + 1}`;
  if (v.pass) {
    if (t < T.keyA[0]) return `${n(4)} · espera validación`;
    if (t < T.keyB[0]) return `${n(4)} · validación de la aplicación`;
    if (t < T.ramDown[0]) return `${n(4)} · aprobación humana`;
    if (t < T.slipOut[0]) return `${n(4)} · aprobación humana · ejecutando`;
    return `${n(4)} · aprobación humana · efecto: 1 recibo`;
  }
  if (t < T.gate[0]) return `${n(v.count)} · validación fallida`;
  return `${n(v.count)} · rechazada · sin efecto`;
}
