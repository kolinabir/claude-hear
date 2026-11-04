// Sound effects for the mascot, synthesised with Web Audio (no audio files).
// Silent until set(true), which must happen after a click or key press (browser autoplay rules).
// opts.ctx: use this (e.g. an OfflineAudioContext) instead of a live one; opts.now: clock to schedule against
// (defaults to ctx.currentTime); opts.on: start enabled without the resume handshake (offline rendering).
export function createSfx(opts = {}) {
  let ctx = opts.ctx || null, master = null, meter = null, meterBuf = null, on = !!opts.on, riser = [], noiseBuf = null;
  const now = opts.now || (() => ctx.currentTime);
  if (ctx) ensure();

  function ensure() {
    if (master) return ctx;
    ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
    const comp = ctx.createDynamicsCompressor();
    master = ctx.createGain();
    master.gain.value = 0.55;
    master.connect(comp).connect(ctx.destination);
    meter = ctx.createAnalyser(); meter.fftSize = 1024; meterBuf = new Float32Array(meter.fftSize);
    comp.connect(meter);                                  // level meter: lets tests check sound really comes out
    noiseBuf = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
    const d = noiseBuf.getChannelData(0);
    for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
    return ctx;
  }

  // attack/decay envelope on a gain node
  function env(g, t0, attack, peak, decay) {
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(peak, t0 + attack);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + attack + decay);
  }

  function tone(type, f0, f1, dur, peak = 0.3, attack = 0.008, delay = 0) {
    const t0 = now() + delay, o = ctx.createOscillator(), g = ctx.createGain();
    o.type = type;
    o.frequency.setValueAtTime(f0, t0);
    o.frequency.exponentialRampToValueAtTime(f1, t0 + dur);
    env(g, t0, attack, peak, dur);
    o.connect(g).connect(master);
    o.start(t0); o.stop(t0 + attack + dur + 0.05);
  }

  function noise(dur, f0, f1, peak, type = "bandpass", q = 1.2, attack = 0.01, delay = 0) {
    const t0 = now() + delay, src = ctx.createBufferSource(), f = ctx.createBiquadFilter(), g = ctx.createGain();
    src.buffer = noiseBuf; src.loop = true;
    f.type = type; f.Q.value = q;
    f.frequency.setValueAtTime(f0, t0);
    f.frequency.exponentialRampToValueAtTime(f1, t0 + dur);
    env(g, t0, attack, peak, dur);
    src.connect(f).connect(g).connect(master);
    src.start(t0); src.stop(t0 + attack + dur + 0.05);
  }

  const ready = () => on && ctx && (ctx.state === "running" || !!opts.on);   // an offline context never reports "running"

  return {
    get on() { return on; },
    get running() { return !!ctx && ctx.state === "running"; },
    // returns a promise that settles once the browser has actually started audio (or refused)
    set(v) {
      on = v;
      if (!v) { this.stopRiser(); return Promise.resolve(false); }
      ensure();
      return ctx.resume().then(() => ctx.state === "running", () => false);
    },
    level() {                                               // current output loudness, 0 = silence
      if (!meter) return 0;
      meter.getFloatTimeDomainData(meterBuf);
      let sum = 0; for (const x of meterBuf) sum += x * x;
      return Math.sqrt(sum / meterBuf.length);
    },

    // power-up hum: rises in pitch, brightens, and pulses faster for `dur` seconds
    riser(dur) {
      if (!ready()) return;
      this.stopRiser();
      const t0 = now();
      const saw = ctx.createOscillator(), sub = ctx.createOscillator(), lp = ctx.createBiquadFilter();
      const trem = ctx.createGain(), lfo = ctx.createOscillator(), lfoAmt = ctx.createGain(), g = ctx.createGain();
      saw.type = "sawtooth"; sub.type = "sine";
      saw.frequency.setValueAtTime(70, t0); saw.frequency.exponentialRampToValueAtTime(560, t0 + dur);
      sub.frequency.setValueAtTime(35, t0); sub.frequency.exponentialRampToValueAtTime(140, t0 + dur);
      lp.type = "lowpass"; lp.Q.value = 6;
      lp.frequency.setValueAtTime(260, t0); lp.frequency.exponentialRampToValueAtTime(4200, t0 + dur);
      lfo.frequency.setValueAtTime(4, t0); lfo.frequency.exponentialRampToValueAtTime(22, t0 + dur);
      trem.gain.value = 0.65; lfoAmt.gain.value = 0.35;
      lfo.connect(lfoAmt).connect(trem.gain);
      g.gain.setValueAtTime(0.0001, t0);
      g.gain.linearRampToValueAtTime(0.09, t0 + 0.12);       // audible right away
      g.gain.linearRampToValueAtTime(0.26, t0 + dur * 0.8);
      g.gain.linearRampToValueAtTime(0.36, t0 + dur);
      saw.connect(lp); sub.connect(lp);
      lp.connect(trem).connect(g).connect(master);
      [saw, sub, lfo].forEach(o => { o.start(t0); o.stop(t0 + dur + 0.1); });
      noise(dur, 300, 5200, 0.12, "bandpass", 2, dur * 0.8);   // crackling energy, swelling
      riser = [saw, sub, lfo, g];
    },
    stopRiser() {
      if (!ctx) return;
      const t0 = now();
      riser.forEach(n => {
        if (n.gain) { n.gain.cancelScheduledValues(t0); n.gain.setTargetAtTime(0.0001, t0, 0.03); }
        else { try { n.stop(t0 + 0.12); } catch { /* already stopped */ } }
      });
      riser = [];
    },

    // the burst: deep boom, crackle and a bright shimmer
    boom() {
      if (!ready()) return;
      tone("sine", 150, 32, 1.1, 0.95, 0.005);
      tone("triangle", 90, 40, 0.6, 0.4, 0.005);
      noise(0.7, 3000, 160, 0.55, "lowpass", 0.7, 0.003);
      tone("triangle", 1300, 2600, 0.55, 0.07, 0.02, 0.04);
      tone("sine", 1950, 3900, 0.7, 0.05, 0.03, 0.08);
    },

    // an ear growing: a rising bloop, bigger on the second pulse
    bloop(big) {
      if (!ready()) return;
      tone("sine", 240, big ? 1150 : 720, big ? 0.32 : 0.22, big ? 0.6 : 0.45, 0.01);
      tone("triangle", 480, big ? 2300 : 1440, big ? 0.24 : 0.16, 0.1, 0.01);
      if (big) { tone("sine", 110, 42, 0.35, 0.7, 0.004); noise(0.25, 1800, 400, 0.28, "bandpass", 1, 0.004); }
    },

    // a meteor streaking in: rising rush of air plus a falling whistle
    meteor(dur) {
      if (!ready()) return;
      noise(dur, 300, 3800, 0.3, "bandpass", 1.3, dur * 0.85);
      tone("sine", 1600, 260, dur, 0.12, dur * 0.4);
      tone("triangle", 800, 130, dur, 0.06, dur * 0.4);
    },
    // the meteor landing: a heavy thud with grit
    thud() {
      if (!ready()) return;
      tone("sine", 120, 38, 0.7, 0.95, 0.004);
      noise(0.45, 2500, 180, 0.5, "lowpass", 0.8, 0.003);
      tone("square", 70, 35, 0.25, 0.08, 0.004);
    },
    // an explosion somewhere on screen: a shorter boom
    blast() {
      if (!ready()) return;
      tone("sine", 110 + Math.random() * 40, 34, 0.55, 0.6, 0.004);
      noise(0.5, 2600, 220, 0.4, "lowpass", 0.7, 0.003);
    },
    // glass cracking: sharp high crackle
    crack() {
      if (!ready()) return;
      noise(0.16, 5200, 2600, 0.32, "highpass", 0.7, 0.001);
      noise(0.08, 3600, 3000, 0.22, "bandpass", 4, 0.001, 0.05);
      tone("square", 2200, 900, 0.04, 0.05, 0.001);
    },
    pop() { if (ready()) { tone("sine", 520, 900, 0.09, 0.45, 0.004); tone("triangle", 1400, 1600, 0.05, 0.09, 0.003); } },
    whoosh(dur) { if (ready()) { noise(dur * 0.55, 260, 2600, 0.22, "bandpass", 1.4, dur * 0.4); noise(dur * 0.5, 2600, 300, 0.16, "bandpass", 1.4, 0.02, dur * 0.5); } },
    boing() { if (ready()) { tone("sine", 190, 640, 0.11, 0.3, 0.004); tone("sine", 640, 240, 0.28, 0.22, 0.004, 0.11); } },
    tick() { if (ready()) tone("triangle", 880, 1500, 0.06, 0.12, 0.003); },
    huh() { if (ready()) { tone("sine", 300, 300, 0.07, 0.16, 0.01); tone("sine", 320, 600, 0.2, 0.2, 0.01, 0.08); } },
  };
}
