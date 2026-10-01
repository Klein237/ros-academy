import { expect, it } from "vitest";
import { poseFromMessage, yawFromQuaternion } from "../../src/ros/pose";

const q = (theta: number) => ({ x: 0, y: 0, z: Math.sin(theta / 2), w: Math.cos(theta / 2) });

it("lacet d'un quaternion", () => {
  for (const theta of [0, 0.5, Math.PI / 2, -2, 3]) expect(yawFromQuaternion(q(theta))).toBeCloseTo(theta, 9);
});

it("lit Odometry, PoseStamped et Pose", () => {
  const pose = { position: { x: 1, y: -2, z: 0 }, orientation: q(1) };
  for (const msg of [{ pose: { pose } }, { pose }, pose]) {
    const p = poseFromMessage(msg)!;
    expect(p.x).toBe(1);
    expect(p.y).toBe(-2);
    expect(p.theta).toBeCloseTo(1, 9);
  }
});

it("ignore les messages sans pose", () => {
  expect(poseFromMessage({ data: "x" })).toBeNull();
  expect(poseFromMessage(null)).toBeNull();
  expect(poseFromMessage({ position: { x: NaN, y: 0 }, orientation: q(0) })).toBeNull();
});
