import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { TerminalConnection } from "../../src/api/terminals";
import { FakeSocket, flush } from "./fakes";

beforeEach(() => {
  vi.useFakeTimers();
  FakeSocket.all = [];
});
afterEach(() => vi.useRealTimers());

function make(opts: { exists?: (boolean | null)[]; alive?: boolean } = {}) {
  const exists = [...(opts.exists ?? [true])];
  const client = {
    create: vi.fn(async () => "2"),
    exists: vi.fn(async () => (exists.length > 1 ? exists.shift()! : exists[0]!)),
    socketUrl: vi.fn(async (name: string) => `wss://x/terminals/websocket/${name}?token=t`),
  };
  const data: string[] = [];
  const replaced: string[] = [];
  const statuses: string[] = [];
  const conn = new TerminalConnection({
    name: "1",
    client,
    onData: (d) => data.push(d),
    onReplaced: (n) => replaced.push(n),
    onStatus: (s) => statuses.push(s),
    isServerAlive: async () => opts.alive ?? true,
    socketFactory: (url) => new FakeSocket(url),
  });
  return { conn, client, data, replaced, statuses };
}

it("relaie stdout et envoie stdin / set_size", async () => {
  const { conn, data } = make();
  await conn.connect();
  conn.resize(24, 80);
  FakeSocket.last().open();
  FakeSocket.last().receive(["stdout", "etudiant@lab:~$ "]);
  conn.send("ls\r");
  expect(data).toEqual(["etudiant@lab:~$ "]);
  expect(FakeSocket.last().sent).toEqual([["set_size", 24, 80], ["stdin", "ls\r"]]);
});

it("coupure réseau → reconnexion au même terminal", async () => {
  const { conn, client, statuses } = make({ exists: [null, true] });
  await conn.connect();
  FakeSocket.last().open();
  FakeSocket.last().drop();
  expect(statuses.at(-1)).toBe("reconnecting");
  await vi.advanceTimersByTimeAsync(500); // 1re tentative : réseau encore coupé
  await vi.advanceTimersByTimeAsync(1000);
  await flush();
  expect(FakeSocket.all).toHaveLength(2);
  expect(FakeSocket.last().url).toContain("/websocket/1?");
  expect(client.create).not.toHaveBeenCalled();
  FakeSocket.last().open();
  expect(statuses.at(-1)).toBe("open");
});

it("terminal disparu (404) → nouveau terminal", async () => {
  const { conn, client, replaced } = make({ exists: [false] });
  await conn.connect();
  FakeSocket.last().open();
  FakeSocket.last().drop();
  await vi.advanceTimersByTimeAsync(500);
  await flush();
  expect(client.create).toHaveBeenCalled();
  expect(replaced).toEqual(["2"]);
  expect(FakeSocket.last().url).toContain("/websocket/2?");
});

it("conteneur arrêté → plus de reconnexion", async () => {
  const { conn, statuses } = make({ exists: [null], alive: false });
  await conn.connect();
  FakeSocket.last().open();
  FakeSocket.last().drop();
  await vi.advanceTimersByTimeAsync(10_000);
  expect(statuses.at(-1)).toBe("closed");
  expect(FakeSocket.all).toHaveLength(1);
});

it("fermeture volontaire → pas de reconnexion", async () => {
  const { conn } = make();
  await conn.connect();
  FakeSocket.last().open();
  conn.close();
  FakeSocket.last().drop();
  await vi.advanceTimersByTimeAsync(30_000);
  expect(FakeSocket.all).toHaveLength(1);
});
