// U.L.T.R.O.N 코어 엠블럼 — PC 판 ui/Emblem.qml 을 캔버스로 옮김
//
//   육각 꺾쇠 r211 · 톱니 링 r184~196 (60개) · 눈금 링 r160~174 (72개) · 칼날 띠 r124~151 (6개)
//   강철 호 r116 · 안쪽 링 r107 + 어두운 원판 + 삼각 무늬 · 붉게 빛나는 두 눈 · 워드마크
// 좌표는 440 단위 정사각형(중심 220,220) 기준. 모든 움직임은 지수 감쇠로 목표값을 따라간다.

export type Mode = "boot" | "standby" | "listening" | "thinking" | "speaking" | "offline";

const ACCENT: Record<Mode, string> = {
  boot: "#ff2d3f", standby: "#ff2d3f", listening: "#ff7468", thinking: "#ffbe4d", speaking: "#ff2d3f", offline: "#9aa4b0",
};

function hex(c: string): [number, number, number] {
  const n = parseInt(c.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
const rgba = ([r, g, b]: number[], a: number) => `rgba(${r | 0},${g | 0},${b | 0},${Math.max(0, Math.min(1, a)).toFixed(3)})`;
const mixc = (a: number[], b: number[], k: number) => a.map((v, i) => v + (b[i] - v) * k);

export class Emblem {
  mode: Mode = "boot";
  level = 0;          // 0..1 (듣거나 말할 때의 크기)
  private ctx: CanvasRenderingContext2D;
  private raf = 0;
  private lastT = 0;
  private reduce = matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
  // 매 프레임 값
  private t = 0; private spd = 1; private energy = 0.2; private tint = 0; private amp = 0;
  private listenAmt = 0; private thinkAmt = 0; private eyeOpen = 1; private eyeGlow = 0.86;
  private aSaw = 0; private aTicks = 0; private aBand = 0; private aSteel = 0; private aCore = 0; private aOrbit = 0; private scanA = 0;
  private blink = 1; private nextBlink = 4; private blinkT = -1;
  private accent: number[] = hex(ACCENT.boot);
  intro = 0;

  constructor(private canvas: HTMLCanvasElement) {
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("canvas 2d 없음");
    this.ctx = ctx;
  }

  start(): void {
    const loop = (ms: number) => {
      const dt = this.lastT ? Math.min((ms - this.lastT) / 1000, 0.05) : 0.016;
      this.lastT = ms;
      this.step(dt);
      this.draw();
      this.raf = requestAnimationFrame(loop);
    };
    this.raf = requestAnimationFrame(loop);
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) { cancelAnimationFrame(this.raf); this.raf = 0; this.lastT = 0; }
      else if (!this.raf) this.raf = requestAnimationFrame(loop);
    });
  }

  /** 아이콘처럼 멈춘 한 장면 그리기 */
  still(): void {
    this.intro = 1; this.mode = "standby"; this.energy = 0.5; this.eyeGlow = 1; this.accent = hex(ACCENT.standby);
    this.aSaw = 3; this.aBand = 12; this.aSteel = -20; this.scanA = 300;
    this.draw();
  }

  private step(dt: number): void {
    const f = (k: number) => 1 - Math.exp(-dt * k);
    const m = this.mode;
    const speedTarget = m === "thinking" ? 4.5 : m === "listening" ? 1.6 : m === "speaking" ? 1.4 : m === "offline" ? 0.25 : 1;
    const energyTarget = m === "thinking" ? 1 : m === "listening" ? 0.85 : m === "speaking" ? 0.7 : m === "boot" ? 0.5 : m === "offline" ? 0.3 : 0.2;
    const tintTarget = m === "thinking" || m === "offline" ? 0.8 : 0;
    const eyeTarget = m === "listening" ? 1.25 : m === "thinking" ? 0.6 : m === "offline" ? 0.4 : m === "boot" ? 0.8 : 1;
    const glowTarget = m === "offline" ? 0.3 : m === "standby" ? 0.86 : 1;
    const slow = this.reduce ? 0.25 : 1;

    this.t += dt;
    this.intro = Math.min(1, this.intro + dt / 1.9);
    this.accent = mixc(this.accent, hex(ACCENT[m]), f(4));
    this.spd += (speedTarget - this.spd) * f(1.6);
    this.energy += (energyTarget - this.energy) * f(2.4);
    this.tint += (tintTarget - this.tint) * f(3);
    this.listenAmt += ((m === "listening" ? 1 : 0) - this.listenAmt) * f(3.5);
    this.thinkAmt += ((m === "thinking" ? 1 : 0) - this.thinkAmt) * f(3.5);
    const target = Math.min(1, m === "standby" ? this.level * 0.5 : this.level);
    this.amp += (target - this.amp) * f(target > this.amp ? 20 : 4.5);
    this.level *= Math.exp(-dt * 3);   // 들어온 소리 크기는 저절로 가라앉는다
    this.eyeOpen += (eyeTarget - this.eyeOpen) * f(6);
    this.eyeGlow += (Math.min(1.2, glowTarget + 0.4 * this.amp) - this.eyeGlow) * f(9);
    const s = dt * slow;
    this.aSaw += s * (3 * this.spd + 40 * this.thinkAmt);
    this.aTicks -= s * 2 * this.spd;
    this.aBand += s * (6 * this.spd + 150 * this.thinkAmt);
    this.aSteel -= s * (10 + 80 * this.thinkAmt);
    this.aCore += s * 5 * this.spd;
    this.aOrbit += s * (50 + 130 * this.thinkAmt);
    this.scanA += s * (40 + 150 * this.listenAmt + 90 * this.thinkAmt);

    // 가끔 깜빡임 (대기 · 말하는 중에만)
    this.nextBlink -= dt;
    if (this.nextBlink <= 0) {
      this.nextBlink = 3.5 + Math.random() * 5.5;
      if (m === "standby" || m === "speaking") this.blinkT = 0;
    }
    if (this.blinkT >= 0) {
      this.blinkT += dt;
      const k = this.blinkT;
      this.blink = k < 0.07 ? 1 - (k / 0.07) * 0.94 : k < 0.21 ? 0.06 + ((k - 0.07) / 0.14) * 0.94 : 1;
      if (k >= 0.21) this.blinkT = -1;
    }
  }

  private stage(a: number, b: number): number {
    const x = Math.max(0, Math.min(1, (this.intro - a) / (b - a)));
    return 1 - Math.pow(1 - x, 3);
  }

  private draw(): void {
    const c = this.canvas;
    const dpr = Math.min(window.devicePixelRatio || 1, 3);
    const w = c.clientWidth || c.width;
    const px = Math.round(w * dpr);
    if (c.width !== px || c.height !== px) { c.width = px; c.height = px; }
    const g = this.ctx;
    const u = px / 440;
    g.setTransform(u, 0, 0, u, 0, 0);
    g.clearRect(0, 0, 440, 440);
    const cx = 220, cy = 220;
    const acc = this.accent;
    const ringCol = mixc([255, 75, 85], acc, this.tint);
    const ringHot = ringCol.map((v) => Math.min(255, v * (1.1 + 0.25 * this.amp)));
    const bandCol = mixc([200, 20, 31], acc, this.tint * 0.85);
    const steel = [195, 202, 211];
    const breath = 0.5 + 0.5 * Math.sin(this.t * 1.15);
    const sway = 2 * Math.sin(this.t * 0.23) + Math.sin(this.t * 0.11 + 1.3);
    const rad = (d: number) => (d * Math.PI) / 180;
    const pt = (deg: number, r: number): [number, number] => [cx + Math.cos(rad(deg)) * r, cy + Math.sin(rad(deg)) * r];

    // 0) 그림자 + 후광
    let gr = g.createRadialGradient(cx, cy, 0, cx, cy, 220);
    gr.addColorStop(0, "rgba(18,0,3,0.45)");
    gr.addColorStop(0.8, "rgba(18,0,3,0.22)");
    gr.addColorStop(1, "rgba(18,0,3,0)");
    g.globalAlpha = this.stage(0, 0.5);
    g.fillStyle = gr;
    g.beginPath(); g.arc(cx, cy, 220, 0, Math.PI * 2); g.fill();
    g.globalAlpha = this.stage(0.2, 0.9) * (0.35 + 0.35 * this.energy + 0.45 * this.amp + 0.12 * breath);
    gr = g.createRadialGradient(cx, cy, 0, cx, cy, 220);
    gr.addColorStop(0, rgba(acc, 0));
    gr.addColorStop(0.62, rgba(acc, 0.1));
    gr.addColorStop(0.89, rgba(acc, 0.22));
    gr.addColorStop(1, rgba(acc, 0));
    g.fillStyle = gr;
    g.beginPath(); g.arc(cx, cy, 220, 0, Math.PI * 2); g.fill();

    // 1) 안쪽 원판 + 삼각 무늬
    g.globalAlpha = this.stage(0.05, 0.5);
    gr = g.createRadialGradient(cx, cy - 30, 0, cx, cy, 105);
    gr.addColorStop(0, "rgba(46,8,13,0.96)");
    gr.addColorStop(0.85, "rgba(18,3,5,0.96)");
    gr.addColorStop(1, rgba(ringCol, 0.35));
    g.fillStyle = gr;
    g.beginPath(); g.arc(cx, cy, 105, 0, Math.PI * 2); g.fill();
    g.globalAlpha = this.stage(0.3, 0.9) * (0.18 + 0.12 * this.energy);
    g.strokeStyle = rgba(ringCol, 1);
    g.lineWidth = 1;
    for (const off of [0, 60]) {
      g.beginPath();
      for (let k = 0; k <= 3; k++) {
        const [x, y] = pt(this.aCore + off - 90 + k * 120, 96);
        k ? g.lineTo(x, y) : g.moveTo(x, y);
      }
      g.stroke();
    }

    // 2) 안쪽 밝은 링
    g.globalAlpha = this.stage(0.1, 0.6);
    g.strokeStyle = rgba(ringHot, 0.85);
    g.lineWidth = 2.2;
    g.beginPath(); g.arc(cx, cy, 107, 0, Math.PI * 2); g.stroke();

    // 3) 강철 호 (반대로 회전)
    g.globalAlpha = this.stage(0.2, 0.7) * 0.9;
    g.strokeStyle = rgba(steel, 0.75);
    g.lineWidth = 3;
    for (const base of [0, 180]) {
      g.beginPath(); g.arc(cx, cy, 116, rad(this.aSteel + base), rad(this.aSteel + base + 100)); g.stroke();
    }

    // 4) 칼날 띠
    g.globalAlpha = this.stage(0.25, 0.8) * (0.55 + 0.35 * this.energy);
    g.fillStyle = rgba(bandCol, 0.9);
    for (let k = 0; k < 6; k++) {
      const a = this.aBand + k * 60;
      const p = [pt(a, 124), pt(a + 22, 124), pt(a + 32, 151), pt(a + 10, 151)];
      g.beginPath(); g.moveTo(...p[0]); for (const q of p.slice(1)) g.lineTo(...q); g.closePath(); g.fill();
    }

    // 5) 눈금 링 (빛이 훑고 지나감, 말할 때 바깥으로 늘어남)
    g.globalAlpha = this.stage(0.3, 0.85);
    g.lineWidth = 1.6;
    for (let k = 0; k < 72; k++) {
      const a = this.aTicks + k * 5;
      let d = (((a - this.scanA) % 360) + 360) % 360;
      d = Math.min(d, 360 - d);
      const hot = Math.max(0, 1 - d / 40);
      const major = k % 6 === 0;
      const outer = 174 + (this.mode === "speaking" || this.mode === "listening" ? this.amp * 10 * (0.5 + 0.5 * Math.sin(k * 1.7 + this.t * 9)) : 0);
      g.strokeStyle = rgba(hot > 0 ? ringHot : ringCol, 0.22 + 0.25 * this.energy + 0.55 * hot + (major ? 0.15 : 0));
      g.beginPath(); g.moveTo(...pt(a, major ? 158 : 162)); g.lineTo(...pt(a, outer)); g.stroke();
    }

    // 6) 톱니 링
    g.globalAlpha = this.stage(0.35, 0.95);
    g.beginPath();
    for (let k = 0; k <= 60; k++) {
      const p1 = pt(this.aSaw + k * 6, 184);
      k ? g.lineTo(...p1) : g.moveTo(...p1);
      if (k < 60) g.lineTo(...pt(this.aSaw + k * 6 + 4.5, 196));
    }
    g.closePath();
    g.fillStyle = rgba(ringCol, 0.1 + 0.1 * this.energy);
    g.fill();
    g.strokeStyle = rgba(ringHot, 0.55 + 0.3 * this.energy);
    g.lineWidth = 1.4;
    g.stroke();

    // 7) 궤도 점
    g.globalAlpha = this.stage(0.5, 1) * (0.5 + 0.5 * this.energy);
    g.fillStyle = rgba(ringHot, 1);
    g.beginPath(); g.arc(...pt(this.aOrbit, 178), 2.6, 0, Math.PI * 2); g.fill();

    // 8) 육각 꺾쇠
    g.globalAlpha = this.stage(0.4, 1) * (0.6 + 0.3 * this.energy);
    g.strokeStyle = rgba(ringCol, 0.9);
    g.lineWidth = 2.4;
    g.lineJoin = "miter";
    for (let i = 0; i < 6; i++) {
      const v = -90 + i * 60 + sway;
      const p = pt(v, 211);
      const prev = pt(v - 60, 211);
      const next = pt(v + 60, 211);
      const k = 0.17;
      g.beginPath();
      g.moveTo(p[0] + (prev[0] - p[0]) * k, p[1] + (prev[1] - p[1]) * k);
      g.lineTo(...p);
      g.lineTo(p[0] + (next[0] - p[0]) * k, p[1] + (next[1] - p[1]) * k);
      g.stroke();
    }

    // 9) 두 눈 — 안쪽으로 치켜 내려간 빛나는 눈
    const open = Math.max(0.05, this.eyeOpen * this.blink) * this.stage(0.75, 1);
    const eyeHot = mixc([255, 244, 240], acc, 0.22);
    g.globalAlpha = 1;
    for (const side of [-1, 1]) {
      g.save();
      g.translate(cx + side * 40, 208);
      g.rotate(rad(side * -16));
      g.scale(side, 1);  // 오른쪽 눈을 기준으로 그리고 왼쪽은 뒤집는다 (안쪽 = -x)
      g.shadowColor = rgba(acc, 0.95);
      g.shadowBlur = 18 + 16 * this.eyeGlow;
      g.fillStyle = rgba(eyeHot, Math.min(1, this.eyeGlow));
      g.beginPath();
      g.moveTo(-28, 1 * open);
      g.lineTo(-12, -8 * open);
      g.lineTo(22, -6 * open);
      g.lineTo(30, 0);
      g.lineTo(12, 7 * open);
      g.lineTo(-18, 6 * open);
      g.closePath();
      g.fill();
      g.restore();
    }

    // 10) 워드마크
    g.globalAlpha = this.stage(0.6, 1) * 0.9;
    g.fillStyle = rgba(ringHot, 0.9);
    g.font = "600 17px 'Rajdhani', 'Segoe UI', sans-serif";
    g.textAlign = "center";
    g.textBaseline = "middle";
    const word = "U L T R O N";
    g.fillText(word, cx, 266);
    g.globalAlpha = 1;
  }
}
