/** Terminaux jupyter-server : API REST + WebSocket avec reconnexion. */
import { Backoff, realTimers, type Timers } from "../backoff";
import { normalizePath } from "../paths";
import { HttpError, type HubClient } from "./hub";

type HubLike = Pick<HubClient, "request" | "serverPath" | "wsUrl">;

export class TerminalsClient {
  constructor(private readonly hub: HubLike) {}

  async create(cwd = ""): Promise<string> {
    const r = await this.hub.request(this.hub.serverPath("api/terminals"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cwd ? { cwd: normalizePath(cwd) } : {}),
    });
    if (!r.ok) throw new HttpError(r.status, `création du terminal refusée (${r.status})`);
    return ((await r.json()) as { name: string }).name;
  }

  /** Terminaux encore ouverts dans le conteneur (rechargement de la page). */
  async list(): Promise<string[]> {
    const r = await this.hub.request(this.hub.serverPath("api/terminals"));
    if (!r.ok) return [];
    return ((await r.json()) as { name: string }[]).map((t) => t.name);
  }

  /** null : impossible de savoir (réseau coupé). */
  async exists(name: string): Promise<boolean | null> {
    try {
      const r = await this.hub.request(this.hub.serverPath(`api/terminals/${encodeURIComponent(name)}`));
      if (r.status === 404) return false;
      return r.ok ? true : null;
    } catch {
      return null;
    }
  }

  async remove(name: string): Promise<void> {
    await this.hub.request(this.hub.serverPath(`api/terminals/${encodeURIComponent(name)}`), {
      method: "DELETE",
    });
  }

  socketUrl(name: string): Promise<string> {
    return this.hub.wsUrl(`terminals/websocket/${encodeURIComponent(name)}`);
  }
}

export interface SocketLike {
  readyState: number;
  onopen: ((ev: unknown) => void) | null;
  onclose: ((ev: unknown) => void) | null;
  onerror: ((ev: unknown) => void) | null;
  onmessage: ((ev: { data: unknown }) => void) | null;
  send(data: string): void;
  close(): void;
}

export type SocketFactory = (url: string) => SocketLike;
export const browserSocket: SocketFactory = (url) => new WebSocket(url) as unknown as SocketLike;

export type ConnectionStatus = "connecting" | "open" | "reconnecting" | "closed";

export interface TerminalConnectionOptions {
  name: string;
  client: Pick<TerminalsClient, "create" | "exists" | "socketUrl">;
  cwd?: string;
  onData(data: string): void;
  onStatus?(status: ConnectionStatus): void;
  /** Le terminal a été remplacé par un nouveau (l'ancien n'existait plus). */
  onReplaced?(name: string): void;
  /** Vrai si le conteneur tourne encore ; faux → on arrête de se reconnecter. */
  isServerAlive(): Promise<boolean>;
  socketFactory?: SocketFactory;
  timers?: Timers;
  backoff?: Backoff;
}

const OPEN = 1;

/**
 * Un terminal reste vivant dans le conteneur quand le WebSocket tombe :
 * on se reconnecte au même terminal, l'historique du shell est conservé.
 */
export class TerminalConnection {
  name: string;
  status: ConnectionStatus = "connecting";
  private socket: SocketLike | null = null;
  private closedByUs = false;
  private size: [number, number] | null = null;
  private readonly timers: Timers;
  private readonly backoff: Backoff;
  private readonly factory: SocketFactory;

  constructor(private readonly opts: TerminalConnectionOptions) {
    this.name = opts.name;
    this.timers = opts.timers ?? realTimers;
    this.backoff = opts.backoff ?? new Backoff();
    this.factory = opts.socketFactory ?? browserSocket;
  }

  private setStatus(status: ConnectionStatus): void {
    this.status = status;
    this.opts.onStatus?.(status);
  }

  async connect(): Promise<void> {
    if (this.closedByUs) return;
    let url: string;
    try {
      url = await this.opts.client.socketUrl(this.name);
    } catch {
      return this.scheduleReconnect();
    }
    const socket = this.factory(url);
    this.socket = socket;
    socket.onopen = () => {
      this.backoff.reset();
      this.setStatus("open");
      if (this.size) this.sendRaw(["set_size", ...this.size]);
    };
    socket.onmessage = (ev) => {
      let msg: unknown;
      try {
        msg = JSON.parse(String(ev.data));
      } catch {
        return;
      }
      if (!Array.isArray(msg)) return;
      if (msg[0] === "stdout") this.opts.onData(String(msg[1]));
      // ["disconnect", …] : le shell s'est terminé (exit) ; la fermeture suit
    };
    socket.onerror = () => undefined;
    socket.onclose = () => {
      if (this.socket !== socket) return;
      this.socket = null;
      if (!this.closedByUs) void this.scheduleReconnect();
    };
  }

  private async scheduleReconnect(): Promise<void> {
    this.setStatus("reconnecting");
    await new Promise((resolve) => this.timers.setTimeout(() => resolve(undefined), this.backoff.next()));
    if (this.closedByUs) return;
    const exists = await this.opts.client.exists(this.name);
    if (exists !== true) {
      // conteneur arrêté : la page bascule sur l'écran « Lab arrêté »
      if (!(await this.opts.isServerAlive())) return this.close();
      if (exists === null) return this.scheduleReconnect(); // réseau encore coupé
      try {
        this.name = await this.opts.client.create(this.opts.cwd);
      } catch {
        return this.scheduleReconnect();
      }
      this.opts.onReplaced?.(this.name);
    }
    await this.connect();
  }

  private sendRaw(msg: unknown[]): void {
    if (this.socket && this.socket.readyState === OPEN) this.socket.send(JSON.stringify(msg));
  }

  send(data: string): void {
    this.sendRaw(["stdin", data]);
  }

  resize(rows: number, cols: number): void {
    this.size = [rows, cols];
    this.sendRaw(["set_size", rows, cols]);
  }

  close(): void {
    this.closedByUs = true;
    this.socket?.close();
    this.socket = null;
    this.setStatus("closed");
  }
}
