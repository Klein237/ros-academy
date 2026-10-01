import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { RosbridgeClient, ServiceError } from "../../src/ros/rosbridge";
import { FakeSocket } from "./fakes";

beforeEach(() => {
  vi.useFakeTimers();
  FakeSocket.all = [];
});
afterEach(() => vi.useRealTimers());

async function connected() {
  const ros = new RosbridgeClient({
    url: async () => "wss://x/user/a/rosbridge/?token=t",
    socketFactory: (url) => new FakeSocket(url),
  });
  await ros.connect();
  FakeSocket.last().open();
  return ros;
}

it("s'abonne avec throttle et reçoit les messages du topic", async () => {
  const ros = await connected();
  const got: unknown[] = [];
  ros.subscribe("/odom", "nav_msgs/msg/Odometry", (m) => got.push(m), 50);
  expect(FakeSocket.last().sent[0]).toMatchObject({
    op: "subscribe",
    topic: "/odom",
    type: "nav_msgs/msg/Odometry",
    throttle_rate: 50,
    queue_length: 1,
  });
  FakeSocket.last().receive({ op: "publish", topic: "/odom", msg: { a: 1 } });
  FakeSocket.last().receive({ op: "publish", topic: "/other", msg: { a: 2 } });
  expect(got).toEqual([{ a: 1 }]);
});

it("se désabonne quand le dernier abonné part", async () => {
  const ros = await connected();
  const off1 = ros.subscribe("/odom", "nav_msgs/msg/Odometry", () => undefined);
  const off2 = ros.subscribe("/odom", "nav_msgs/msg/Odometry", () => undefined);
  off1();
  expect(FakeSocket.last().sent).toHaveLength(1);
  off2();
  expect(FakeSocket.last().sent[1]).toMatchObject({ op: "unsubscribe", topic: "/odom" });
});

it("rétablit abonnements et annonces après reconnexion", async () => {
  const ros = await connected();
  ros.subscribe("/odom", "nav_msgs/msg/Odometry", () => undefined);
  ros.publish("/cmd_vel", "geometry_msgs/msg/Twist", { linear: { x: 1 } });
  FakeSocket.last().drop();
  expect(ros.status).toBe("reconnecting");
  await vi.advanceTimersByTimeAsync(1000);
  FakeSocket.last().open();
  const ops = FakeSocket.last().sent.map((m) => (m as { op: string; topic: string }).op + " " + (m as { topic: string }).topic);
  expect(ops).toEqual(["subscribe /odom", "advertise /cmd_vel"]);
});

it("annonce un topic avant la première publication", async () => {
  const ros = await connected();
  ros.publish("/cmd_vel", "geometry_msgs/msg/Twist", {});
  ros.publish("/cmd_vel", "geometry_msgs/msg/Twist", {});
  expect(FakeSocket.last().sent.map((m) => (m as { op: string }).op)).toEqual(["advertise", "publish", "publish"]);
});

it("appel de service : réponse associée par id, échec et délai", async () => {
  const ros = await connected();
  const ok = ros.callService<{ topics: string[] }>("/rosapi/topics");
  const sent = FakeSocket.last().sent[0] as { id: string; op: string };
  expect(sent.op).toBe("call_service");
  FakeSocket.last().receive({ op: "service_response", id: "autre", result: true, values: {} });
  FakeSocket.last().receive({ op: "service_response", id: sent.id, result: true, values: { topics: ["/odom"] } });
  await expect(ok).resolves.toEqual({ topics: ["/odom"] });

  const ko = ros.callService("/x");
  const id = (FakeSocket.last().sent[1] as { id: string }).id;
  FakeSocket.last().receive({ op: "service_response", id, result: false, values: "nope" });
  await expect(ko).rejects.toBeInstanceOf(ServiceError);

  const late = ros.callService("/y", {}, 1000);
  vi.advanceTimersByTime(1000);
  await expect(late).rejects.toThrow(/pas de réponse/);
});

it("appel de service sans connexion → erreur immédiate", async () => {
  const ros = new RosbridgeClient({ url: async () => "x", socketFactory: (u) => new FakeSocket(u) });
  await expect(ros.callService("/rosapi/topics")).rejects.toThrow(/non connecté/);
});
