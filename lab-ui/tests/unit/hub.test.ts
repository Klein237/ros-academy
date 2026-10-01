import { describe, expect, it, vi } from "vitest";
import { HubClient, NotLoggedIn, parseSSE } from "../../src/api/hub";
import { json } from "./fakes";

const TOKEN = { user: "alice", token: "t1", expires_in: 3600, server_url: "/user/alice/" };
const origin = { protocol: "https:", host: "lab.example" };

function hubWith(...responses: Response[]) {
  const fetchFn = vi.fn(async () => responses.shift() ?? json(500));
  let now = 0;
  const hub = new HubClient(fetchFn, () => now, origin);
  return { hub, fetchFn, advance: (ms: number) => (now += ms) };
}

describe("parseSSE", () => {
  it("lit des événements découpés en plusieurs morceaux", () => {
    const first = parseSSE('data: {"progress": 10, "message": "Spawning"}\n\ndata: {"progr');
    expect(first.events).toEqual([{ progress: 10, message: "Spawning" }]);
    const second = parseSSE(first.rest + 'ess": 100, "ready": true}\n\n');
    expect(second.events).toEqual([{ progress: 100, ready: true }]);
    expect(second.rest).toBe("");
  });

  it("ignore les lignes de keep-alive et le JSON illisible", () => {
    expect(parseSSE(": keepalive\n\ndata: {oops\n\n").events).toEqual([]);
  });
});

describe("HubClient", () => {
  it("demande le jeton avec le cookie du Hub puis l'envoie en en-tête, sans cookie", async () => {
    const { hub, fetchFn } = hubWith(json(200, TOKEN), json(200, { servers: { "": { ready: true, pending: null } } }));
    expect(await hub.server()).toEqual({ ready: true, pending: null });
    const calls = fetchFn.mock.calls as unknown as [string, RequestInit][];
    expect(calls[0]![0]).toBe("/hub/lab_token");
    expect(calls[0]![1].credentials).toBe("same-origin");
    expect(calls[1]![0]).toBe("/hub/api/users/alice");
    expect(calls[1]![1].credentials).toBe("omit");
    expect(new Headers(calls[1]![1].headers).get("Authorization")).toBe("token t1");
  });

  it("sans cookie du Hub → NotLoggedIn", async () => {
    const { hub } = hubWith(json(403));
    await expect(hub.refreshToken()).rejects.toBeInstanceOf(NotLoggedIn);
  });

  it("renouvelle le jeton avant son expiration", async () => {
    const { hub, fetchFn, advance } = hubWith(json(200, TOKEN), json(200, { ...TOKEN, token: "t2" }));
    expect(await hub.token()).toBe("t1");
    advance(50 * 60_000);
    expect(await hub.token()).toBe("t1");
    advance(6 * 60_000);
    expect(await hub.token()).toBe("t2");
    expect(fetchFn).toHaveBeenCalledTimes(2);
  });

  it("un 403 renouvelle le jeton une seule fois", async () => {
    const { hub, fetchFn } = hubWith(json(200, TOKEN), json(403), json(200, { ...TOKEN, token: "t2" }), json(403));
    expect((await hub.request("/hub/api/users/alice")).status).toBe(403);
    expect(fetchFn).toHaveBeenCalledTimes(4);
  });

  it.each([
    [201, "started"],
    [202, "pending"],
    [400, "running"],
    [429, "full"],
  ])("POST /server → %i = %s", async (status, result) => {
    const { hub } = hubWith(json(200, TOKEN), json(status));
    expect(await hub.start()).toBe(result);
  });

  it("une autre erreur de démarrage est remontée", async () => {
    const { hub } = hubWith(json(200, TOKEN), json(500, { message: "boom" }));
    await expect(hub.start()).rejects.toThrow(/500/);
  });

  it("lit la progression jusqu'à ready", async () => {
    const body = new ReadableStream({
      start(c) {
        const enc = new TextEncoder();
        c.enqueue(enc.encode('data: {"progress": 50, "message": "Spawning"}\n\n'));
        c.enqueue(enc.encode('data: {"progress": 100, "ready": true}\n\n'));
        c.close();
      },
    });
    const { hub } = hubWith(json(200, TOKEN), new Response(body, { status: 200 }));
    const seen: number[] = [];
    const last = await hub.progress((e) => seen.push(e.progress ?? -1));
    expect(seen).toEqual([50, 100]);
    expect(last?.ready).toBe(true);
  });

  it("URL WebSocket avec le jeton en paramètre", async () => {
    const { hub } = hubWith(json(200, { ...TOKEN, token: "a b" }));
    await hub.refreshToken();
    expect(await hub.wsUrl("terminals/websocket/1")).toBe(
      "wss://lab.example/user/alice/terminals/websocket/1?token=a%20b",
    );
    expect(await hub.wsUrl("rosbridge/?x=1")).toBe("wss://lab.example/user/alice/rosbridge/?x=1&token=a%20b");
  });
});
