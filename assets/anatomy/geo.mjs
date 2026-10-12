// Shared world constants for the Contexto / Juicio / Acción machine.
// World: x along the rail, y toward the viewer, z up. Units are about 1 px.
export const W = 900;
export const H = 380;
export const AZ = 63;

export const PLATE = { x: -358, y: -100, w: 716, d: 200, r: 10 };
export const PLATE_H = 12;
export const FOOT_H = 5;

export const RAIL_Y = [-10, 10];
export const RAIL_X = [-350, 198];
export const CAR_Z = [3, 8];
export const CAR_HW = 30; // carriage half length in x
export const CAR_HD = 20; // half depth in y

export const HOME = -312;
export const S1 = -236;
export const S2 = -52;
export const S3 = 134;

export const TICKET = { hw: 27, hd: 16, z: 8, h: 1.4 };
export const TICKET_TOP = 9.4;
export const HOLE_DX = [-15, -5, 5, 15];
export const HOLE_Y = 9.5;
export const STAMP_AT = [12, -3];
export const READ_AT = [-13, -4];

// Station 1: card catalogue
export const CAB = { x: -282, y: -96, w: 66, d: 48, h: 44 };
export const ARM_Z = [50, 56];
export const ARM1 = { x: -257, w: 16, y0: -96, y1: 2 };
export const DRAWER = { x: -248, w: 30, z: 15, h: 14, travel: 26 };
export const PAD = { x: S1 + READ_AT[0], y: READ_AT[1], r: 5, h: 3, up: 30, down: TICKET_TOP };

// Station 2: go/no-go gauge
export const GAUGE_COL = { x: -86, y: -96, w: 68, d: 44, h: 46 };
export const GARM = { x: -76, w: 48, y0: -96, y1: 18, z0: 46, z1: 56 };
export const PIN_Z_ARM = 46;
export const PIN_TOP = 56;
export const PIN_REACH = 12; // travel until the tip meets a ticket with no hole
export const PIN_DEPTH = 5; // further travel into a punched hole
export const DIAL = { x: -52, y: -40, r: 16, z: 56, h: 8 };

// Station 3: stamp press with two keys
export const PCOL = { x: 100, y: -96, w: 88, d: 46, h: 46 };
export const PARM = { x: 126, w: 40, y0: -96, y1: 14, z0: 46, z1: 56 };
export const RAM = { x: S3 + STAMP_AT[0], y: STAMP_AT[1], r: 7.4, dieH: 4, rest: 24, down: 9.6, rodR: 2.4 };
export const HOUSE = { r: 9, z0: 56, z1: 65 };
export const KEYS = [
  { x: 114, y: -72, name: "aplicación" },
  { x: 174, y: -72, name: "humana" },
];
export const BOX = { x: 128, w: 36, y0: -50, y1: -43, z0: 16, z1: 30 };
export const SHUTTER = { x: 130, w: 32, z: 18.6, h: 3, y0: -12, d: 18, travel: 22 };
export const PADDLE = { x: S3 - 22, w: 44, z: 8.4, h: 7.6, d: 4, y0: -28, y1: 36 };
export const BIN = { x: 101, y: 28, w: 66, d: 54, wall: 3 };
export const TRAY = { x: 188, y: -92, w: 70, d: 32, z: 14, h: 2.6 };
export const SLIP = { w: 24, d: 20, z: TRAY.z + TRAY.h, h: 0.9, y: -76, start: 188 - 24, stroke: 30 };
