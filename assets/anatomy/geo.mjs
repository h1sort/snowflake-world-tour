// Shared world constants for the Contexto / Juicio / Acción machine.
// World: x along the rail, y toward the viewer, z up. Units are about 1 px.
export const W = 900;
export const H = 380;
export const AZ = 71;
export const EL = 36;

export const PLATE = { x: -316, y: -100, w: 576, d: 190, r: 10 };
export const PLATE_H = 12;
export const FOOT_H = 5;

export const RAIL_Y = [-10, 10];
export const RAIL_X = [-310, 178];
export const CAR_Z = [3, 8];
export const CAR_HW = 34; // carriage half length in x
export const CAR_HD = 22; // half depth in y

export const HOME = -264;
export const S1 = -176;
export const S2 = -36;
export const S3 = 114;

export const TICKET = { hw: 31, hd: 18, z: 8, h: 1.4 };
export const TICKET_TOP = 9.4;
export const HOLE_DX = [-16.5, -5.5, 5.5, 16.5];
export const HOLE_Y = 9.5;
export const STAMP_AT = [14, -3];
export const READ_AT = [-15, -4];

// Station 1: card catalogue
export const CAB = { x: S1 - 73, y: -96, w: 66, d: 48, h: 44 };
export const ARM_Z = [50, 56];
export const DRAWER = { x: CAB.x + 2, w: 30, travel: 26 };
export const PAD = { x: S1 + READ_AT[0], y: READ_AT[1], r: 5, h: 3, up: 30, down: TICKET_TOP };
export const ARM1 = { x: PAD.x - 6, w: 12, y0: -96, y1: 2 };

// Station 2: go/no-go gauge
export const GAUGE_COL = { x: S2 - 34, y: -96, w: 68, d: 44, h: 46 };
export const GARM = { x: S2 - 24, w: 48, y0: -96, y1: 18, z0: 46, z1: 56 };
export const PIN_Z_ARM = 46;
export const PIN_TOP = 56;
export const PIN_REACH = 12; // travel until the tip meets a ticket with no hole
export const PIN_DEPTH = 7; // further travel into a punched hole
export const DIAL = { x: -52, y: -40, r: 16, z: 56, h: 8 };

// Station 3: stamp press with two keys
export const PCOL = { x: S3 - 34, y: -96, w: 88, d: 46, h: 46 };
export const PARM = { x: S3 - 6, w: 40, y0: -96, y1: 14, z0: 46, z1: 56 };
export const RAM = { x: S3 + STAMP_AT[0], y: STAMP_AT[1], r: 7.4, dieH: 4, rest: 24, down: 9.6, rodR: 2.4 };
export const HOUSE = { r: 9, z0: 56, z1: 65 };
export const KEYS = [
  { x: S3 - 18, y: -62, name: "aplicación" },
  { x: S3 + 42, y: -62, name: "humana" },
];
export const BOX = { x: S3 - 6, w: 36, y0: -50, y1: -43, z0: 16, z1: 30 };
export const SHUTTER = { x: S3 - 4, w: 32, z: 18.6, h: 3, y0: -12, d: 18, travel: 22 };
export const PADDLE = { x: S3 - 24, w: 48, z: 8.4, h: 7.6, d: 4, y0: -28 };
export const PUSH = 60; // the gate's stroke: its front face goes from -24 to 36
// The bench is an L: a strip under the rail and stations, with a lobe in front of the press for the reject bin.
export const FRONT = 40; // front edge of the strip
export const LOBE_X = S3 - 56; // the lobe runs from here to the bench's right end
export const BIN = { x: S3 - 37, y: 28, w: 74, d: 54, wall: 3 };
export const TRAY = { x: S3 + 54, y: -92, w: 70, d: 32, z: 14, h: 2.6 };
export const SLIP = { w: 24, d: 20, z: TRAY.z + TRAY.h, h: 0.9, y: -76, start: TRAY.x - 24, stroke: 30 };
