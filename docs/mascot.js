// The hear mascot: the boxy Claude Code critter in 3D, built entirely in code (three.js).
// On load it powers up, anime style: it charges, two beams summon its ears, they slam on,
// and it bursts into a jade aura. Motion follows the classic animation principles: springs give
// anticipation, follow-through and squash-and-stretch that keeps its volume.
import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";

const COL = {
  clay: 0xb94322,                // renders close to Claude's terracotta after tone mapping
  ocean: new THREE.Color(0x00d3fb),
  jade: new THREE.Color(0x83fd80),
  white: new THREE.Color(0xffffff),
  ink: 0x170a06,
};

// pure additive light on a transparent canvas: adds colour, never touches the canvas alpha
// (plain additive blending also raises alpha, which turns fading glows into dark specks over the page)
function lightBlend(m) {
  Object.assign(m, { blending: THREE.CustomBlending, blendEquation: THREE.AddEquation,
    blendSrc: THREE.SrcAlphaFactor, blendDst: THREE.OneFactor, blendSrcAlpha: THREE.ZeroFactor, blendDstAlpha: THREE.OneFactor });
  return m;
}

// damped spring: v moves toward t; kick() adds velocity
class Spring {
  constructor(v = 0, k = 140, d = 14) { this.v = v; this.t = v; this.vel = 0; this.k = k; this.d = d; }
  kick(i) { this.vel += i; }
  step(dt) { this.vel += (this.k * (this.t - this.v) - this.d * this.vel) * dt; this.v += this.vel * dt; return this.v; }
}

// a soft round dot texture for glowing particles
function dotTexture() {
  const c = document.createElement("canvas"); c.width = c.height = 64;
  const g = c.getContext("2d"), r = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  r.addColorStop(0, "rgba(255,255,255,1)"); r.addColorStop(0.35, "rgba(255,255,255,.55)"); r.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = r; g.fillRect(0, 0, 64, 64);
  return new THREE.CanvasTexture(c);
}

// pooled additive particles: fade by darkening their colour as they age
class Particles {
  constructor(max, size, tex) {
    this.max = max; this.n = 0;
    this.pos = new Float32Array(max * 3); this.col = new Float32Array(max * 3);
    this.vel = new Float32Array(max * 3); this.life = new Float32Array(max); this.age = new Float32Array(max);
    this.base = new Float32Array(max * 3); this.grav = new Float32Array(max); this.pull = new Float32Array(max);
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(this.pos, 3));
    g.setAttribute("color", new THREE.BufferAttribute(this.col, 3));
    this.points = new THREE.Points(g, lightBlend(new THREE.PointsMaterial({ size, map: tex, vertexColors: true, transparent: true, depthWrite: false, sizeAttenuation: true })));
    this.points.frustumCulled = false;
  }
  emit(x, y, z, vx, vy, vz, life, color, grav = 0, pull = 0) {
    const i = this.n < this.max ? this.n++ : Math.floor(Math.random() * this.max);
    this.pos.set([x, y, z], i * 3); this.vel.set([vx, vy, vz], i * 3); this.base.set([color.r * 1.8, color.g * 1.8, color.b * 1.8], i * 3);
    this.life[i] = life; this.age[i] = 0; this.grav[i] = grav; this.pull[i] = pull;
  }
  update(dt) {
    let alive = 0;
    for (let i = 0; i < this.n; i++) {
      this.age[i] += dt;
      const k = Math.max(0, 1 - this.age[i] / this.life[i]);
      if (k <= 0) { this.col[i * 3] = this.col[i * 3 + 1] = this.col[i * 3 + 2] = 0; continue; }
      alive++;
      const o = i * 3;
      if (this.pull[i]) { this.vel[o] -= this.pos[o] * this.pull[i] * dt; this.vel[o + 1] -= (this.pos[o + 1] + 0.1) * this.pull[i] * dt; }
      this.vel[o + 1] -= this.grav[i] * dt;
      this.pos[o] += this.vel[o] * dt; this.pos[o + 1] += this.vel[o + 1] * dt; this.pos[o + 2] += this.vel[o + 2] * dt;
      const f = Math.min(1, k * 1.6);
      this.col[o] = this.base[o] * f; this.col[o + 1] = this.base[o + 1] * f; this.col[o + 2] = this.base[o + 2] * f;
    }
    if (!alive) this.n = 0;
    this.points.geometry.attributes.position.needsUpdate = true;
    this.points.geometry.attributes.color.needsUpdate = true;
  }
}

export function createMascot(canvas, { still = false } = {}) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: still });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.95;

  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  pmrem.dispose();

  const CAM = new THREE.Vector3(0, 0.5, 9.4);
  const camera = new THREE.PerspectiveCamera(28, 1, 0.1, 50);
  camera.position.copy(CAM);
  camera.lookAt(0, 0.25, 0);

  const key = new THREE.DirectionalLight(0xffffff, 1.7); key.position.set(2.5, 4, 5);
  const rim = new THREE.DirectionalLight(0x00d3fb, 2.4); rim.position.set(-4, 2.5, -3);
  const rim2 = new THREE.DirectionalLight(0x83fd80, 0.8); rim2.position.set(4, -1, -3);
  const power = new THREE.PointLight(0x83fd80, 0, 9, 1.6); power.position.set(0, 0.2, 2.2);   // flares during the burst
  scene.add(key, rim, rim2, power, new THREE.HemisphereLight(0xffe2d6, 0x020817, 0.35));

  const lowPoly = window.innerWidth < 640;
  const seg = lowPoly ? 32 : 56, rseg = lowPoly ? 4 : 7;
  const sphere = new THREE.SphereGeometry(1, seg, seg);
  const clay = new THREE.MeshPhysicalMaterial({ color: COL.clay, roughness: 0.5, clearcoat: 0.3, clearcoatRoughness: 0.3, envMapIntensity: 0.45, emissive: COL.jade.clone(), emissiveIntensity: 0 });
  const ink = new THREE.MeshPhysicalMaterial({ color: COL.ink, roughness: 0.12, clearcoat: 1 });
  const eyeInk = ink.clone(); eyeInk.emissive = COL.jade.clone(); eyeInk.emissiveIntensity = 0;
  const glow = c => lightBlend(new THREE.MeshBasicMaterial({ color: c, transparent: true, opacity: 0, depthWrite: false }));

  const root = new THREE.Group();   // hop + squash
  const head = new THREE.Group();   // look, tilt, turn
  root.add(head);
  scene.add(root);

  // body: one soft block
  const body = new THREE.Mesh(new RoundedBoxGeometry(2.1, 1.55, 1.35, rseg, 0.34), clay);
  head.add(body);

  // stubby arms and legs
  const arms = [-1, 1].map(side => {
    const pivot = new THREE.Group();
    pivot.position.set(side * 1.05, -0.05, 0);
    const arm = new THREE.Mesh(new RoundedBoxGeometry(0.42, 0.36, 0.42, rseg, 0.13), clay);
    arm.position.x = side * 0.17;
    pivot.add(arm);
    head.add(pivot);
    return { pivot, side, wave: new Spring(0, 120, 7) };
  });
  const legGeo = new RoundedBoxGeometry(0.26, 0.34, 0.3, rseg, 0.1);
  [-0.62, -0.22, 0.22, 0.62].forEach(x => {
    const leg = new THREE.Mesh(legGeo, clay);
    leg.position.set(x, -0.86, 0.12);
    head.add(leg);
  });

  // ears. Inner glow takes the colour of whoever is talking; the outer shell glows white-hot while summoned.
  const beamGeo = new THREE.CylinderGeometry(0.1, 0.2, 3.4, 20, 1, true); beamGeo.translate(0, 1.7, 0);
  const coreGeo = new THREE.CylinderGeometry(0.035, 0.06, 3.4, 12, 1, true); coreGeo.translate(0, 1.7, 0);
  const ears = [-1, 1].map(side => {
    const pivot = new THREE.Group();
    pivot.position.set(side * 0.58, 0.66, -0.05);
    const shell = clay.clone(); shell.emissive = COL.white.clone(); shell.emissiveIntensity = 0;
    const outer = new THREE.Mesh(sphere, shell);
    outer.scale.set(0.27, 0.5, 0.16);
    outer.position.y = 0.42;
    const innerMat = new THREE.MeshStandardMaterial({ color: COL.ocean, emissive: COL.ocean.clone(), emissiveIntensity: 0.25, roughness: 0.35 });
    const inner = new THREE.Mesh(sphere, innerMat);
    inner.scale.set(0.16, 0.35, 0.07);
    inner.position.set(0, 0.45, 0.11);
    pivot.add(outer, inner);
    const base = -side * 0.3;
    pivot.rotation.z = base;
    head.add(pivot);
    // summoning beam rising from where the ear will attach
    const beam = new THREE.Mesh(beamGeo, glow(COL.jade)), core = new THREE.Mesh(coreGeo, glow(COL.white));
    beam.position.set(pivot.position.x, pivot.position.y, -0.05); core.position.copy(beam.position);
    beam.rotation.z = core.rotation.z = base * 0.6;
    head.add(beam, core);
    // shockwave on impact
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.34, 0.03, 8, 56), glow(COL.jade));
    ring.position.set(pivot.position.x, pivot.position.y + 0.05, 0.3);
    head.add(ring);
    return { side, pivot, shell, innerMat, base, beam, core, ring, beamOn: 0,
      rot: new Spring(base, 170, 8), perk: new Spring(1, 170, 9), color: COL.ocean.clone(), target: COL.ocean.clone(),
      baseY: pivot.position.y, drop: new Spring(0, 260, 13), spin: new Spring(0, 60, 7), landed: true, landT: -9, hot: 0 };
  });

  // face: tall dark eyes, brows, a small mouth
  const faceZ = 0.68;
  const eyeGeo = new RoundedBoxGeometry(0.2, 0.38, 0.08, rseg, 0.08);
  const glintMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
  const eyes = [-1, 1].map(side => {
    const g = new THREE.Group();
    g.position.set(side * 0.42, 0.1, faceZ);
    const eye = new THREE.Mesh(eyeGeo, eyeInk);
    const glint = new THREE.Mesh(sphere, glintMat);
    glint.scale.set(0.035, 0.05, 0.02);
    glint.position.set(0.04, 0.1, 0.045);
    g.add(eye, glint);
    head.add(g);
    return { g, side };
  });
  const brows = [-1, 1].map(side => {
    const b = new THREE.Mesh(new THREE.CapsuleGeometry(0.035, 0.2, 4, 10), ink);
    b.rotation.z = Math.PI / 2 - side * 0.1;
    b.position.set(side * 0.44, 0.42, faceZ);
    head.add(b);
    return { b, side };
  });
  const mouth = new THREE.Mesh(new THREE.CapsuleGeometry(0.022, 0.07, 4, 8), ink);
  mouth.rotation.z = Math.PI / 2;
  mouth.position.set(0, -0.2, faceZ);
  const oh = new THREE.Mesh(new THREE.TorusGeometry(0.05, 0.022, 10, 28), ink);
  oh.position.set(0, -0.22, faceZ);
  oh.visible = false;
  const grin = new THREE.Mesh(new THREE.TorusGeometry(0.1, 0.022, 10, 32, Math.PI), ink);   // confident smile after powering up
  grin.rotation.z = Math.PI;
  grin.position.set(0, -0.14, faceZ);
  grin.visible = false;
  head.add(mouth, oh, grin);

  // soft contact shadow
  const sc = document.createElement("canvas"); sc.width = sc.height = 128;
  const sg = sc.getContext("2d"), grad = sg.createRadialGradient(64, 64, 0, 64, 64, 64);
  grad.addColorStop(0, "rgba(0,8,30,.8)"); grad.addColorStop(1, "rgba(0,8,30,0)");
  sg.fillStyle = grad; sg.fillRect(0, 0, 128, 128);
  const shadow = new THREE.Mesh(new THREE.PlaneGeometry(3.2, 3.2), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(sc), transparent: true, depthWrite: false }));
  shadow.rotation.x = -Math.PI / 2;
  shadow.position.y = -1.08;
  shadow.scale.set(1, 0.42, 1);
  scene.add(shadow);

  // power-up effects: aura ring at the feet, particles, flames
  const aura = new THREE.Mesh(new THREE.TorusGeometry(1.35, 0.05, 10, 80), glow(COL.jade));
  aura.rotation.x = Math.PI / 2.25;
  aura.position.y = -1.02;
  const aura2 = new THREE.Mesh(new THREE.TorusGeometry(1.0, 0.03, 8, 64), glow(COL.white));
  aura2.rotation.x = Math.PI / 2.25;
  aura2.position.y = -1.02;
  scene.add(aura, aura2);
  const tex = dotTexture();
  const sparks = new Particles(lowPoly ? 260 : 640, 0.26, tex);
  const flames = new Particles(lowPoly ? 200 : 480, 0.5, tex);
  scene.add(sparks.points, flames.points);

  // motion state
  const s = {
    lookX: new Spring(0, 40, 9), lookY: new Spring(0, 40, 9),
    hop: new Spring(0, 70, 7), squash: new Spring(1, 180, 9),
    tilt: new Spring(0, 90, 9), nod: new Spring(0, 110, 10), turn: new Spring(0, 45, 10),
    open: new Spring(1, 320, 24), size: new Spring(1, 140, 8), brow: new Spring(0, 160, 10),
    aura: new Spring(0, 30, 9), auraScale: new Spring(1, 60, 7), bodyGlow: new Spring(0, 40, 9), eyeGlow: new Spring(0, 30, 9),
  };
  let listening = false, ohUntil = 0, sizeUntil = 0, blinkAt = 2, blinkEnd = 0, t = 0, twitch = 0, landed = 0;
  let phase = "idle", chargeUntil = 0, lookUpUntil = 0, flameUntil = 0, grinUntil = 0, shake = 0, seq = 0;
  const slow = /[?&]slowmo/.test(location.search) ? 0.25 : 1;
  const later = (ms, fn) => { const id = seq; setTimeout(() => { if (id === seq) fn(); }, ms / slow); };
  const emitFx = (name) => dispatchEvent(new Event(name));

  addEventListener("pointermove", e => {
    const r = canvas.getBoundingClientRect();
    s.lookX.t = Math.max(-1, Math.min(1, (e.clientX - (r.left + r.width / 2)) / (innerWidth / 2)));
    s.lookY.t = Math.max(-1, Math.min(1, -(e.clientY - (r.top + r.height * 0.45)) / (innerHeight / 2)));
  }, { passive: true });

  function burstSparks(x, y, n, speed, color) {
    for (let i = 0; i < n; i++) {
      const a = Math.random() * Math.PI * 2, v = speed * (0.4 + Math.random() * 0.8);
      sparks.emit(x, y, 0.4, Math.cos(a) * v, Math.sin(a) * v + 1.2, (Math.random() - 0.5) * v, 0.45 + Math.random() * 0.4, color, 5);
    }
  }

  // an ear slams down its beam and locks on
  const slam = e => { e.drop.t = 0; e.drop.vel = -14; e.spin.t = 0; };
  function onLand(e) {
    const second = landed === 1;
    s.squash.kick(second ? -5.2 : -4); s.hop.kick(0.6); e.perk.kick(6);
    blinkEnd = t + 0.1;
    e.beamOn = -1;                                   // beam fades out
    shake = Math.max(shake, second ? 0.16 : 0.1);
    const wx = e.pivot.position.x, wy = e.pivot.position.y + root.position.y;
    burstSparks(wx, wy, second ? 46 : 32, second ? 5 : 4, COL.jade);
    burstSparks(wx, wy, 14, 3, COL.white);
    emitFx(second ? "hear:impact2" : "hear:impact");
    if (++landed === 2) later(240, powerBurst);
  }

  // the big moment: aura explodes, eyes flash, everything glows
  function powerBurst() {
    phase = "burst";
    s.squash.t = 1; s.squash.kick(-3);
    s.brow.t = 0;
    later(90, () => {
      s.hop.kick(4); s.squash.kick(4.5);
      arms.forEach(a => a.wave.kick(a.side * 16));
      s.size.t = 1.25; s.size.kick(4); sizeUntil = t + 0.9;
      s.open.t = 1;
    });
    s.bodyGlow.v = 1.1; s.eyeGlow.v = 2.4; s.eyeGlow.t = 0;
    s.aura.t = 1; s.auraScale.v = 0.6; s.auraScale.t = 1.7; s.auraScale.kick(4);
    flameUntil = t + 1.2;
    grinUntil = t + 3;
    shake = 0.22;
    power.intensity = 60;
    burstSparks(0, 0.2, 90, 6.5, COL.jade);
    burstSparks(0, 0.2, 40, 5, COL.white);
    emitFx("hear:burst");
    later(1050, () => {
      phase = "idle";
      s.aura.t = 0.16; s.auraScale.t = 1;            // a soft shimmer stays
      emitFx("hear:ready");
    });
  }

  const api = {
    // anime power-up: charge, summon ears, slam them on, burst
    intro() {
      seq++;
      landed = 0; listening = false; phase = "charge";
      ears.forEach(e => {
        e.drop.v = e.drop.t = 1.5; e.drop.vel = 0;
        e.spin.v = e.spin.t = e.side * 2.6;
        e.landed = false; e.beamOn = 0; e.hot = 1;
        e.pivot.visible = false;
      });
      chargeUntil = t + 1.5;
      s.squash.t = 0.84; s.open.t = 0.32; s.brow.t = -0.22;   // crouch, narrow eyes, determined brows
      s.aura.t = 0.75; s.auraScale.v = 0.7; s.auraScale.t = 1;
      emitFx("hear:charge");
      later(800, () => {                               // summon: beams shoot up, ears form at the top
        lookUpUntil = t + 1.1;
        ears.forEach((e, i) => later(i * 120, () => { e.beamOn = 1; e.pivot.visible = true; burstSparks(e.pivot.position.x, e.baseY + 1.9, 18, 2.5, COL.white); }));
      });
      later(1500, () => { s.squash.t = 1; slam(ears[0]); });
      later(1780, () => slam(ears[1]));
    },
    // anticipation: crouch, then spring up with ears perked
    listen() {
      if (phase !== "idle") return;
      listening = true;
      s.squash.kick(-3.2);
      later(130, () => {
        s.hop.kick(2.4); s.squash.kick(3);
        ears.forEach(e => { e.rot.t = e.base * 0.3; e.perk.t = 1.16; e.perk.kick(2.2); });
        s.open.t = 0.62;
        arms.forEach(a => a.wave.kick(a.side * 6));
      });
    },
    word({ text = "", end = "", emo = "", spk = "S1" } = {}) {
      if (phase !== "idle") return;
      const e = ears[twitch++ % 2];
      e.rot.kick(e.side * -2.2);
      if (/↑/.test(text)) { s.hop.kick(1.3); s.squash.kick(1.4); }
      if (end === "↗") s.tilt.kick(4);
      if (end === "↘") s.nod.kick(3.2);
      if (emo) {
        s.size.t = 1.35; s.size.kick(5); sizeUntil = t + 1.5; ohUntil = t + 1.5; s.hop.kick(1.6);
        arms.forEach(a => a.wave.kick(a.side * 9));
      }
      const c = spk === "S2" ? COL.jade : COL.ocean;
      ears.forEach(x => x.target.copy(c));
      s.turn.t = spk === "S2" ? 0.28 : -0.1;
    },
    end() {
      listening = false;
      ears.forEach(e => { e.rot.t = e.base; e.perk.t = 1; e.target.copy(COL.ocean); });
      s.open.t = 1; s.turn.t = 0;
      later(200, () => { s.squash.kick(-2.4); later(110, () => { s.hop.kick(2.8); s.squash.kick(2.6); arms.forEach(a => a.wave.kick(a.side * 10)); }); });
    },
    boop() {
      s.squash.kick(-4);
      ears.forEach(e => e.rot.kick(e.side * 3));
      arms.forEach(a => a.wave.kick(a.side * 8));
      blinkEnd = t + 0.22;
      later(120, () => s.hop.kick(1.8));
    },
    hop() { s.squash.kick(-2); later(100, () => { s.hop.kick(1.8); s.squash.kick(2); }); },
  };

  function update(dt) {
    t += dt;
    for (const k in s) s[k].step(dt);
    ears.forEach(e => { e.rot.step(dt); e.perk.step(dt); e.drop.step(dt); e.spin.step(dt); });
    arms.forEach(a => a.wave.step(dt));
    if (t < lookUpUntil) { s.lookY.t = 0.9; s.lookX.t = 0; }

    // charging: energy streams in, the body trembles
    const charging = t < chargeUntil;
    if (charging) {
      const rate = lowPoly ? 5 : 12;
      for (let i = 0; i < rate; i++) {
        const a = Math.random() * Math.PI * 2, r = 2.3 + Math.random() * 0.8;
        const x = Math.cos(a) * r, y = Math.sin(a) * r * 0.95 + 0.1;
        sparks.emit(x, y, (Math.random() - 0.5) * 1.2, -x * 1.6, -y * 1.6, 0, 0.55, Math.random() < 0.25 ? COL.white : COL.jade, 0, 2.5);
      }
    }
    // aura flames rise during the burst
    if (t < flameUntil) {
      const rate = lowPoly ? 5 : 12;
      for (let i = 0; i < rate; i++) {
        const a = Math.random() * Math.PI * 2, r = 1.15 + Math.random() * 0.25;
        flames.emit(Math.cos(a) * r, -1.0, Math.sin(a) * r * 0.5, -Math.cos(a) * 0.25, 2.2 + Math.random() * 2.2, 0, 0.55 + Math.random() * 0.35, Math.random() < 0.3 ? COL.white : COL.jade);
      }
    }
    sparks.update(dt); flames.update(dt);

    if (t > blinkAt) { blinkEnd = t + 0.11; blinkAt = t + 2.4 + Math.random() * 3.2; }
    if (t > sizeUntil) s.size.t = 1;
    const blink = t < blinkEnd ? 0.08 : 1;

    const breathe = 1 + Math.sin(t * 1.7) * 0.012;
    const sy = Math.max(0.7, s.squash.v) * breathe;
    const sx = 1 / Math.sqrt(sy);                       // keep the volume
    root.scale.set(sx, sy, sx);
    const y = Math.max(-0.05, s.hop.v * 0.18) + Math.sin(t * 1.1) * 0.03;
    root.position.y = y;
    root.position.x = charging ? (Math.random() - 0.5) * 0.045 : 0;   // trembling with power

    head.rotation.y = s.lookX.v * 0.32 + s.turn.v;
    head.rotation.x = -s.lookY.v * 0.16 + s.nod.v * 0.05;
    head.rotation.z = s.tilt.v * 0.05 + Math.sin(t * 0.7) * 0.015;

    eyes.forEach(({ g, side }) => {
      const sz = s.size.v;
      g.scale.set(sz, sz * Math.max(0.06, s.open.v * blink), 1);
      g.position.x = side * 0.42 + s.lookX.v * 0.06;     // eyes slide toward what they look at
      g.position.y = 0.1 + s.lookY.v * 0.05;
    });
    eyeInk.emissiveIntensity = Math.max(0, s.eyeGlow.v);
    clay.emissiveIntensity = Math.max(0, s.bodyGlow.v) * 0.9;
    power.intensity *= Math.exp(-dt * 4);

    const surprised = t < ohUntil;
    const confident = !surprised && t < grinUntil;
    mouth.visible = !surprised && !confident; oh.visible = surprised; grin.visible = confident;
    if (phase === "idle") s.brow.t = surprised ? 0.09 : listening ? 0.04 : 0;
    brows.forEach(({ b, side }) => {
      b.position.y = 0.42 + s.brow.v + (s.size.v - 1) * 0.16;
      b.rotation.z = Math.PI / 2 - side * (0.1 + s.brow.v * 1.6);   // lifted: curious; lowered: determined
    });

    arms.forEach(({ pivot, side, wave }, i) => {
      pivot.rotation.z = wave.v * 0.08 + Math.sin(t * 1.9 + i * Math.PI) * 0.04;   // follow-through on the nubs
    });

    ears.forEach((e, i) => {
      const sway = Math.sin(t * 2.1 + i * 1.7) * (listening ? 0.03 : 0.05);  // secondary action
      e.pivot.rotation.z = e.rot.v + sway + e.spin.v;
      e.pivot.position.y = e.baseY + e.drop.v;
      if (!e.landed && e.drop.t === 0 && e.drop.v < 0.04) { e.landed = true; e.landT = t; onLand(e); }
      const rt = t - e.landT;
      e.ring.material.opacity = rt < 0.5 ? (1 - rt / 0.5) : 0;
      e.ring.scale.setScalar(0.4 + Math.min(rt, 0.5) * 3.4);
      e.pivot.scale.set(1, e.perk.v, 1);
      // summoned ears glow white-hot, cooling after they lock on
      e.hot = e.landed ? Math.max(0, e.hot - dt * 2.2) : 1;
      e.shell.emissiveIntensity = e.hot * 1.4;
      // beams
      const target = e.beamOn > 0 ? 1 : 0;
      const bo = e.beam.material.opacity;
      e.beam.material.opacity = bo + (target * 0.9 - bo) * Math.min(1, dt * (target ? 10 : 7));
      e.core.material.opacity = Math.min(1, e.beam.material.opacity * 1.4);
      e.beam.scale.set(1 + Math.sin(t * 40 + i) * 0.08, 1, 1);
      e.beam.visible = e.core.visible = e.beam.material.opacity > 0.01;
      e.color.lerp(e.target, Math.min(1, dt * 6));
      e.innerMat.color.copy(e.color).multiplyScalar(0.55);   // darker base keeps the hue after tone mapping
      e.innerMat.emissive.copy(e.color);
      e.innerMat.emissiveIntensity = (listening ? 0.5 : 0.3) + (rt < 0.7 ? (1 - rt / 0.7) * 1.8 : 0);
    });

    // aura ring at the feet
    const av = Math.max(0, s.aura.v);
    aura.material.opacity = av * (0.75 + Math.sin(t * 14) * 0.15);
    aura2.material.opacity = av * 0.6;
    aura.scale.setScalar(s.auraScale.v * (1 + Math.sin(t * 9) * 0.03));
    aura2.scale.setScalar(s.auraScale.v * 0.9);
    aura.rotation.z += dt * 2.4; aura2.rotation.z -= dt * 3.5;
    aura.visible = aura2.visible = av > 0.01;

    // camera shake
    shake *= Math.exp(-dt * 7);
    camera.position.set(CAM.x + (Math.random() - 0.5) * shake, CAM.y + (Math.random() - 0.5) * shake, CAM.z);

    const lift = Math.max(0, y);
    shadow.scale.set(1 - lift * 0.5, 0.42 * (1 - lift * 0.5), 1);
    shadow.material.opacity = 1 - lift * 1.2;
  }

  function resize() {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(canvas);
  resize();

  const clock = new THREE.Clock();
  if (still) {
    for (let i = 0; i < 90; i++) update(1 / 60);  // settle the springs
    renderer.render(scene, camera);
    return api;
  }

  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let visible = true, raf = 0;
  const frame = () => {
    raf = 0;
    if (!visible || document.hidden) return;
    update(Math.min(clock.getDelta(), 1 / 30) * slow);
    renderer.render(scene, camera);
    if (!reduce) raf = requestAnimationFrame(frame);
  };
  const wake = () => { if (!raf) { clock.getDelta(); raf = requestAnimationFrame(frame); } };
  new IntersectionObserver(es => { visible = es[0].isIntersecting; if (visible) wake(); }).observe(canvas);
  document.addEventListener("visibilitychange", wake);
  if (reduce) { for (let i = 0; i < 90; i++) update(1 / 60); renderer.render(scene, camera); }
  else wake();

  // in reduced-motion mode, re-render once after each reaction instead of animating
  if (reduce) for (const k of Object.keys(api)) { const f = api[k]; api[k] = (...a) => { f(...a); update(0.3); renderer.render(scene, camera); }; }
  return api;
}
