// Geometry builders for the machine. makeParts(k, P) returns static assemblies (built once, at build time)
// and dynamic builders (called again by the page each frame for the few parts whose shape changes).
// Needs the constants from geo.mjs and reachShare from model.mjs.

export function makeParts(k, P) {
  const counter = { solids: 0 };
  const S = (paths, style = {}) => {
    counter.solids++;
    return k.solidSvg(paths, style);
  };
  const L = (d, style) => k.lineSvg(d, style);
  const D = (points, style) => k.dotsSvg(points, style);
  const at = (p) => k.iso(p, P);
  const dots3 = (list, style) => D(list.map((p) => at(p)), style);
  const plan = (x0, y0, x1, y1, r = 1) => ({ x: x0, y: y0, w: x1 - x0, d: y1 - y0, r });
  const slab = (x0, y0, x1, y1, z, h, o = {}) =>
    S(k.slabOf(plan(x0, y0, x1, y1, o.r ?? 1), z, h, P, o.steps ?? 3, o.bevel ?? 0.4), {
      tone: o.tone ?? "mid",
      crease: o.crease,
      lit: o.lit,
      inner: o.inner,
      className: o.cls,
    });
  const cyl = (x, y, r, z, h, o = {}) =>
    S(k.cylinder(x, y, r, z, h, P, o.steps ?? Math.max(12, Math.round(r * 4.2)), o.bevel ?? 0), {
      tone: o.tone ?? "mid",
      crease: o.crease,
      lit: o.lit,
      inner: o.inner,
      className: o.cls,
    });
  const byDepth = (list) => [...list].sort((a, b) => k.depthOf([a[0], a[1], 0], P) - k.depthOf([b[0], b[1], 0], P));
  const rect = (pts) => k.pathOf(pts.map(at), true);
  const faceY = (y, x0, x1, z0, z1) => rect([[x0, y, z0], [x1, y, z0], [x1, y, z1], [x0, y, z1]]);
  const faceX = (x, y0, y1, z0, z1) => rect([[x, y0, z0], [x, y1, z0], [x, y1, z1], [x, y0, z1]]);
  const topRect = (x0, y0, x1, y1, z) => rect([[x0, y0, z], [x1, y0, z], [x1, y1, z], [x0, y1, z]]);
  const seg = (a, b) => k.segment(a, b, P);
  const dirOf = (phi) => {
    // world direction at screen angle phi (radians, clockwise from screen-up)
    const a = (P.azimuth * Math.PI) / 180;
    return [-Math.cos(a) * Math.cos(phi) + Math.sin(a) * Math.sin(phi), -Math.sin(a) * Math.cos(phi) - Math.cos(a) * Math.sin(phi)];
  };
  const topRing = (cx, cy, r, z, steps = 24) => k.ring(cx, cy, r, z, P, steps);

  // ───────────────────────── base, rails, feet, ruler ─────────────────────────
  function base() {
    const out = [`<path class="iso-halo" d="${k.haloOf(PLATE, -PLATE_H - FOOT_H, PLATE_H, P)}"/>`];
    const feet = [];
    for (const x of [PLATE.x + 26, PLATE.x + PLATE.w / 2, PLATE.x + PLATE.w - 26]) for (const y of [-78, 68]) feet.push([x, y]);
    for (const [x, y] of byDepth(feet)) {
      out.push(cyl(x, y, 7, -PLATE_H - FOOT_H, 1.6, { tone: "lo", steps: 24 }));
      out.push(cyl(x, y, 5.4, -PLATE_H - FOOT_H + 1.6, FOOT_H - 1.6, { tone: "mid", steps: 22 }));
    }
    out.push(S(k.slabOf(PLATE, -PLATE_H, PLATE_H, P, 8, 1.6), { tone: "mid", inner: L(k.sideSeam(PLATE, -PLATE_H / 2, P, 8), { tone: "faint" }) }));
    out.push(L(k.planOutline(k.insetPlan(PLATE, 5), 0, P), { tone: "faint" }));
    const screws = k.corners(PLATE, 10);
    out.push(L(screws.map(([x, y]) => k.ring(x, y, 2.2, 0, P, 14)).join(""), { tone: "lo" }));
    out.push(dots3(screws.map(([x, y]) => [x, y, 0]), { size: 0.5 }));
    // slots in the bench's front and end faces (closed outlines)
    const fy = PLATE.y + PLATE.d, ex = PLATE.x + PLATE.w;
    for (const x of [PLATE.x + 60, PLATE.x + 90, PLATE.x + PLATE.w - 120, PLATE.x + PLATE.w - 90]) out.push(L(faceY(fy, x - 10, x + 10, -9, -5), { tone: "faint" }));
    out.push(L(faceX(ex, PLATE.y + 40, PLATE.y + 60, -9, -5), { tone: "faint" }), L(faceX(ex, PLATE.y + 130, PLATE.y + 150, -9, -5), { tone: "faint" }));
    // front ruler strip with ticks, rooted on its back edge
    const strip = { x: PLATE.x + 20, y: 78, w: 340, d: 7, r: 1 };
    out.push(S(k.slabOf(strip, 0, 0.6, P, 3), { tone: "lo", crease: "none" }));
    const ticks = k.topTicks(strip.x + 4, strip.x + strip.w - 4, 5, 5, strip.y + 0.8, 0.6, [2, 3.6], P);
    out.push(L(ticks.minor, { tone: "lo" }), L(ticks.major, { tone: "mid" }));
    out.push(dots3([[strip.x + 2, strip.y + 3.5, 0.6], [strip.x + strip.w - 2, strip.y + 3.5, 0.6]], { size: 0.45 }));
    // label plate with three rule lines (they stand for text, so they may stop)
    const lp = { x: PLATE.x + PLATE.w - 68, y: 72, w: 54, d: 14, r: 1.5 };
    out.push(S(k.slabOf(lp, 0, 0.8, P, 4), { tone: "lo", crease: "none" }));
    out.push(L(k.planOutline(k.insetPlan(lp, 1.6), 0.8, P), { tone: "faint" }));
    out.push(L(k.lineOnTop([lp.x + 6, lp.y + 4.2], [lp.x + 40, lp.y + 4.2], 0.8, P), { tone: "lo", free: true }));
    out.push(L(k.lineOnTop([lp.x + 6, lp.y + 7], [lp.x + 30, lp.y + 7], 0.8, P), { tone: "lo", free: true }));
    out.push(L(k.lineOnTop([lp.x + 6, lp.y + 9.8], [lp.x + 36, lp.y + 9.8], 0.8, P), { tone: "lo", free: true }));
    out.push(dots3([[lp.x + 47, lp.y + 4, 0.8], [lp.x + 47, lp.y + 10, 0.8]], { size: 0.45 }));
    return out.join("");
  }

  function rails() {
    const out = [];
    for (let x = RAIL_X[0] + 14; x < RAIL_X[1]; x += 76) {
      out.push(slab(x - 3, -18, x + 3, 18, 0, 1.6, { tone: "lo", r: 0.6, steps: 2, bevel: 0 }));
    }
    for (const y of RAIL_Y) {
      out.push(slab(RAIL_X[0], y - 2.5, RAIL_X[1], y + 2.5, 0, 3, { tone: "mid", r: 1, steps: 3, bevel: 0.4 }));
      const pts = [];
      for (let x = RAIL_X[0] + 10; x < RAIL_X[1]; x += 48) pts.push([x, y, 3]);
      out.push(dots3(pts, { size: 0.4 }));
    }
    for (const x of [RAIL_X[0] + 2, RAIL_X[1] - 1]) {
      out.push(slab(x, -17, x + 5, 17, 0, 7, { tone: "mid", r: 1.2, steps: 3, bevel: 0.5 }));
      out.push(dots3([[x + 2.5, -11, 7], [x + 2.5, 11, 7]], { size: 0.45 }));
    }
    return out.join("");
  }

  // ───────────────────────── feeder of tickets at the rail's start ─────────────────────────
  function feeder() {
    const out = [];
    const x0 = HOME - 36, x1 = HOME + 8;
    out.push(slab(x0, -88, x1, -50, 0, 16, { tone: "mid", r: 2, steps: 4, bevel: 0.8, inner: L(k.sideSeam(plan(x0, -88, x1, -50, 2), 9, P, 4), { tone: "faint" }) }));
    out.push(L(k.planOutline(plan(x0 + 3, -85, x1 - 3, -53, 1.4), 16, P, 4), { tone: "faint" }));
    // a stack of request tickets standing in the feeder, front edges showing
    out.push(slab(x0 + 5, -82, x0 + 6.8, -66, 16, 9, { tone: "lo", r: 0.3, steps: 2, bevel: 0 }));
    for (let i = 0; i < 5; i++) out.push(slab(x0 + 7, -81 + i * 2.8, x1 - 7, -79.8 + i * 2.8, 16, 11 + (i % 2 ? 0 : 1), { tone: i === 4 ? "hi" : "mid", r: 0.3, steps: 2, bevel: 0 }));
    out.push(slab(x1 - 6.8, -82, x1 - 5, -66, 16, 9, { tone: "lo", r: 0.3, steps: 2, bevel: 0 }));
    out.push(L(faceY(-50, x0 + 8, x1 - 8, 5, 8.5), { tone: "hi" }));
    out.push(dots3([[x0 + 3, -85, 16], [x1 - 3, -85, 16], [x0 + 3, -53, 16], [x1 - 3, -53, 16]], { size: 0.45 }));
    out.push(L(k.sideRing([x1, -69, 8], 3.2, "x", P, 14), { tone: "lo" }));
    return out.join("");
  }

  // ───────────────────────── station 1: card catalogue ─────────────────────────
  const COLS = [[CAB.x + 2, CAB.x + 32], [CAB.x + 34, CAB.x + 64]];
  const ROWS = [5, 18.5, 32];
  const ROW_H = 11;
  function cabinet() {
    const out = [];
    const body = plan(CAB.x, CAB.y, CAB.x + CAB.w, CAB.y + CAB.d, 2);
    out.push(slab(CAB.x - 2, CAB.y - 2, CAB.x + CAB.w + 2, CAB.y + CAB.d + 2, 0, 3, { tone: "lo", r: 2.5, steps: 4, bevel: 0.6 }));
    out.push(S(k.slabOf(body, 3, CAB.h - 3, P, 4, 0.8), { tone: "mid", inner: L(k.sideSeam(body, 3 + (CAB.h - 3) / 2, P, 4), { tone: "faint" }) }));
    out.push(L(k.planOutline(k.insetPlan(body, 3), CAB.h, P, 4), { tone: "faint" }));
    out.push(dots3([[CAB.x + 5, CAB.y + 5, CAB.h], [CAB.x + CAB.w - 5, CAB.y + 5, CAB.h], [CAB.x + CAB.w - 5, CAB.y + CAB.d - 5, CAB.h], [CAB.x + 5, CAB.y + CAB.d - 5, CAB.h]], { size: 0.45 }));
    // right flank: a panel and three closed vent slots
    const xr = CAB.x + CAB.w;
    out.push(L(faceX(xr, CAB.y + 6, CAB.y + CAB.d - 6, 8, CAB.h - 5), { tone: "faint" }));
    for (const z of [14, 22, 30]) out.push(L(faceX(xr, CAB.y + 14, CAB.y + CAB.d - 14, z, z + 3), { tone: "lo" }));
    out.push(dots3([[xr, CAB.y + 9, 11], [xr, CAB.y + CAB.d - 9, 11], [xr, CAB.y + 9, CAB.h - 8], [xr, CAB.y + CAB.d - 9, CAB.h - 8]], { size: 0.45 }));
    // drawer fronts, all but the active one
    const fy = CAB.y + CAB.d;
    COLS.forEach(([x0, x1], c) => {
      ROWS.forEach((z, r) => {
        if (r === 1 && c === 0) return;
        out.push(slab(x0, fy - 1.2, x1, fy, z, ROW_H, { tone: "mid", r: 0.6, steps: 2, bevel: 0.3 }));
        const xc = (x0 + x1) / 2;
        out.push(slab(xc - 4, fy - 2.6, xc + 4, fy - 1.2, z + 2.2, 1.5, { tone: "lo", r: 0.5, steps: 2, bevel: 0 }));
        out.push(L(faceY(fy - 1.2, x0 + 4, x1 - 4, z + 5.2, z + 9), { tone: "faint" }));
        out.push(dots3([[x0 + 2.4, fy - 1.2, z + 2.6], [x1 - 2.4, fy - 1.2, z + 2.6]], { size: 0.4 }));
      });
    });
    return out.join("");
  }

  // The active drawer slides out along +y. Only the part in front of the cabinet face is drawn, so
  // nothing hides inside the body.
  function drawerSvg(d) {
    const fy = CAB.y + CAB.d;
    const out = [];
    const z0 = ROWS[1];
    const front = fy - 1.2 + DRAWER.travel * d;
    const x0 = DRAWER.x, x1 = DRAWER.x + DRAWER.w;
    if (d > 0.002) {
      const back = fy;
      const len = front - back;
      if (len > 0.5) {
        out.push(slab(x0 + 1.2, back, x1 - 1.2, front, z0 + 0.6, 1.2, { tone: "lo", r: 0.3, steps: 2, bevel: 0 }));
        out.push(slab(x0, back, x0 + 1.2, front, z0 + 0.6, ROW_H - 1.2, { tone: "mid", r: 0.3, steps: 2, bevel: 0.2 }));
        // cards stand across the drawer, back to front; the approved definition is the tall one
        const gap = 3.6;
        for (let j = 0, y = front - 4.4; y > back + 0.2; j++, y -= gap) {
          const key = j === 2;
          out.push(slab(x0 + 2, y - 1, x1 - 2, y, z0 + 1.8, key ? 9.6 : 7.2, { tone: key ? "hi" : "mid", r: 0.3, steps: 2, bevel: key ? 0.3 : 0, lit: false }));
        }
        out.push(slab(x1 - 1.2, back, x1, front, z0 + 0.6, ROW_H - 1.2, { tone: "mid", r: 0.3, steps: 2, bevel: 0.2 }));
      }
    }
    out.push(slab(x0, front, x1, front + 1.2, z0, ROW_H, { tone: "hi", r: 0.6, steps: 2, bevel: 0.3 }));
    const xc = (x0 + x1) / 2;
    out.push(slab(xc - 4, front + 1.2, xc + 4, front + 2.6, z0 + 2.2, 1.5, { tone: "lo", r: 0.5, steps: 2, bevel: 0 }));
    // version plate on the drawer front: the one engraved label
    out.push(slab(x0 + 4, front + 1.2, x1 - 4, front + 1.7, z0 + 5.2, 3.8, { tone: "lo", r: 0.4, steps: 2, bevel: 0, crease: "none" }));
    out.push(k.faceTextSvg(k.sideMatrix([xc, front + 1.7], z0 + 8.2, P, "left"), "v3", { size: 2.6, tone: "hi", anchor: "middle" }));
    out.push(dots3([[x0 + 2.4, front + 1.2, z0 + 2.6], [x1 - 2.4, front + 1.2, z0 + 2.6]], { size: 0.4 }));
    return out.join("");
  }

  function readingPad(d) {
    const z = PAD.up + (PAD.down - PAD.up) * d; // pad bottom
    const out = [];
    out.push(cyl(PAD.x, PAD.y, 1.8, z + PAD.h, 48 - z - PAD.h, { tone: "hi", steps: 14, crease: "none" }));
    out.push(cyl(PAD.x, PAD.y, PAD.r, z, PAD.h, { tone: "hi", steps: 24, bevel: 0.4 }));
    out.push(L(k.knurl(PAD.x, PAD.y, PAD.r, z, z + PAD.h, 20, P, 0.3), { tone: "lo" }));
    return out.join("");
  }

  function readingArm() {
    const out = [];
    const ax0 = ARM1.x, ax1 = ARM1.x + ARM1.w;
    out.push(slab(ax0 - 3, -94, ax1 + 3, -76, 44, 6, { tone: "mid", r: 1.5, steps: 3, bevel: 0.5 }));
    out.push(slab(ax0, ARM1.y0, ax1, ARM1.y1 - 4, ARM_Z[0], ARM_Z[1] - ARM_Z[0], { tone: "mid", r: 1.4, steps: 3, bevel: 0.5, inner: L(k.sideSeam(plan(ax0, ARM1.y0, ax1, ARM1.y1 - 4, 1.4), 53, P, 3), { tone: "faint" }) }));
    out.push(L(k.lineOnTop([PAD.x, ARM1.y0], [PAD.x, ARM1.y1 - 4], ARM_Z[1], P), { tone: "faint" }));
    out.push(dots3([[PAD.x - 4, -88, 56], [PAD.x + 4, -88, 56], [PAD.x - 4, -60, 56], [PAD.x + 4, -60, 56]], { size: 0.42 }));
    out.push(cyl(PAD.x, PAD.y, 6.6, 48, 8, { tone: "mid", steps: 28, bevel: 0.5 }));
    out.push(L(k.sideArc(PAD.x, PAD.y, 6.6, 52, P, 16), { tone: "faint" }));
    out.push(L(topRing(PAD.x, PAD.y, 4.2, 56, 20), { tone: "lo" }));
    return out.join("");
  }

  // ───────────────────────── station 2: go/no-go gauge ─────────────────────────
  const pinX = (i) => S2 + HOLE_DX[i];
  function gaugeColumn() {
    const out = [];
    const c = GAUGE_COL;
    const body = plan(c.x, c.y, c.x + c.w, c.y + c.d, 2);
    out.push(S(k.slabOf(body, 0, c.h, P, 4, 0.8), { tone: "mid", inner: L(k.sideSeam(body, 8, P, 4), { tone: "faint" }) }));
    const fy = c.y + c.d;
    out.push(L(faceY(fy, c.x + 6, c.x + c.w - 6, 14, c.h - 8), { tone: "faint" }));
    for (const x of [c.x + 14, c.x + 22, c.x + 30]) out.push(L(faceY(fy, x, x + 4, c.h - 16, c.h - 12), { tone: "lo" }));
    out.push(dots3([[c.x + 4, fy, 5], [c.x + c.w - 4, fy, 5], [c.x + 4, fy, c.h - 5], [c.x + c.w - 4, fy, c.h - 5]], { size: 0.45 }));
    const xr = c.x + c.w;
    out.push(L(faceX(xr, c.y + 6, fy - 6, 8, c.h - 6), { tone: "faint" }));
    out.push(dots3([[xr, c.y + 10, 12], [xr, fy - 10, 12]], { size: 0.45 }));
    return out.join("");
  }
  function gaugeLower(pins) {
    // pins hang from the bridge; each is drawn from its tip (or the ticket's surface) up to the guide
    const out = [];
    for (let i = 0; i < 4; i++) {
      const p = pins[i];
      const tip = TICKET_TOP - PIN_DEPTH + (1 - p) * (PIN_REACH + PIN_DEPTH);
      const zb = Math.max(tip, TICKET_TOP);
      out.push(cyl(pinX(i), HOLE_Y, 1.5, zb, PIN_Z_ARM - zb, { tone: "hi", steps: 12, crease: "none" }));
      out.push(cyl(pinX(i), HOLE_Y, 1.5, zb, 1.0, { tone: "hi", steps: 12, bevel: 0 }));
    }
    return out.join("");
  }
  function gaugeArm() {
    const out = [];
    const a = GARM;
    const body = plan(a.x, a.y0, a.x + a.w, a.y1, 2);
    out.push(S(k.slabOf(body, a.z0, a.z1 - a.z0, P, 4, 0.7), { tone: "mid", inner: L(k.sideSeam(body, a.z0 + 5, P, 4), { tone: "faint" }) }));
    out.push(L(k.planOutline(k.insetPlan(body, 3), a.z1, P, 4), { tone: "faint" }));
    for (let i = 0; i < 4; i++) {
      out.push(cyl(pinX(i), HOLE_Y, 3.1, a.z0 - 3.4, 3.4, { tone: "lo", steps: 14 }));
      out.push(cyl(pinX(i), HOLE_Y, 3.5, a.z1, 2.4, { tone: "mid", steps: 14, bevel: 0.3 }));
    }
    out.push(dots3([[a.x + 4, -88, a.z1], [a.x + a.w - 4, -88, a.z1], [a.x + 4, -60, a.z1], [a.x + a.w - 4, -60, a.z1], [a.x + 4, 14, a.z1], [a.x + a.w - 4, 14, a.z1]], { size: 0.45 }));
    return out.join("");
  }
  const capTop = (p) => PIN_TOP + 2.4 + 1.2 + (1 - p) * (PIN_REACH + PIN_DEPTH);
  function gaugeUpper(pins) {
    const out = [];
    for (let i = 0; i < 4; i++) {
      const z = PIN_TOP + 2.4;
      const zc = capTop(pins[i]);
      out.push(cyl(pinX(i), HOLE_Y, 1.1, z, zc - z, { tone: "hi", steps: 10, crease: "none" }));
      out.push(cyl(pinX(i), HOLE_Y, 2.4, zc, 1.6, { tone: "hi", steps: 14, bevel: 0.3 }));
    }
    return out.join("");
  }
  const DIAL_SPAN = [-60, 60]; // degrees on screen, clockwise from straight up
  const dialAngle = (value) => ((DIAL_SPAN[0] + ((DIAL_SPAN[1] - DIAL_SPAN[0]) * value) / 4) * Math.PI) / 180;
  function dial() {
    const out = [];
    const { x, y, r, z, h } = DIAL;
    const top = z + h;
    out.push(cyl(x, y, r, z, h, { tone: "hi", steps: 56, bevel: 0.7, crease: "lo" }));
    out.push(L(k.knurl(x, y, r, top - 3.2, top, 72, P, 0.3), { tone: "lo" }));
    out.push(L(k.sideArc(x, y, r, top - 3.2, P, 36), { tone: "faint" }));
    out.push(L(topRing(x, y, r - 2.2, top, 56), { tone: "lo" }));
    // scale: 0..4, a tick every 0.2, a long one every whole number
    const minor = [], major = [];
    for (let i = 0; i <= 20; i++) {
      const phi = dialAngle(i / 5);
      const [dx, dy] = dirOf(phi);
      const r1 = r - 3, r0 = r1 - (i % 5 === 0 ? 3.2 : 1.6);
      (i % 5 === 0 ? major : minor).push(k.lineOnTop([x + dx * r0, y + dy * r0], [x + dx * r1, y + dy * r1], top, P));
    }
    out.push(L(minor.join(""), { tone: "lo" }), L(major.join(""), { tone: "mid" }));
    for (let n = 0; n <= 4; n++) {
      const [dx, dy] = dirOf(dialAngle(n));
      out.push(k.faceTextSvg(k.topMatrix([x + dx * (r - 9.4), y + dy * (r - 9.4) + 1], top, P, "x"), String(n), { size: 2.6, tone: "mid", anchor: "middle" }));
    }
    out.push(S(k.slabOf(plan(x + r - 1, y - 3, x + r + 4, y + 3, 1), z + 1.4, 4.6, P, 3, 0.3), { tone: "mid" }));
    out.push(L(topRing(x, y, 1.7, top, 14), { tone: "mid" }));
    return out.join("");
  }
  const needleD = (value) => {
    const { x, y, r, z, h } = DIAL;
    const [dx, dy] = dirOf(dialAngle(Math.max(0, Math.min(4, value))));
    return k.lineOnTop([x - dx * 3.4, y - dy * 3.4], [x + dx * (r - 4.4), y + dy * (r - 4.4)], z + h + 0.2, P);
  };

  // ───────────────────────── station 3: stamp press with two keys ─────────────────────────
  function pressColumn() {
    const out = [];
    const c = PCOL;
    const body = plan(c.x, c.y, c.x + c.w, c.y + c.d, 2);
    out.push(S(k.slabOf(body, 0, c.h, P, 4, 0.8), { tone: "mid", inner: L(k.sideSeam(body, 8, P, 4), { tone: "faint" }) }));
    const fy = c.y + c.d;
    out.push(L(faceY(fy, c.x + 6, c.x + c.w - 6, 5, 14), { tone: "faint" }));
    out.push(L(faceY(fy, c.x + 6, c.x + c.w - 6, 33, c.h - 4), { tone: "faint" }));
    out.push(dots3([[c.x + 4, fy, 5], [c.x + c.w - 4, fy, 5], [c.x + 4, fy, c.h - 5], [c.x + c.w - 4, fy, c.h - 5]], { size: 0.45 }));
    const xr = c.x + c.w;
    // the slot where the receipt comes out
    out.push(L(faceX(xr, SLIP.y - 13, SLIP.y + 13, TRAY.z + TRAY.h - 0.2, TRAY.z + TRAY.h + 4), { tone: "hi" }));
    out.push(L(faceX(xr, c.y + 6, c.y + 14, 8, c.h - 6), { tone: "faint" }));
    out.push(dots3([[xr, c.y + c.d - 6, 8], [xr, c.y + c.d - 6, c.h - 8]], { size: 0.45 }));
    // key deck: bezel rings are drawn with the keys
    out.push(L(k.planOutline(k.insetPlan(body, 3), c.h, P, 4), { tone: "faint" }));
    return out.join("");
  }
  function relayBox() {
    const out = [];
    const b = BOX;
    out.push(slab(b.x, b.y0, b.x + b.w, b.y1, b.z0, b.z1 - b.z0, { tone: "mid", r: 1.2, steps: 3, bevel: 0.5 }));
    out.push(L(faceY(b.y1, b.x + 3, b.x + b.w - 3, b.z0 + 3, b.z1 - 3), { tone: "faint" }));
    const terms = [b.x + 4, b.x + 10, b.x + 30].map((x) => [x, b.y1, 26]);
    out.push(dots3(terms, { size: 1.1, tone: "hi" }));
    out.push(dots3([[b.x + 3, b.y1, b.z0 + 3], [b.x + b.w - 3, b.y1, b.z0 + 3]], { size: 0.45 }));
    return out.join("");
  }
  const keyPlace = (i) => KEYS[i];
  function keyBase(i) {
    const { x, y } = keyPlace(i);
    const out = [];
    out.push(cyl(x, y, 8, PCOL.h, 2, { tone: "lo", steps: 28, bevel: 0.3 }));
    // detents at 0 and 90 degrees
    const t = [];
    for (const a of [0, 90]) {
      const rad = (a * Math.PI) / 180;
      t.push(k.lineOnTop([x + Math.cos(rad) * 6.6, y + Math.sin(rad) * 6.6], [x + Math.cos(rad) * 8, y + Math.sin(rad) * 8], PCOL.h + 2, P));
    }
    out.push(L(t.join(""), { tone: "mid" }));
    out.push(cyl(x, y, i === 1 ? 5.6 : 4.4, PCOL.h + 2, 3.2, { tone: "mid", steps: 22, bevel: 0.3 }));
    return out.join("");
  }
  function keyBow(i, a) {
    // a: 0..1, the key turns a quarter
    const { x, y } = keyPlace(i);
    const ang = (-30 + 90 * a) * (Math.PI / 180);
    const len = i === 1 ? 7.6 : 6.4;
    const wid = i === 1 ? 2.0 : 1.5;
    const ring = [[-len, -wid], [len, -wid], [len, wid], [-len, wid]].map(([u, v]) => [x + u * Math.cos(ang) - v * Math.sin(ang), y + u * Math.sin(ang) + v * Math.cos(ang)]);
    const z = PCOL.h + 5.2;
    const out = [S(k.extrude(ring, z, 2.4, P, { bevel: 0.3 }), { tone: "hi" })];
    const c = Math.cos(ang), s = Math.sin(ang);
    out.push(L(k.lineOnTop([x - c * (len - 1.2), y - s * (len - 1.2)], [x + c * (len - 1.2), y + s * (len - 1.2)], z + 2.4, P), { tone: "lo" }));
    out.push(dots3([[x, y, z + 2.4]], { size: 0.6, tone: "hi" }));
    return out.join("");
  }
  function pressArm() {
    const out = [];
    const a = PARM;
    const body = plan(a.x, a.y0, a.x + a.w, a.y1, 2);
    out.push(S(k.slabOf(body, a.z0, a.z1 - a.z0, P, 4, 0.7), { tone: "mid", inner: L(k.sideSeam(body, a.z0 + 5, P, 4), { tone: "faint" }) }));
    out.push(L(k.planOutline(k.insetPlan(body, 3), a.z1, P, 4), { tone: "faint" }));
    // ram sleeve under the arm and the actuator housing above it
    out.push(cyl(RAM.x, RAM.y, 4.4, a.z0 - 4, 4, { tone: "lo", steps: 18 }));
    out.push(dots3([[a.x + 4, -88, a.z1], [a.x + a.w - 4, -88, a.z1], [a.x + 4, -50, a.z1], [a.x + a.w - 4, -50, a.z1], [a.x + 4, 10, a.z1], [a.x + a.w - 4, 10, a.z1]], { size: 0.45 }));
    return out.join("");
  }
  function pressHousing() {
    const out = [];
    out.push(cyl(RAM.x, RAM.y, HOUSE.r, HOUSE.z0, HOUSE.z1 - HOUSE.z0, { tone: "mid", steps: 36, bevel: 0.6, crease: "lo" }));
    out.push(L(k.knurl(RAM.x, RAM.y, HOUSE.r, HOUSE.z0 + 1.6, HOUSE.z1 - 1.6, 44, P, 0.3), { tone: "lo" }));
    out.push(L(k.sideArc(RAM.x, RAM.y, HOUSE.r, HOUSE.z0 + 1.6, P, 24), { tone: "faint" }));
    out.push(L(topRing(RAM.x, RAM.y, 5.2, HOUSE.z1, 20), { tone: "lo" }));
    return out.join("");
  }
  const STEM = 14;
  function ramTop(r) {
    const z = HOUSE.z1;
    const len = STEM * (1 - r);
    const out = [];
    if (len > 0.05) out.push(cyl(RAM.x, RAM.y, 2.2, z, len, { tone: "hi", steps: 12, crease: "none" }));
    out.push(cyl(RAM.x, RAM.y, 3.6, z + len, 2, { tone: "hi", steps: 16, bevel: 0.3 }));
    return out.join("");
  }
  function ramLower(r) {
    const zb = RAM.rest + (RAM.down - RAM.rest) * r;
    const out = [];
    out.push(cyl(RAM.x, RAM.y, RAM.rodR, zb + RAM.dieH, PARM.z0 - zb - RAM.dieH, { tone: "hi", steps: 14, crease: "none" }));
    out.push(cyl(RAM.x, RAM.y, RAM.r, zb, RAM.dieH, { tone: "hi", steps: 28, bevel: 0.4 }));
    out.push(L(k.knurl(RAM.x, RAM.y, RAM.r, zb, zb + RAM.dieH, 26, P, 0.3), { tone: "lo" }));
    return out.join("");
  }
  function shutter(open) {
    // the shutter plate blocks the die; it slides back (toward -y) when the interlock opens
    const y = SHUTTER.y0 - SHUTTER.travel * open;
    const out = [];
    out.push(slab(SHUTTER.x + 12, BOX.y1, SHUTTER.x + 20, y + 1, SHUTTER.z, SHUTTER.h - 0.6, { tone: "lo", r: 0.5, steps: 2, bevel: 0 }));
    out.push(slab(SHUTTER.x, y, SHUTTER.x + SHUTTER.w, y + SHUTTER.d, SHUTTER.z, SHUTTER.h, { tone: "hi", r: 1.2, steps: 3, bevel: 0.4 }));
    out.push(L(k.planOutline(plan(SHUTTER.x + 3, y + 3, SHUTTER.x + SHUTTER.w - 3, y + SHUTTER.d - 3, 0.8), SHUTTER.z + SHUTTER.h, P, 3), { tone: "faint" }));
    return out.join("");
  }
  function paddle(g) {
    const front = PADDLE.y0 + PADDLE.d + PUSH * g; // plate front face
    const yb = front - PADDLE.d;
    const out = [];
    out.push(slab(S3 - 20, PCOL.y + PCOL.d, S3 - 12, yb + 0.6, 9.2, 3.2, { tone: "lo", r: 0.6, steps: 2, bevel: 0 }));
    out.push(slab(PADDLE.x, yb, PADDLE.x + PADDLE.w, front, PADDLE.z, PADDLE.h, { tone: "mid", r: 0.8, steps: 3, bevel: 0.4 }));
    return out.join("");
  }
  function paddleHousing() {
    // the gate's mount on the column's front face
    const out = [];
    out.push(slab(S3 - 26, PCOL.y + PCOL.d, S3 - 6, PCOL.y + PCOL.d + 3, 6, 11, { tone: "lo", r: 0.8, steps: 3, bevel: 0.3 }));
    return out.join("");
  }
  function tray() {
    const out = [];
    const t = TRAY;
    out.push(slab(t.x + 2, t.y + 2, t.x + 8, t.y + t.d - 2, 0, t.z, { tone: "lo", r: 0.8, steps: 3, bevel: 0.3 }));
    out.push(slab(t.x + t.w - 10, t.y + 2, t.x + t.w - 4, t.y + t.d - 2, 0, t.z, { tone: "lo", r: 0.8, steps: 3, bevel: 0.3 }));
    out.push(slab(t.x, t.y, t.x + t.w, t.y + t.d, t.z, t.h, { tone: "mid", r: 1.2, steps: 3, bevel: 0.5 }));
    out.push(slab(t.x, t.y, t.x + t.w, t.y + 1.8, t.z + t.h, 2.4, { tone: "mid", r: 0.5, steps: 2, bevel: 0 }));
    out.push(L(k.planOutline(k.insetPlan(plan(t.x, t.y, t.x + t.w, t.y + t.d, 1.2), 3), t.z + t.h, P, 3), { tone: "faint" }));
    out.push(dots3([[t.x + t.w - 4, t.y + 5, t.z + t.h], [t.x + t.w - 4, t.y + t.d - 5, t.z + t.h]], { size: 0.45 }));
    return out.join("");
  }
  function tray2() {
    // the front lip and the end stop, drawn after the slip
    const t = TRAY;
    return slab(t.x, t.y + t.d - 1.8, t.x + t.w, t.y + t.d, t.z + t.h, 2.4, { tone: "mid", r: 0.5, steps: 2, bevel: 0 }) + slab(t.x + t.w - 2, t.y, t.x + t.w, t.y + t.d, t.z + t.h, 2.4, { tone: "mid", r: 0.5, steps: 2, bevel: 0 });
  }
  function slip(s) {
    // s: 0..1 how far out it has come. Clipped to the tray side of the column's face.
    const x0 = SLIP.start + SLIP.stroke * s;
    const out = [];
    const z = SLIP.z;
    out.push(slab(x0, SLIP.y - SLIP.d / 2, x0 + SLIP.w, SLIP.y + SLIP.d / 2, z, SLIP.h, { tone: "hi", r: 0.8, steps: 3, bevel: 0 }));
    out.push(L(k.lineOnTop([x0 + 4, SLIP.y - 5], [x0 + SLIP.w - 5, SLIP.y - 5], z + SLIP.h, P), { tone: "lo", free: true }));
    out.push(L(k.lineOnTop([x0 + 4, SLIP.y - 1.5], [x0 + SLIP.w - 9, SLIP.y - 1.5], z + SLIP.h, P), { tone: "lo", free: true }));
    out.push(L(k.lineOnTop([x0 + 4, SLIP.y + 2], [x0 + SLIP.w - 7, SLIP.y + 2], z + SLIP.h, P), { tone: "lo", free: true }));
    out.push(L(topRing(x0 + SLIP.w - 6, SLIP.y + 5.5, 2.2, z + SLIP.h, 12), { tone: "hi" }));
    return out.join("");
  }
  const slipClip = () => {
    const fx = PCOL.x + PCOL.w;
    const a = at([fx, -300, TRAY.z + TRAY.h]);
    const b = at([fx, 300, TRAY.z + TRAY.h]);
    const far = at([fx + 400, 0, TRAY.z + TRAY.h]);
    const o = at([fx, 0, TRAY.z + TRAY.h]);
    const dx = far[0] - o[0], dy = far[1] - o[1];
    return `<clipPath id="slipclip"><path d="${k.pathOf([a, b, [b[0] + dx, b[1] + dy], [a[0] + dx, a[1] + dy]], true)}"/></clipPath>`;
  };

  // ───────────────────────── bin for rejected requests ─────────────────────────
  function binBack() {
    const out = [];
    const b = BIN;
    out.push(slab(b.x, b.y, b.x + b.w, b.y + b.d, 0, 1.5, { tone: "mid", r: 1.5, steps: 3, bevel: 0.3, cls: "rej-liner" }));
    out.push(L(k.planOutline(plan(b.x + 5, b.y + 5, b.x + b.w - 5, b.y + b.d - 5, 1), 1.5, P, 3), { tone: "faint", className: "rej-line" }));
    out.push(slab(b.x, b.y, b.x + b.wall, b.y + b.d, 1.5, 10.5, { tone: "mid", r: 0.6, steps: 2, bevel: 0.3, cls: "rej-wall" }));
    out.push(slab(b.x + b.wall, b.y, b.x + b.w - b.wall, b.y + b.wall, 1.5, 2.5, { tone: "mid", r: 0.6, steps: 2, bevel: 0.3, cls: "rej-wall" }));
    return out.join("");
  }
  function binFront() {
    const out = [];
    const b = BIN;
    out.push(slab(b.x + b.w - b.wall, b.y, b.x + b.w, b.y + b.d, 1.5, 10.5, { tone: "mid", r: 0.6, steps: 2, bevel: 0.3, cls: "rej-wall" }));
    out.push(slab(b.x + b.wall, b.y + b.d - b.wall, b.x + b.w - b.wall, b.y + b.d, 1.5, 10.5, { tone: "mid", r: 0.6, steps: 2, bevel: 0.3, cls: "rej-wall" }));
    out.push(dots3([[b.x + b.w - b.wall / 2, b.y + 8, 12], [b.x + b.w - b.wall / 2, b.y + b.d - 8, 12]], { size: 0.42 }));
    out.push(dots3([[b.x + 8, b.y + b.d, 11], [b.x + b.w - 8, b.y + b.d, 11]], { size: 0.42 }));
    out.push(L(faceY(b.y + b.d, b.x + 12, b.x + b.w - 12, 4, 8), { tone: "lo", className: "rej-line" }));
    return out.join("");
  }

  // ───────────────────────── carriage and ticket ─────────────────────────
  function carriage() {
    const out = [];
    const hw = CAR_HW, hd = CAR_HD;
    out.push(`<path class="iso-halo" d="${k.haloOf(plan(-hw + 3, -hd + 3, hw - 3, hd - 3, 3), CAR_Z[0], 0.1, P)}" style="filter:blur(3px)"/>`);
    // bearing blocks wrap the rails
    for (const y of RAIL_Y) out.push(slab(-hw + 2, y - 5, hw - 2, y + 5, 1.2, 1.9, { tone: "lo", r: 1, steps: 3, bevel: 0 }));
    const body = plan(-hw, -hd, hw, hd, 3);
    out.push(S(k.slabOf(body, CAR_Z[0], CAR_Z[1] - CAR_Z[0], P, 5, 0.6), { tone: "mid", inner: L(k.sideSeam(body, 5.4, P, 5), { tone: "faint" }) }));
    out.push(L(k.planOutline(k.insetPlan(body, 2.4), CAR_Z[1], P, 4), { tone: "faint" }));
    // screws at the four corners, with rings
    const sc = [[-hw + 5, -hd + 5], [hw - 5, -hd + 5], [-hw + 5, hd - 5], [hw - 5, hd - 5]];
    out.push(L(sc.map(([x, y]) => k.ring(x, y, 1.9, CAR_Z[1], P, 12)).join(""), { tone: "lo" }));
    out.push(dots3(sc.map(([x, y]) => [x, y, CAR_Z[1]]), { size: 0.45 }));
    // rear stops hold the ticket's back edge
    for (const x of [-hw + 9, hw - 14]) out.push(slab(x, -hd + 2.4, x + 5, -hd + 5.4, CAR_Z[1], 2.2, { tone: "mid", r: 0.5, steps: 2, bevel: 0.2 }));
    // pull handle on the right end
    out.push(slab(hw - 0.5, -2, hw + 4, 2, 3.4, 3, { tone: "mid", r: 0.8, steps: 2, bevel: 0 }));
    out.push(cyl(hw + 6, 0, 2.8, 3, 5, { tone: "mid", steps: 16, bevel: 0.2 }));
    out.push(L(k.knurl(hw + 6, 0, 2.8, 3, 8, 14, P, 0.3), { tone: "lo" }));
    return out.join("");
  }

  function ticket(cls = "") {
    const T = TICKET;
    const out = [];
    const p = plan(-T.hw, -T.hd, T.hw, T.hd, 1.8);
    out.push(S(k.slabOf(p, T.z, T.h, P, 4, 0.3), { tone: "hi", lit: true }));
    const zt = T.z + T.h;
    out.push(L(k.planOutline(k.insetPlan(p, 2), zt, P, 3), { tone: "faint" }));
    // request text, then the definition box that gets inked at station 1
    out.push(L(k.lineOnTop([-26, -13.6], [-4, -13.6], zt, P), { tone: "lo", free: true }));
    out.push(L(k.lineOnTop([-26, -10.8], [-10, -10.8], zt, P), { tone: "lo", free: true }));
    out.push(L(k.lineOnTop([-26, -8], [-6, -8], zt, P), { tone: "lo", free: true }));
    out.push(L(k.planOutline(plan(-27, -4.4, -4, 2.6, 0.8), zt, P, 3), { tone: "mid" }));
    out.push(`<g data-part="ink" opacity="0">${L(k.lineOnTop([-24.4, -2.2], [-7, -2.2], zt, P), { tone: "hi", className: "ink", free: true })}${L(k.lineOnTop([-24.4, -0.4], [-11.6, -0.4], zt, P), { tone: "hi", className: "ink", free: true })}</g>`);
    // stamp target and the mark the press leaves
    out.push(L(topRing(STAMP_AT[0], STAMP_AT[1], RAM.r + 0.8, zt, 28), { tone: "faint" }));
    const sr = RAM.r - 0.4;
    out.push(`<g data-part="stamp" opacity="0">${L(topRing(STAMP_AT[0], STAMP_AT[1], sr, zt, 28), { tone: "hi" })}${L(topRing(STAMP_AT[0], STAMP_AT[1], sr - 2.6, zt, 22), { tone: "hi" })}${L(k.lineOnTop([STAMP_AT[0] - 2.4, STAMP_AT[1] + 0.2], [STAMP_AT[0] - 0.6, STAMP_AT[1] + 2], zt, P), { tone: "hi" })}${L(k.lineOnTop([STAMP_AT[0] - 0.6, STAMP_AT[1] + 2], [STAMP_AT[0] + 2.6, STAMP_AT[1] - 2.2], zt, P), { tone: "hi" })}</g>`);
    // evidence: four punched holes, or a blank where the evidence is missing
    for (let i = 0; i < 4; i++) {
      const x = HOLE_DX[i];
      out.push(`<g data-part="hole${i}"><path class="iso-shade" data-shade="0" d="${topRing(x, HOLE_Y, 2.6, zt, 18)}"/>${L(topRing(x, HOLE_Y, 2.6, zt, 18), { tone: "hi" })}</g>`);
      out.push(`<g data-part="blank${i}" style="display:none">${L(k.lineOnTop([x - 1.4, HOLE_Y], [x + 1.4, HOLE_Y], zt, P), { tone: "lo" })}</g>`);
    }
    out.push(L(k.lineOnTop([HOLE_DX[0] - 4.5, HOLE_Y - 4.4], [HOLE_DX[3] + 4.5, HOLE_Y - 4.4], zt, P), { tone: "faint" }));
    out.push(L(k.lineOnTop([HOLE_DX[0] - 4.5, HOLE_Y + 4.4], [HOLE_DX[3] + 4.5, HOLE_Y + 4.4], zt, P), { tone: "faint" }));
    return `<g class="ticket ${cls}">${out.join("")}</g>`;
  }

  // ───────────────────────── wires ─────────────────────────
  function wires() {
    const pts = (...list) => list.map(at);
    const gx = S2 + 12, bx = BOX.x + 4;
    const permit = pts([gx, GAUGE_COL.y + GAUGE_COL.d, 10], [gx, -46, 1.2], [bx, -46, 1.2], [bx, -40, 1.2], [bx, -43, 26]);
    const keyA = pts([KEYS[0].x, -63, PCOL.h + 0.6], [KEYS[0].x, -50, PCOL.h], [KEYS[0].x, -50, 36], [BOX.x + 10, -43, 26]);
    const keyB = pts([KEYS[1].x, -63, PCOL.h + 0.6], [KEYS[1].x, -50, PCOL.h], [KEYS[1].x, -50, 36], [BOX.x + 30, -43, 26]);
    const w = (name, list) => `<g data-part="${name}">${k.wireSvg(list[0], list[list.length - 1], { via: list.slice(1, -1), tone: "lo", size: 1.1 })}</g>`;
    return w("wirePermit", permit) + w("wireA", keyA) + w("wireB", keyB);
  }

  return {
    counter, S, L, D, at, slab, cyl,
    base, rails, feeder, cabinet, drawerSvg, readingPad, readingArm,
    gaugeColumn, gaugeLower, gaugeArm, gaugeUpper, dial, needleD,
    pressColumn, relayBox, keyBase, keyBow, pressArm, pressHousing, ramTop, ramLower, shutter, paddle, paddleHousing,
    tray, tray2, slip, slipClip, binBack, binFront, carriage, ticket, wires, dialAngle,
  };
}
