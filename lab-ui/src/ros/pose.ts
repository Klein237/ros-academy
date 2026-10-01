export interface Quaternion {
  x: number;
  y: number;
  z: number;
  w: number;
}

export interface Pose2D {
  x: number;
  y: number;
  theta: number;
}

/** Lacet (rotation autour de z) d'un quaternion, en radians dans ]-π, π]. */
export function yawFromQuaternion(q: Quaternion): number {
  return Math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z));
}

interface PoseLike {
  position: { x: number; y: number };
  orientation: Quaternion;
}

/** Accepte nav_msgs/Odometry, geometry_msgs/PoseStamped et geometry_msgs/Pose. */
export function poseFromMessage(msg: unknown): Pose2D | null {
  const m = msg as { pose?: { pose?: PoseLike } & Partial<PoseLike> } & Partial<PoseLike>;
  const pose: Partial<PoseLike> | undefined = m?.pose?.pose ?? m?.pose ?? m;
  if (!pose?.position || !pose.orientation) return null;
  const { x, y } = pose.position;
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return { x, y, theta: yawFromQuaternion(pose.orientation) };
}
