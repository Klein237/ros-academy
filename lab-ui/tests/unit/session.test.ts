import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { HttpError, NotLoggedIn, type ProgressEvent, type ServerStatus, type StartResult } from "../../src/api/hub";
import { Session, type SessionState } from "../../src/session";
import { flush } from "./fakes";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

function fakeHub(opts: {
  token?: () => Promise<unknown>;
  start?: StartResult[];
  progress?: ProgressEvent[];
  server?: (ServerStatus | null)[];
}) {
  const starts = [...(opts.start ?? ["started"])];
  const servers = [...(opts.server ?? [{ ready: true, pending: null }])];
  return {
    refreshToken: vi.fn(opts.token ?? (async () => ({}))),
    start: vi.fn(async () => starts.shift() ?? "running"),
    progress: vi.fn(async (cb: (e: ProgressEvent) => void) => {
      const events = opts.progress ?? [{ progress: 100, ready: true }];
      events.forEach(cb);
      return events.at(-1) ?? null;
    }),
    server: vi.fn(async () => (servers.length > 1 ? servers.shift()! : servers[0]!)),
    stop: vi.fn(async () => undefined),
  };
}

function track(session: Session): SessionState["kind"][] {
  const kinds: SessionState["kind"][] = [];
  session.onChange((s) => kinds.push(s.kind));
  return kinds;
}

it("démarrage normal : auth → starting → ready", async () => {
  const s = new Session(fakeHub({}) as never);
  const kinds = track(s);
  await s.open();
  expect(kinds[0]).toBe("auth");
  expect(kinds).toContain("starting");
  expect(s.state.kind).toBe("ready");
});

it("sans cookie du Hub → noauth", async () => {
  const s = new Session(fakeHub({ token: async () => Promise.reject(new NotLoggedIn("x")) }) as never);
  await s.open();
  expect(s.state.kind).toBe("noauth");
});

it("serveur plein (429) → full, puis nouvel essai automatique", async () => {
  const hub = fakeHub({ start: ["full", "started"] });
  const s = new Session(hub as never, { fullRetryMs: 15_000 });
  await s.open();
  expect(s.state).toEqual({ kind: "full", retryInMs: 15_000 });
  await vi.advanceTimersByTimeAsync(15_000);
  await flush();
  expect(hub.start).toHaveBeenCalledTimes(2);
  expect(s.state.kind).toBe("ready");
});

it("échec signalé par la progression → failed", async () => {
  const s = new Session(fakeHub({ progress: [{ progress: 50 }, { failed: true, message: "Spawn failed" }] }) as never);
  await s.open();
  expect(s.state.kind).toBe("failed");
});

it("serveur déjà démarré → ready sans lire la progression", async () => {
  const hub = fakeHub({ start: ["running"] });
  const s = new Session(hub as never);
  await s.open();
  expect(hub.progress).not.toHaveBeenCalled();
  expect(s.state.kind).toBe("ready");
});

it("ancien conteneur en cours d'arrêt → on redemande le démarrage", async () => {
  const hub = fakeHub({ start: ["running", "started"], server: [null, { ready: true, pending: null }] });
  const s = new Session(hub as never, { pollMs: 10 });
  const done = s.open();
  await vi.advanceTimersByTimeAsync(50);
  await done;
  expect(hub.start).toHaveBeenCalledTimes(2);
  expect(s.state.kind).toBe("ready");
});

it("conteneur jamais prêt → failed après le délai", async () => {
  const hub = fakeHub({ server: [{ ready: false, pending: "spawn" }] });
  const s = new Session(hub as never, { startTimeoutMs: 5000, pollMs: 1000 });
  const done = s.open();
  await vi.advanceTimersByTimeAsync(6000);
  await done;
  expect(s.state).toEqual({ kind: "failed", message: "Le conteneur met trop de temps à démarrer." });
});

it("checkAlive : conteneur disparu → stopped ; réseau coupé → on ne conclut rien", async () => {
  const hub = fakeHub({ server: [{ ready: true, pending: null }, null] });
  const s = new Session(hub as never);
  await s.open();
  hub.server.mockRejectedValueOnce(new TypeError("offline"));
  expect(await s.checkAlive()).toBe(true);
  expect(await s.checkAlive()).toBe(false);
  expect(s.state).toEqual({ kind: "stopped", reason: "external" });
});

it("arrêt pour inactivité : DELETE du serveur", async () => {
  const hub = fakeHub({});
  const s = new Session(hub as never);
  await s.open();
  await s.stop("idle");
  expect(hub.stop).toHaveBeenCalled();
  expect(s.state).toEqual({ kind: "stopped", reason: "idle" });
});

it("statut momentanément illisible (503) pendant le démarrage → on continue d'attendre", async () => {
  const hub = fakeHub({ start: ["pending"], progress: [] });
  hub.server.mockRejectedValueOnce(new HttpError(503, "proxy")).mockRejectedValueOnce(new TypeError("offline"));
  const s = new Session(hub as never, { pollMs: 10 });
  const done = s.open();
  await vi.advanceTimersByTimeAsync(100);
  await done;
  expect(s.state.kind).toBe("ready");
});

it("erreur non passagère du statut → failed", async () => {
  const hub = fakeHub({ start: ["pending"], progress: [] });
  hub.server.mockRejectedValueOnce(new HttpError(400, "bad"));
  const s = new Session(hub as never, { pollMs: 10 });
  await s.open();
  expect(s.state.kind).toBe("failed");
});
