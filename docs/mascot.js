// The hear mascot: the boxy Claude Code critter in 3D, with ears attached, built entirely in code (three.js).
// Motion follows the classic animation principles: springs give anticipation, follow-through
// and squash-and-stretch that keeps its volume; reactions are driven by the demo's real word data.
import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";

const COL = {
  clay: 0xb94322,                // renders close to Claude's terracotta after tone mapping
  ocean: new THREE.Color(0x00d3fb),
  jade: new THREE.Color(0x83fd80),
  ink: 0x170a06,
};

// damped spring: v moves toward t; kick() adds velocity
class Spring {
  constructor(v = 0, k = 140, d = 14) { this.v = v; this.t = v; this.vel = 0; this.k = k; this.d = d; }
  kick(i) { this.vel += i; }
  step(dt) { this.vel += (this.k * (this.t - this.v) - this.d * this.vel) * dt; this.v += this.vel * dt; return this.v; }
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

  const camera = new THREE.PerspectiveCamera(28, 1, 0.1, 50);
  camera.position.set(0, 0.45, 8.4);
  camera.lookAt(0, 0.2, 0);

  const key = new THREE.DirectionalLight(0xffffff, 1.7); key.position.set(2.5, 4, 5);
  const rim = new THREE.DirectionalLight(0x00d3fb, 2.4); rim.position.set(-4, 2.5, -3);
  const rim2 = new THREE.DirectionalLight(0x83fd80, 0.8); rim2.position.set(4, -1, -3);
  scene.add(key, rim, rim2, new THREE.HemisphereLight(0xffe2d6, 0x020817, 0.35));

  const lowPoly = window.innerWidth < 640;
  const seg = lowPoly ? 32 : 56, rseg = lowPoly ? 4 : 7;
  const sphere = new THREE.SphereGeometry(1, seg, seg);
  const clay = new THREE.MeshPhysicalMaterial({ color: COL.clay, roughness: 0.5, clearcoat: 0.3, clearcoatRoughness: 0.3, envMapIntensity: 0.45 });
  const ink = new THREE.MeshPhysicalMaterial({ color: COL.ink, roughness: 0.12, clearcoat: 1 });

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

  // ears: attached on top. Inner glow takes the colour of whoever is talking.
  const ears = [-1, 1].map(side => {
    const pivot = new THREE.Group();
    pivot.position.set(side * 0.58, 0.66, -0.05);
    const outer = new THREE.Mesh(sphere, clay);
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
    return { side, pivot, innerMat, base, rot: new Spring(base, 170, 8), perk: new Spring(1, 170, 9), color: COL.ocean.clone(), target: COL.ocean.clone() };
  });

  // face: tall dark eyes, brows, a small mouth
  const faceZ = 0.68;
  const eyeGeo = new RoundedBoxGeometry(0.2, 0.38, 0.08, rseg, 0.08);
  const glintMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
  const eyes = [-1, 1].map(side => {
    const g = new THREE.Group();
    g.position.set(side * 0.42, 0.1, faceZ);
    const eye = new THREE.Mesh(eyeGeo, ink);
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
  head.add(mouth, oh);

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

  // motion state
  const s = {
    lookX: new Spring(0, 40, 9), lookY: new Spring(0, 40, 9),
    hop: new Spring(0, 70, 7), squash: new Spring(1, 180, 9),
    tilt: new Spring(0, 90, 9), nod: new Spring(0, 110, 10), turn: new Spring(0, 45, 10),
    open: new Spring(1, 320, 24), size: new Spring(1, 140, 8), brow: new Spring(0, 160, 10),
  };
  let listening = false, ohUntil = 0, sizeUntil = 0, blinkAt = 2, blinkEnd = 0, t = 0, twitch = 0;
  const later = (ms, fn) => setTimeout(fn, ms);

  addEventListener("pointermove", e => {
    const r = canvas.getBoundingClientRect();
    s.lookX.t = Math.max(-1, Math.min(1, (e.clientX - (r.left + r.width / 2)) / (innerWidth / 2)));
    s.lookY.t = Math.max(-1, Math.min(1, -(e.clientY - (r.top + r.height * 0.45)) / (innerHeight / 2)));
  }, { passive: true });

  const api = {
    // anticipation: crouch, then spring up with ears perked
    listen() {
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
    ears.forEach(e => { e.rot.step(dt); e.perk.step(dt); });
    arms.forEach(a => a.wave.step(dt));

    if (t > blinkAt) { blinkEnd = t + 0.11; blinkAt = t + 2.4 + Math.random() * 3.2; }
    if (t > sizeUntil) s.size.t = 1;
    const blink = t < blinkEnd ? 0.08 : 1;

    const breathe = 1 + Math.sin(t * 1.7) * 0.012;
    const sy = Math.max(0.7, s.squash.v) * breathe;
    const sx = 1 / Math.sqrt(sy);                       // keep the volume
    root.scale.set(sx, sy, sx);
    const y = Math.max(-0.05, s.hop.v * 0.18) + Math.sin(t * 1.1) * 0.03;
    root.position.y = y;

    head.rotation.y = s.lookX.v * 0.32 + s.turn.v;
    head.rotation.x = -s.lookY.v * 0.16 + s.nod.v * 0.05;
    head.rotation.z = s.tilt.v * 0.05 + Math.sin(t * 0.7) * 0.015;

    eyes.forEach(({ g, side }) => {
      const sz = s.size.v;
      g.scale.set(sz, sz * Math.max(0.06, s.open.v * blink), 1);
      g.position.x = side * 0.42 + s.lookX.v * 0.06;     // eyes slide toward what they look at
      g.position.y = 0.1 + s.lookY.v * 0.05;
    });
    const surprised = t < ohUntil;
    mouth.visible = !surprised; oh.visible = surprised;
    s.brow.t = surprised ? 0.09 : listening ? 0.04 : 0;
    brows.forEach(({ b, side }) => {
      b.position.y = 0.42 + s.brow.v + (s.size.v - 1) * 0.16;
      b.rotation.z = Math.PI / 2 - side * (0.1 + s.brow.v * 1.6);   // inner ends lift: curious, then surprised
    });

    arms.forEach(({ pivot, side, wave }, i) => {
      pivot.rotation.z = wave.v * 0.08 + Math.sin(t * 1.9 + i * Math.PI) * 0.04;   // follow-through on the nubs
    });

    ears.forEach((e, i) => {
      const sway = Math.sin(t * 2.1 + i * 1.7) * (listening ? 0.03 : 0.05);  // secondary action
      e.pivot.rotation.z = e.rot.v + sway;
      e.pivot.scale.set(1, e.perk.v, 1);
      e.color.lerp(e.target, Math.min(1, dt * 6));
      e.innerMat.color.copy(e.color).multiplyScalar(0.55);   // darker base keeps the hue after tone mapping
      e.innerMat.emissive.copy(e.color);
      e.innerMat.emissiveIntensity = listening ? 0.5 : 0.25;
    });

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
    update(Math.min(clock.getDelta(), 1 / 30));
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
