import { normalizePath } from "./paths";

export const IDLE_STOP_MS = 20 * 60_000;
export const IDLE_WARN_BEFORE_MS = 5 * 60_000;
export const FULL_RETRY_MS = 15_000;
export const START_TIMEOUT_MS = 150_000;
export const MAX_TEXT_FILE_BYTES = 1024 * 1024;

export interface LabConfig {
  /** Fichier à ouvrir au démarrage (« Ouvrir dans le lab » du site). */
  openPath: string | null;
  /** Dossier de départ de l'arborescence et des terminaux. */
  folder: string;
  idleStopMs: number;
  idleWarnMs: number;
}

function safePath(value: string | null): string | null {
  if (!value) return null;
  try {
    return normalizePath(value) || null;
  } catch {
    return null;
  }
}

export function readConfig(search: string): LabConfig {
  const params = new URLSearchParams(search);
  // ?inactivite=<secondes> ne peut que raccourcir le délai (tests de bout en bout).
  const seconds = Number(params.get("inactivite"));
  const idleStopMs =
    Number.isFinite(seconds) && seconds >= 10 ? Math.min(IDLE_STOP_MS, seconds * 1000) : IDLE_STOP_MS;
  const idleWarnMs = idleStopMs - Math.min(IDLE_WARN_BEFORE_MS, idleStopMs / 4);
  return {
    openPath: safePath(params.get("open")),
    folder: safePath(params.get("dossier")) ?? "",
    idleStopMs,
    idleWarnMs,
  };
}
