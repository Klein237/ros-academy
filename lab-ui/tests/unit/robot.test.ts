import { expect, it } from "vitest";
import {
  descriptionFromMessage,
  descriptionFromParameters,
  formatJoint,
  isMovable,
  jointPositions,
  jointStateMessage,
  sliderRange,
  transformTo,
} from "../../src/ros/robot";

const URDF = '<robot name="r"><link name="base_link"/></robot>';

it("lit la description publiée ou demandée à robot_state_publisher", () => {
  expect(descriptionFromMessage({ data: URDF })).toBe(URDF);
  expect(descriptionFromMessage({ data: "" })).toBeNull();
  expect(descriptionFromParameters({ values: [{ type: 4, string_value: URDF }] })).toBe(URDF);
  expect(descriptionFromParameters({ values: [{ type: 0 }] })).toBeNull(); // paramètre absent
  expect(descriptionFromParameters({})).toBeNull();
});

it("positions d'un JointState, par nom", () => {
  const p = jointPositions({ name: ["a", "b", "c"], position: [0.5, Number.NaN] });
  expect([...p]).toEqual([["a", 0.5]]);
  expect(jointPositions({ name: "a" }).size).toBe(0);
});

it("plage et affichage des curseurs selon le type de joint", () => {
  const revolute = { jointType: "revolute", limit: { lower: -1, upper: 2 } };
  const continuous = { jointType: "continuous", limit: { lower: 0, upper: 0 } };
  const prismatic = { jointType: "prismatic", limit: { lower: 0, upper: 0.2 } };
  expect(sliderRange(revolute)).toEqual([-1, 2]);
  expect(sliderRange(continuous)).toEqual([-Math.PI, Math.PI]);
  expect(sliderRange(prismatic)).toEqual([0, 0.2]);
  expect(isMovable({ jointType: "fixed", limit: { lower: 0, upper: 0 } })).toBe(false);
  // le second doigt d'une pince suit le premier : pas de curseur à lui
  expect(isMovable({ ...prismatic, mimicJoint: "pince" })).toBe(false);
  expect(formatJoint(revolute, Math.PI / 2)).toBe("90°");
  expect(formatJoint(prismatic, 0.05)).toBe("0.050 m");
});

it("message JointState horodaté", () => {
  const msg = jointStateMessage(new Map([["roue", 1.5]]), 12_345);
  expect(msg).toMatchObject({ name: ["roue"], position: [1.5], header: { stamp: { sec: 12, nanosec: 345_000_000 } } });
});

it("transformation vers la racine du robot dans /tf", () => {
  const t = (parent: string, child: string, x: number) => ({
    header: { frame_id: parent },
    child_frame_id: child,
    transform: { translation: { x, y: 0, z: 0 }, rotation: { x: 0, y: 0, z: 0, w: 1 } },
  });
  const found = transformTo({ transforms: [t("odom", "base_link", 1), t("base_link", "roue", 2), t("odom", "base_link", 3)] }, "base_link");
  expect(found?.parent).toBe("odom");
  expect(found?.transform.translation.x).toBe(3);
  expect(transformTo({ transforms: [] }, "base_link")).toBeNull();
});
