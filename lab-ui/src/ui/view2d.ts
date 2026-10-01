import { poseFromMessage, type Pose2D } from "../ros/pose";
import type { RosbridgeClient, RosStatus } from "../ros/rosbridge";
import { button, h } from "./dom";

const POSE_TYPE = "nav_msgs/msg/Odometry";
const TWIST_TYPE = "geometry_msgs/msg/Twist";
const PIXELS_PER_METER = 60;
const TRAIL_POINTS = 600;
const LINEAR_SPEED = 0.3; // m/s
const ANGULAR_SPEED = 1.0; // rad/s

const STATUS_TEXT: Record<RosStatus, string> = {
  connecting: "connexion…",
  open: "connecté",
  reconnecting: "reconnexion…",
  closed: "déconnecté",
};

/** Vue de dessus du robot (pose reçue par rosbridge) et téléopération. */
export class View2D {
  readonly el = h("aside", { class: "panel view2d", attrs: { "aria-label": "Vue 2D" } });
  private readonly canvas = h("canvas", { class: "view-canvas", attrs: { tabindex: "0", "aria-label": "Vue de dessus du robot" } });
  private readonly status = h("span", { class: "pill", text: STATUS_TEXT.closed });
  private readonly readout = h("div", { class: "readout muted small" });
  private readonly hint = h("p", { class: "view-hint muted small" });
  private readonly topics = h("ul", { class: "topic-list" });
  private readonly poseInput = h("input", { attrs: { value: "/odom", "aria-label": "Topic de pose", spellcheck: "false" } });
  private readonly cmdInput = h("input", { attrs: { value: "/cmd_vel", "aria-label": "Topic de commande", spellcheck: "false" } });
  private pose: Pose2D | null = null;
  private trail: Pose2D[] = [];
  private center = { x: 0, y: 0 };
  private messages = 0;
  private unsubscribe: (() => void) | null = null;
  private drive: { linear: number; angular: number } | null = null;
  private driveTimer: number | null = null;
  private frame: number | null = null;

  constructor(private readonly ros: RosbridgeClient) {
    const pad = h(
      "div",
      { class: "teleop", attrs: { role: "group", "aria-label": "Téléopération" } },
      h("span"),
      this.driveButton("↑", "Avancer", 1, 0),
      h("span"),
      this.driveButton("←", "Tourner à gauche", 0, 1),
      this.driveButton("■", "Stop", 0, 0),
      this.driveButton("→", "Tourner à droite", 0, -1),
      h("span"),
      this.driveButton("↓", "Reculer", -1, 0),
      h("span"),
    );
    this.el.append(
      h("div", { class: "panel-header" }, h("h2", { text: "Vue 2D" }), this.status),
      h("div", { class: "view-stage" }, this.canvas, this.hint),
      this.readout,
      h(
        "div",
        { class: "view-settings" },
        h("label", {}, "Pose ", this.poseInput),
        h("label", {}, "Commande ", this.cmdInput),
      ),
      pad,
      h(
        "div",
        { class: "panel-actions" },
        button("Topics actifs", () => void this.listTopics()),
        button("Effacer la trace", () => {
          this.trail = [];
          this.draw();
        }),
      ),
      this.topics,
    );
    this.poseInput.addEventListener("change", () => this.subscribe());
    this.canvas.addEventListener("keydown", (ev) => this.key(ev, true));
    this.canvas.addEventListener("keyup", (ev) => this.key(ev, false));
    this.canvas.addEventListener("blur", () => this.setDrive(null));
    new ResizeObserver(() => this.draw()).observe(this.canvas);
    this.setHint();
  }

  start(): void {
    this.subscribe();
  }

  setStatus(status: RosStatus): void {
    this.status.textContent = `rosbridge ${STATUS_TEXT[status]}`;
    this.status.dataset.status = status;
  }

  private subscribe(): void {
    this.unsubscribe?.();
    this.pose = null;
    this.trail = [];
    this.messages = 0;
    this.setHint();
    const topic = this.poseInput.value.trim() || "/odom";
    this.unsubscribe = this.ros.subscribe(topic, POSE_TYPE, (msg) => this.onPose(msg), 50);
    this.draw();
  }

  private setHint(): void {
    this.hint.hidden = this.messages > 0;
    this.hint.textContent = `En attente de ${this.poseInput.value.trim() || "/odom"}… Lancez par exemple « academy-diffbot » dans un terminal.`;
  }

  private onPose(msg: unknown): void {
    const pose = poseFromMessage(msg);
    if (!pose) return;
    this.pose = pose;
    this.messages += 1;
    const last = this.trail[this.trail.length - 1];
    if (!last || Math.hypot(last.x - pose.x, last.y - pose.y) > 0.01) {
      this.trail.push(pose);
      if (this.trail.length > TRAIL_POINTS) this.trail.shift();
    }
    if (this.messages === 1) this.setHint();
    this.canvas.dataset.x = pose.x.toFixed(3);
    this.canvas.dataset.y = pose.y.toFixed(3);
    this.canvas.dataset.theta = pose.theta.toFixed(3);
    this.readout.textContent = `x = ${pose.x.toFixed(2)} m · y = ${pose.y.toFixed(2)} m · θ = ${((pose.theta * 180) / Math.PI).toFixed(0)}°`;
    this.frame ??= requestAnimationFrame(() => {
      this.frame = null;
      this.draw();
    });
  }

  private driveButton(label: string, title: string, linear: number, angular: number): HTMLButtonElement {
    const b = h("button", { type: "button", text: label, title, attrs: { "aria-label": title } });
    if (linear === 0 && angular === 0) {
      b.addEventListener("click", () => this.setDrive(null, true));
      return b;
    }
    b.addEventListener("pointerdown", (ev) => {
      b.setPointerCapture(ev.pointerId);
      this.setDrive({ linear, angular });
    });
    for (const end of ["pointerup", "pointercancel", "lostpointercapture"] as const) {
      b.addEventListener(end, () => this.setDrive(null, true));
    }
    return b;
  }

  private key(ev: KeyboardEvent, down: boolean): void {
    const dirs: Record<string, [number, number]> = {
      ArrowUp: [1, 0],
      ArrowDown: [-1, 0],
      ArrowLeft: [0, 1],
      ArrowRight: [0, -1],
    };
    const dir = dirs[ev.key];
    if (!dir) return;
    ev.preventDefault();
    this.setDrive(down ? { linear: dir[0], angular: dir[1] } : null, !down);
  }

  /** Publie la commande à 10 Hz tant qu'un bouton est maintenu (le simulateur s'arrête seul sans commande). */
  private setDrive(drive: { linear: number; angular: number } | null, sendStop = false): void {
    this.drive = drive;
    if (this.driveTimer !== null) clearInterval(this.driveTimer);
    this.driveTimer = null;
    if (drive) {
      this.publishDrive();
      this.driveTimer = window.setInterval(() => this.publishDrive(), 100);
    } else if (sendStop) {
      this.publishTwist(0, 0);
    }
  }

  private publishDrive(): void {
    if (this.drive) this.publishTwist(this.drive.linear * LINEAR_SPEED, this.drive.angular * ANGULAR_SPEED);
  }

  private publishTwist(linear: number, angular: number): void {
    this.ros.publish(this.cmdInput.value.trim() || "/cmd_vel", TWIST_TYPE, {
      linear: { x: linear, y: 0, z: 0 },
      angular: { x: 0, y: 0, z: angular },
    });
  }

  private async listTopics(): Promise<void> {
    this.topics.replaceChildren(h("li", { class: "muted", text: "Chargement…" }));
    try {
      const { topics, types } = await this.ros.callService<{ topics: string[]; types: string[] }>("/rosapi/topics");
      const items = topics
        .map((t, i) => ({ t, type: types[i] ?? "" }))
        .sort((a, b) => a.t.localeCompare(b.t))
        .map(({ t, type }) => h("li", {}, h("code", { text: t }), h("span", { class: "muted small", text: ` ${type}` })));
      this.topics.replaceChildren(...(items.length ? items : [h("li", { class: "muted", text: "Aucun topic" })]));
    } catch {
      this.topics.replaceChildren(h("li", { class: "muted", text: "rosbridge ne répond pas encore, réessayez." }));
    }
  }

  private draw(): void {
    const canvas = this.canvas;
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    if (!width || !height) return;
    if (canvas.width !== Math.round(width * dpr) || canvas.height !== Math.round(height * dpr)) {
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
    }
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const scale = PIXELS_PER_METER;
    // recentre la vue quand le robot approche du bord
    if (this.pose) {
      const marginX = width / scale / 2 - 0.5;
      const marginY = height / scale / 2 - 0.5;
      if (Math.abs(this.pose.x - this.center.x) > marginX || Math.abs(this.pose.y - this.center.y) > marginY) {
        this.center = { x: this.pose.x, y: this.pose.y };
      }
    }
    const toScreen = (x: number, y: number): [number, number] => [
      width / 2 + (x - this.center.x) * scale,
      height / 2 - (y - this.center.y) * scale,
    ];
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = "#0f141a";
    ctx.fillRect(0, 0, width, height);

    // grille de 1 m
    ctx.strokeStyle = "#1e2a36";
    ctx.lineWidth = 1;
    const x0 = Math.floor(this.center.x - width / scale / 2);
    const x1 = Math.ceil(this.center.x + width / scale / 2);
    const y0 = Math.floor(this.center.y - height / scale / 2);
    const y1 = Math.ceil(this.center.y + height / scale / 2);
    ctx.beginPath();
    for (let x = x0; x <= x1; x++) {
      const [sx] = toScreen(x, 0);
      ctx.moveTo(Math.round(sx) + 0.5, 0);
      ctx.lineTo(Math.round(sx) + 0.5, height);
    }
    for (let y = y0; y <= y1; y++) {
      const [, sy] = toScreen(0, y);
      ctx.moveTo(0, Math.round(sy) + 0.5);
      ctx.lineTo(width, Math.round(sy) + 0.5);
    }
    ctx.stroke();

    // axes du repère odom (x rouge, y vert)
    const [ox, oy] = toScreen(0, 0);
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#d9534f";
    ctx.beginPath();
    ctx.moveTo(ox, oy);
    ctx.lineTo(ox + scale * 0.5, oy);
    ctx.stroke();
    ctx.strokeStyle = "#5cb85c";
    ctx.beginPath();
    ctx.moveTo(ox, oy);
    ctx.lineTo(ox, oy - scale * 0.5);
    ctx.stroke();

    // trace
    if (this.trail.length > 1) {
      ctx.strokeStyle = "#3d7ea6";
      ctx.lineWidth = 2;
      ctx.beginPath();
      this.trail.forEach((p, i) => {
        const [sx, sy] = toScreen(p.x, p.y);
        if (i === 0) ctx.moveTo(sx, sy);
        else ctx.lineTo(sx, sy);
      });
      ctx.stroke();
    }

    // robot : disque + flèche de cap
    if (this.pose) {
      const [rx, ry] = toScreen(this.pose.x, this.pose.y);
      const r = 0.18 * scale;
      ctx.fillStyle = "#7fd4c1";
      ctx.beginPath();
      ctx.arc(rx, ry, r, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#0f141a";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(rx, ry);
      ctx.lineTo(rx + Math.cos(this.pose.theta) * r, ry - Math.sin(this.pose.theta) * r);
      ctx.stroke();
    }

    // échelle
    ctx.fillStyle = "#8a99a8";
    ctx.font = "12px system-ui, sans-serif";
    ctx.fillText("1 m", 12, height - 22);
    ctx.fillRect(12, height - 14, scale, 2);
  }

  stop(): void {
    this.setDrive(null);
    this.unsubscribe?.();
    this.unsubscribe = null;
  }
}
