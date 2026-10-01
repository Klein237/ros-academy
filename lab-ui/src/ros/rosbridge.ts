/** Client minimal du protocole rosbridge v2 (subscribe, publish, call_service). */
import { Backoff, realTimers, type Timers } from "../backoff";
import { browserSocket, type SocketFactory, type SocketLike } from "../api/terminals";

export type RosStatus = "connecting" | "open" | "reconnecting" | "closed";

interface Subscription {
  id: string;
  topic: string;
  type: string;
  throttleMs: number;
  callbacks: Set<(msg: unknown) => void>;
}

interface PendingCall {
  resolve(values: unknown): void;
  reject(err: Error): void;
  timer: unknown;
}

export class ServiceError extends Error {}

export interface RosbridgeOptions {
  url(): Promise<string>;
  socketFactory?: SocketFactory;
  timers?: Timers;
  backoff?: Backoff;
  onStatus?(status: RosStatus): void;
}

const OPEN = 1;

export class RosbridgeClient {
  status: RosStatus = "closed";
  private socket: SocketLike | null = null;
  private closedByUs = false;
  private seq = 0;
  private subs = new Map<string, Subscription>();
  private advertised = new Map<string, string>();
  private pending = new Map<string, PendingCall>();
  private readonly timers: Timers;
  private readonly backoff: Backoff;
  private readonly factory: SocketFactory;

  constructor(private readonly opts: RosbridgeOptions) {
    this.timers = opts.timers ?? realTimers;
    this.backoff = opts.backoff ?? new Backoff(1000, 15_000);
    this.factory = opts.socketFactory ?? browserSocket;
  }

  private setStatus(status: RosStatus): void {
    this.status = status;
    this.opts.onStatus?.(status);
  }

  async connect(): Promise<void> {
    this.closedByUs = false;
    this.setStatus(this.status === "reconnecting" ? "reconnecting" : "connecting");
    let url: string;
    try {
      url = await this.opts.url();
    } catch {
      return this.scheduleReconnect();
    }
    if (this.closedByUs) return;
    const socket = this.factory(url);
    this.socket = socket;
    socket.onopen = () => {
      this.backoff.reset();
      this.setStatus("open");
      for (const sub of this.subs.values()) this.sendSubscribe(sub);
      for (const [topic, type] of this.advertised) this.send({ op: "advertise", topic, type });
    };
    socket.onmessage = (ev) => this.handle(String(ev.data));
    socket.onerror = () => undefined;
    socket.onclose = () => {
      if (this.socket !== socket) return;
      this.socket = null;
      this.failPending("connexion rosbridge perdue");
      if (!this.closedByUs) void this.scheduleReconnect();
    };
  }

  private async scheduleReconnect(): Promise<void> {
    this.setStatus("reconnecting");
    await new Promise((resolve) => this.timers.setTimeout(() => resolve(undefined), this.backoff.next()));
    if (!this.closedByUs) await this.connect();
  }

  private handle(raw: string): void {
    let msg: { op?: string; topic?: string; msg?: unknown; id?: string; result?: boolean; values?: unknown };
    try {
      msg = JSON.parse(raw);
    } catch {
      return;
    }
    if (msg.op === "publish" && msg.topic) {
      for (const sub of this.subs.values()) {
        if (sub.topic === msg.topic) for (const cb of sub.callbacks) cb(msg.msg);
      }
    } else if (msg.op === "service_response" && msg.id) {
      const call = this.pending.get(msg.id);
      if (!call) return;
      this.pending.delete(msg.id);
      this.timers.clearTimeout(call.timer);
      if (msg.result === false) call.reject(new ServiceError(String(msg.values ?? "échec du service")));
      else call.resolve(msg.values);
    }
  }

  private send(msg: Record<string, unknown>): boolean {
    if (!this.socket || this.socket.readyState !== OPEN) return false;
    this.socket.send(JSON.stringify(msg));
    return true;
  }

  private sendSubscribe(sub: Subscription): void {
    this.send({
      op: "subscribe",
      id: sub.id,
      topic: sub.topic,
      type: sub.type,
      throttle_rate: sub.throttleMs,
      queue_length: 1,
    });
  }

  /** Abonnement ; renvoie la fonction de désabonnement. Rétabli après reconnexion. */
  subscribe(topic: string, type: string, cb: (msg: unknown) => void, throttleMs = 0): () => void {
    const key = `${topic}|${type}|${throttleMs}`;
    let sub = this.subs.get(key);
    if (!sub) {
      sub = { id: `sub:${topic}:${++this.seq}`, topic, type, throttleMs, callbacks: new Set() };
      this.subs.set(key, sub);
      this.sendSubscribe(sub);
    }
    sub.callbacks.add(cb);
    const current = sub;
    return () => {
      current.callbacks.delete(cb);
      if (current.callbacks.size === 0 && this.subs.get(key) === current) {
        this.subs.delete(key);
        this.send({ op: "unsubscribe", id: current.id, topic });
      }
    };
  }

  publish(topic: string, type: string, msg: unknown): boolean {
    if (this.advertised.get(topic) !== type) {
      this.advertised.set(topic, type);
      this.send({ op: "advertise", topic, type });
    }
    return this.send({ op: "publish", topic, msg });
  }

  callService<T = unknown>(service: string, args: Record<string, unknown> = {}, timeoutMs = 5000): Promise<T> {
    const id = `call:${service}:${++this.seq}`;
    return new Promise<T>((resolve, reject) => {
      const timer = this.timers.setTimeout(() => {
        this.pending.delete(id);
        reject(new ServiceError(`${service} : pas de réponse`));
      }, timeoutMs);
      this.pending.set(id, { resolve: resolve as (v: unknown) => void, reject, timer });
      if (!this.send({ op: "call_service", id, service, args })) {
        this.pending.delete(id);
        this.timers.clearTimeout(timer);
        reject(new ServiceError("rosbridge non connecté"));
      }
    });
  }

  private failPending(reason: string): void {
    for (const [id, call] of this.pending) {
      this.timers.clearTimeout(call.timer);
      call.reject(new ServiceError(reason));
      this.pending.delete(id);
    }
  }

  close(): void {
    this.closedByUs = true;
    this.socket?.close();
    this.socket = null;
    this.failPending("rosbridge fermé");
    this.setStatus("closed");
  }
}
