// Contexto · Juicio · Acción — an isometric machine for the Snowflake World Tour talk.
//   node build.mjs            writes machine.html (light) and machine-dark.html
//   node build.mjs --light    only the light page
// The model (model.mjs), the world (geo.mjs) and the builders (parts.mjs) are inlined into the page,
// so the live figure draws exactly what the build draws.
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as kit from "/home/claude/vendor/anatomy/kit/iso-kit.mjs";
import { kitScript } from "/home/claude/vendor/anatomy/scripts/inline-kit.mjs";
import * as GEO from "./geo.mjs";
import * as MODEL from "./model.mjs";

Object.assign(globalThis, GEO, MODEL);
const { makeParts } = await import("./parts.mjs");

const HERE = dirname(fileURLToPath(import.meta.url));
const only = process.argv.includes("--light") ? "light" : process.argv.includes("--dark") ? "dark" : "both";
const strip = (file) => readFileSync(join(HERE, file), "utf8").replace(/^export /gm, "");

// ── camera ───────────────────────────────────────────────────────────────
const corners = [
  ...kit.boxCorners({ x: PLATE.x, y: PLATE.y, w: PLATE.w, d: FRONT - PLATE.y }, -PLATE_H - FOOT_H, 0),
  ...kit.boxCorners({ x: LOBE_X, y: PLATE.y, w: PLATE.x + PLATE.w - LOBE_X, d: PLATE.d }, -PLATE_H - FOOT_H, 0),
  [S2, HOLE_Y, 80],
  [S2 - 30, -96, 66],
  [ARM1.x, -96, 60],
  [CAB.x, -96, 46],
  [HOME - 36, -88, 20],
  [PARM.x, -96, 58],
  [RAM.x, RAM.y, 84],
  [KEYS[1].x + 12, 84, 4],
  [HOME - 36, 0, 2],
  [TRAY.x + TRAY.w, -92, 20],
];
const P = kit.fitProjection(corners, W, H, { pad: 22, azimuth: AZ, elevation: EL });
const parts = makeParts(kit, P);
const { S, L, at } = parts;

// ── initial state ────────────────────────────────────────────────────────
const s0 = stateAt(14.1, [], null);
const sReject = stateAt(13.4, [2], null);

// ── layers, back to front ────────────────────────────────────────────────
const g = (name, inner, extra = "") => `<g data-part="${name}"${extra}>${inner}</g>`;
const tr = (x, y = 0, z = 0) => kit.translateAlong(P, [x, y, z]);

const layer0 = [
  parts.base(),
  parts.rails(),
  parts.feeder(),
  parts.cabinet(),
  g("drawer", parts.drawerSvg(0)),
  parts.gaugeColumn(),
  parts.pressColumn(),
  parts.keyBase(0),
  parts.relayBox(),
  parts.paddleHousing(),
  parts.tray(),
  `<g clip-path="url(#slipclip)">${g("slip", parts.slip(0), ` transform="${tr(0)}" opacity="0"`)}</g>`,
  parts.tray2(),
  parts.wires(),
].join("");
const layer1 = g("car", parts.carriage(), ` transform="${tr(HOME)}"`);
const layer1b = parts.binBack() + g("oldTicket", parts.ticket("rej"), ` transform="${tr(S3, PADDLE.y0 + PADDLE.d + PUSH + TICKET.hd, -6.5)}" opacity="0"`);
const layer2 = g("paddle", parts.paddle(0));
const layer3 = g("ticket", parts.ticket(), ` transform="${tr(HOME)}" opacity="0"`);
const layer4 = parts.binFront();
const layer5 = [
  g("shutter", parts.shutter(0)),
  g("pad", parts.readingPad(0)),
  g("pinsLow", parts.gaugeLower([0, 0, 0, 0])),
  g("ramLow", parts.ramLower(0)),
  g("keyA", parts.keyBow(0, 0)),
].join("");
const layer6 = parts.readingArm() + parts.gaugeArm() + parts.pressArm();
const layer7 = [
  g("pinsUp", parts.gaugeUpper([0, 0, 0, 0])),
  parts.dial(),
  `<path data-part="needle" class="iso-line" data-tone="hi" data-free="start" style="stroke-width:1.1" d="${parts.needleD(0)}"/>`,
  parts.pressHousing(),
  g("ramTop", parts.ramTop(0)),
  parts.keyBase(1),
  g("keyB", parts.keyBow(1, 0)),
].join("");

const LABEL =
  "Una máquina isométrica sobre un banco. Una solicitud, un ticket, viaja en un carro por un solo riel y pasa por tres estaciones. En la primera, un cajón de un fichero abre la definición aprobada y versionada, y un brazo lector la presiona contra el ticket. En la segunda, un calibre pasa o no pasa con cuatro pines de evidencia: sólo si los cuatro asientan, una lectura marca 4 y se concede el permiso. En la tercera, una prensa de sello sólo baja si el calibre pasó y dos llaves, la de la aplicación y la humana, están giradas; entonces sella el ticket y entrega un recibo. Si falta evidencia, la prensa queda bloqueada y una compuerta empuja el ticket a un cajón de rechazos, sin efecto.";

const svg = kit.figureSvg({
  width: W,
  height: H,
  label: LABEL,
  body: [`<defs>${parts.slipClip()}</defs>`, layer0, layer1, layer1b, layer2, layer3, layer4, layer5, layer6, layer7],
});

// ── live page ────────────────────────────────────────────────────────────
const KIT_NAMES = [
  "solidSvg", "lineSvg", "dotsSvg", "wireSvg", "faceTextSvg", "slabOf", "cylinder", "extrude", "haloOf", "sideSeam", "planOutline", "insetPlan",
  "corners", "ring", "topTicks", "lineOnTop", "sideRing", "sideArc", "knurl", "sideMatrix", "topMatrix", "pathOf", "segment", "iso", "depthOf",
];

const live = `
const P = ${JSON.stringify(P)};
const kk = { ${KIT_NAMES.join(", ")} };
${strip("geo.mjs")}
${strip("model.mjs")}
${strip("parts.mjs")}
const PARTS = makeParts(kk, P);
${strip("live.mjs")}
`;

const legend = {
  keys: [
    { mark: "lit", label: "La solicitud: el ticket que recorre las tres estaciones" },
    { mark: "raised", label: "Contexto, juicio y acción: el mismo modelo, tres consecuencias distintas" },
    { mark: "red", label: "Rechazo: la solicitud sale sin efecto" },
  ],
  caption:
    "Contexto: una respuesta sólo vale bajo una definición aprobada y versionada. Juicio: el veredicto exige evidencia obligatoria; el agente puede mirar más, pero no puede dejar de ser obligatoria. Acción: el modelo propone; la aplicación valida, una persona aprueba, se ejecuta una vez y regresa un recibo. Si la validación falla, no hay efecto.",
};

const EXTRA_CSS = `
.iso{--lit-blue:#29B5E8;--rej:#FF9F36}
.iso[data-theme="dark"]{--anatomy-lit:#29B5E8}
.iso[data-theme]{--anatomy-lit:#29B5E8;--anatomy-red:#FF9F36}
.iso .ticket.rej .iso-edge,.iso .rej-liner>.iso-edge,.iso .rej-wall>.iso-edge{stroke:var(--rej)}
.iso .ticket.rej .iso-fill,.iso .ticket.rej .iso-top,.iso .ticket.rej .iso-shade{fill:color-mix(in srgb,var(--rej) 36%,var(--anatomy-paper))}
.iso .rej-liner>.iso-top,.iso .rej-liner>.iso-fill{fill:color-mix(in srgb,var(--rej) 30%,var(--anatomy-paper))}
.iso .rej-wall>.iso-fill{fill:color-mix(in srgb,var(--rej) 18%,var(--anatomy-shade-3))}
.iso .rej-wall>.iso-top{fill:color-mix(in srgb,var(--rej) 26%,var(--anatomy-top))}
.iso .iso-line.rej-line{stroke:var(--rej)}
.iso .iso-line[data-tone="hi"].ink{stroke:var(--anatomy-hi)}
.iso .ticket .iso-fill,.iso .ticket .iso-top{fill:color-mix(in srgb,var(--lit-blue) 24%,#fff)}
.iso .ticket .iso-shade{fill:color-mix(in srgb,var(--lit-blue) 42%,var(--anatomy-shade-3))}
.iso .ticket:not(.rej) .iso-edge{stroke:color-mix(in srgb,var(--lit-blue) 70%,#000)}
.iso .ticket .iso-edge{stroke-width:1}
.iso[data-theme="light"]{--anatomy-weight:.9px;--anatomy-shade-0:#8d8d88;--anatomy-shade-1:#a4a49f;--anatomy-shade-2:#bbbbb6;--anatomy-shade-3:#d1d1cc;--anatomy-hi:#0a0a0c;--anatomy-mid:#2d2d33;--anatomy-lo:#66666c;--anatomy-faint:#a0a0a6;--anatomy-halo-opacity:.45;--anatomy-lit-shade:#e6eef2}
body.bare.iso[data-theme="light"]{--anatomy-weight:3px}
body.bare .iso-line[data-dotted]{stroke-width:3px;stroke-dasharray:.01 11px}
body.bare .iso-line[data-flow]{stroke-dasharray:8px 24px}
body.bare .iso-line[data-dashed]{stroke-dasharray:12px 12px}
body.bare .iso-halo{filter:blur(12px)!important}
body.bare .iso .ticket .iso-edge{stroke-width:3px}
body.bare [data-part="needle"]{stroke-width:3.2px!important}
.iso[data-theme="light"] .bench>.iso-top,.iso[data-theme="light"] .bench>.iso-fill{fill:#c4c4bf}
.iso[data-theme="light"] .bench>.iso-top{fill:#cfcfca}
.iso-stage{outline:none;touch-action:pan-y;cursor:crosshair}
.iso-stage:focus-visible{outline:1px solid var(--anatomy-muted);outline-offset:6px}
.iso-wire[data-on] .iso-wire-end{stroke:var(--anatomy-hi)}
.iso-wire[data-on]>.iso-line{stroke:var(--anatomy-hi)}
.iso-wire[data-on]>.iso-line[data-flow]{stroke-dasharray:2 5}
body.bare{background:#fff}
body.bare .iso-page{width:auto;margin:0}
body.bare .iso-figure{margin:0}
body.bare .iso-plate{padding:0;background:transparent;box-shadow:none;width:${W}px}
body.bare .iso-plate-corners,body.bare .iso-legend{display:none}
body.bare .iso-svg{width:${W}px;height:${H}px;display:block}
@media (max-width:560px){.iso-plate .iso-svg{transform:scale(1.12);transform-origin:50% 50%}.iso-plate{overflow:hidden}}
`;

function page(theme) {
  const body = kit.plateHtml({
    fig: "Fig 1",
    title: "Contexto · Juicio · Acción",
    hint: "Clic en un pin o teclas 1–4: quitar evidencia",
    readout: s0.text,
    keys: legend.keys,
    caption: legend.caption,
    body: `<div class="iso-stage" tabindex="0" role="group" aria-label="Máquina de tres estaciones. Teclas 1 a 4 quitan o devuelven la evidencia de un pin; barra espaciadora quita la tercera; Escape restablece." data-calm="${theme}">${svg}</div><span class="sr" aria-live="polite" style="position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)"></span>`,
  });
  let html = kit.pageHtml({ title: "Contexto Juicio Acción", theme, body, script: kitScript() + live, width: 960 });
  html = html.replace("<html lang=\"en\">", "<html lang=\"es\">").replace("</style>", EXTRA_CSS + "</style>");
  return html;
}

if (only !== "dark") {
  writeFileSync(join(HERE, "machine.html"), page("light"));
  console.log("wrote machine.html");
}
if (only !== "light") {
  writeFileSync(join(HERE, "machine-dark.html"), page("dark"));
  console.log("wrote machine-dark.html");
}
console.log(`solids drawn at rest: ${parts.counter.solids}`);
