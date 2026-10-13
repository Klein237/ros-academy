/** Description et état d'un robot reçus par rosbridge : fonctions pures de la Vue 3D. */

export interface JointLimits {
  jointType: string;
  limit: { lower: number; upper: number };
}

/** Description URDF dans la réponse de GetParameters (robot_state_publisher), ou null. */
export function descriptionFromParameters(values: unknown): string | null {
  const list = (values as { values?: unknown })?.values;
  if (!Array.isArray(list) || list.length === 0) return null;
  const text = (list[0] as { string_value?: unknown })?.string_value;
  return typeof text === "string" && text.includes("<robot") ? text : null;
}

/** Description URDF publiée sur un topic std_msgs/String, ou null. */
export function descriptionFromMessage(msg: unknown): string | null {
  const text = (msg as { data?: unknown })?.data;
  return typeof text === "string" && text.includes("<robot") ? text : null;
}

/** Positions d'un sensor_msgs/JointState, par nom de joint (valeurs non numériques ignorées). */
export function jointPositions(msg: unknown): Map<string, number> {
  const out = new Map<string, number>();
  const { name, position } = (msg ?? {}) as { name?: unknown; position?: unknown };
  if (!Array.isArray(name) || !Array.isArray(position)) return out;
  name.forEach((n, i) => {
    const p = position[i];
    if (typeof n === "string" && typeof p === "number" && Number.isFinite(p)) out.set(n, p);
  });
  return out;
}

/** Joints qu'un curseur peut faire bouger, et leur plage. */
export function isMovable(joint: JointLimits): boolean {
  return joint.jointType === "revolute" || joint.jointType === "continuous" || joint.jointType === "prismatic";
}

export function sliderRange(joint: JointLimits): [number, number] {
  const { lower, upper } = joint.limit;
  if (joint.jointType === "continuous" || !(upper > lower)) {
    return joint.jointType === "prismatic" ? [-1, 1] : [-Math.PI, Math.PI];
  }
  return [lower, upper];
}

/** Valeur lisible d'un joint : degrés pour une rotation, mètres pour une translation. */
export function formatJoint(joint: JointLimits, value: number): string {
  return joint.jointType === "prismatic" ? `${value.toFixed(3)} m` : `${((value * 180) / Math.PI).toFixed(0)}°`;
}

/** Message sensor_msgs/JointState pour les valeurs données. */
export function jointStateMessage(values: Map<string, number>, nowMs = Date.now()): Record<string, unknown> {
  const names = [...values.keys()];
  return {
    header: { stamp: { sec: Math.floor(nowMs / 1000), nanosec: (nowMs % 1000) * 1_000_000 }, frame_id: "" },
    name: names,
    position: names.map((n) => values.get(n)!),
    velocity: [],
    effort: [],
  };
}

export interface Transform {
  translation: { x: number; y: number; z: number };
  rotation: { x: number; y: number; z: number; w: number };
}

/** Transformation vers `child` dans un tf2_msgs/TFMessage (la dernière si plusieurs), ou null. */
export function transformTo(msg: unknown, child: string): { parent: string; transform: Transform } | null {
  const list = (msg as { transforms?: unknown })?.transforms;
  if (!Array.isArray(list)) return null;
  let found: { parent: string; transform: Transform } | null = null;
  for (const t of list) {
    const ts = t as { child_frame_id?: unknown; header?: { frame_id?: unknown }; transform?: Transform };
    if (ts?.child_frame_id === child && ts.transform?.translation && ts.transform?.rotation) {
      found = { parent: String(ts.header?.frame_id ?? ""), transform: ts.transform };
    }
  }
  return found;
}
