/** API du Hub vue par le navigateur, avec le jeton court de /hub/lab_token. */

export interface LabToken {
  user: string;
  token: string;
  expires_in: number;
  server_url: string;
}

export interface ServerStatus {
  ready: boolean;
  pending: string | null;
}

export interface ProgressEvent {
  progress?: number;
  message?: string;
  ready?: boolean;
  failed?: boolean;
}

export type StartResult = "started" | "pending" | "running" | "full";

export class HttpError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

/** L'étudiant n'a pas (ou plus) de cookie du Hub : il doit repasser par le site. */
export class NotLoggedIn extends Error {}

type FetchFn = (input: string, init?: RequestInit) => Promise<Response>;

/** Découpe un flux text/event-stream ; `rest` est le morceau incomplet à garder. */
export function parseSSE(buffer: string): { events: ProgressEvent[]; rest: string } {
  const blocks = buffer.replace(/\r\n/g, "\n").split("\n\n");
  const rest = blocks.pop() ?? "";
  const events: ProgressEvent[] = [];
  for (const block of blocks) {
    const data = block
      .split("\n")
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trimStart())
      .join("\n");
    if (!data) continue;
    try {
      events.push(JSON.parse(data) as ProgressEvent);
    } catch {
      // ligne de keep-alive ou morceau illisible : ignoré
    }
  }
  return { events, rest };
}

export class HubClient {
  private current: LabToken | null = null;
  private obtainedAt = 0;

  constructor(
    private readonly fetchFn: FetchFn = (input, init) => fetch(input, init),
    private readonly now: () => number = () => Date.now(),
    private readonly origin: { protocol: string; host: string } = location,
  ) {}

  get user(): string {
    if (!this.current) throw new NotLoggedIn("jeton absent");
    return this.current.user;
  }

  get serverUrl(): string {
    if (!this.current) throw new NotLoggedIn("jeton absent");
    return this.current.server_url;
  }

  /** Jeton valide, renouvelé 5 min avant son expiration. */
  async token(): Promise<string> {
    const marginMs = 5 * 60_000;
    if (!this.current || this.now() > this.obtainedAt + this.current.expires_in * 1000 - marginMs) {
      await this.refreshToken();
    }
    return this.current!.token;
  }

  async refreshToken(): Promise<LabToken> {
    let r: Response;
    try {
      r = await this.fetchFn("/hub/lab_token", { credentials: "same-origin", cache: "no-store" });
    } catch (e) {
      throw new HttpError(0, `Hub injoignable : ${String(e)}`);
    }
    if (r.status === 401 || r.status === 403) throw new NotLoggedIn("cookie du Hub absent ou expiré");
    if (!r.ok) throw new HttpError(r.status, `jeton refusé (${r.status})`);
    this.current = (await r.json()) as LabToken;
    this.obtainedAt = this.now();
    return this.current;
  }

  /** Requête authentifiée ; un 403 provoque un seul renouvellement du jeton. */
  async request(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
    const headers = new Headers(init.headers);
    headers.set("Authorization", `token ${await this.token()}`);
    const r = await this.fetchFn(path, { ...init, headers, credentials: "omit", cache: "no-store" });
    if ((r.status === 401 || r.status === 403) && retry) {
      await this.refreshToken();
      return this.request(path, init, false);
    }
    return r;
  }

  private async userApi(suffix = ""): Promise<string> {
    await this.token();
    return `/hub/api/users/${encodeURIComponent(this.user)}${suffix}`;
  }

  async server(): Promise<ServerStatus | null> {
    const r = await this.request(await this.userApi());
    if (!r.ok) throw new HttpError(r.status, `statut du serveur illisible (${r.status})`);
    const body = (await r.json()) as { servers?: Record<string, ServerStatus> };
    const server = body.servers?.[""];
    return server ? { ready: Boolean(server.ready), pending: server.pending ?? null } : null;
  }

  async start(): Promise<StartResult> {
    const r = await this.request(await this.userApi("/server"), { method: "POST" });
    switch (r.status) {
      case 201:
        return "started";
      case 202:
        return "pending";
      case 400:
        return "running"; // déjà démarré (ou en cours d'arrêt : vérifié ensuite par server())
      case 429:
        return "full";
      case 502:
      case 503:
      case 504:
        // le proxy peut couper la requête pendant que le Hub démarre le conteneur :
        // l'état réel est vérifié ensuite (progression puis statut du serveur)
        return "pending";
      default:
        throw new HttpError(r.status, `démarrage refusé (${r.status}) : ${await r.text()}`);
    }
  }

  async stop(): Promise<void> {
    const r = await this.request(await this.userApi("/server"), { method: "DELETE" });
    if (!r.ok && r.status !== 204 && r.status !== 400) {
      throw new HttpError(r.status, `arrêt refusé (${r.status})`);
    }
  }

  /** Lit /server/progress jusqu'à `ready` ou `failed` (fetch, car EventSource n'envoie pas d'en-tête). */
  async progress(onEvent: (e: ProgressEvent) => void, signal?: AbortSignal): Promise<ProgressEvent | null> {
    const r = await this.request(await this.userApi("/server/progress"), {
      headers: { Accept: "text/event-stream" },
      signal,
    });
    if (!r.ok || !r.body) return null;
    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) return null;
        const parsed = parseSSE(buffer + decoder.decode(value, { stream: true }));
        buffer = parsed.rest;
        for (const event of parsed.events) {
          onEvent(event);
          if (event.ready || event.failed) return event;
        }
      }
    } finally {
      reader.cancel().catch(() => undefined);
    }
  }

  /** URL HTTP vers le serveur de l'étudiant. */
  serverPath(path: string): string {
    return `${this.serverUrl}${path.replace(/^\//, "")}`;
  }

  /** URL WebSocket : le navigateur ne sait pas y mettre d'en-tête, le jeton passe en paramètre. */
  async wsUrl(path: string): Promise<string> {
    const scheme = this.origin.protocol === "https:" ? "wss" : "ws";
    const sep = path.includes("?") ? "&" : "?";
    const token = encodeURIComponent(await this.token());
    return `${scheme}://${this.origin.host}${this.serverPath(path)}${sep}token=${token}`;
  }
}
