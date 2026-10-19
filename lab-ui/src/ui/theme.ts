/**
 * Thème du lab : il suit celui du système (prefers-color-scheme), comme le site.
 * Les couleurs des éléments dessinés en code (éditeur, terminaux, vues 2D et 3D) viennent d'ici ;
 * le reste est dans les variables de style.css.
 */

export type ThemeName = "clair" | "sombre";

export interface LabTheme {
  name: ThemeName;
  /** fond de l'éditeur, des terminaux et des vues */
  surface: string;
  text: string;
  muted: string;
  accent: string;
  /** vue 2D */
  grid: string;
  trail: string;
  axisX: string;
  axisY: string;
  /** vue 3D */
  scene: number;
  gridMajor: number;
  gridMinor: number;
  ground: number;
  /** terminaux */
  cursor: string;
  selection: string;
}

export const THEMES: Record<ThemeName, LabTheme> = {
  sombre: {
    name: "sombre", surface: "#101114", text: "#e6e3dc", muted: "#9a9aa3", accent: "#e3b866",
    grid: "#24252b", trail: "#3d7ea6", axisX: "#d9534f", axisY: "#5cb85c",
    scene: 0x101114, gridMajor: 0x3a3b42, gridMinor: 0x1f2026, ground: 0x2a2b31,
    cursor: "#e3b866", selection: "#4a3d22",
  },
  clair: {
    name: "clair", surface: "#fbfaf6", text: "#12171c", muted: "#5b5f66", accent: "#7a5718",
    grid: "#e7e2d6", trail: "#2f6f9a", axisX: "#c0392b", axisY: "#2e7d32",
    scene: 0xf3f0e8, gridMajor: 0xb9b2a2, gridMinor: 0xdcd6c8, ground: 0xcfc8b8,
    cursor: "#7a5718", selection: "#ecd6a6",
  },
};

const DARK = "(prefers-color-scheme: dark)";

function query(): MediaQueryList | null {
  return typeof window !== "undefined" && window.matchMedia ? window.matchMedia(DARK) : null;
}

/** Thème actuel ; sans matchMedia (tests), le sombre, celui d'avant. */
export function currentTheme(): LabTheme {
  const q = query();
  return THEMES[q && !q.matches ? "clair" : "sombre"];
}

/** Appelle `listener` à chaque changement de thème du système ; renvoie de quoi se désabonner. */
export function onThemeChange(listener: (theme: LabTheme) => void): () => void {
  const q = query();
  if (!q) return () => {};
  const handler = () => listener(currentTheme());
  q.addEventListener("change", handler);
  return () => q.removeEventListener("change", handler);
}

/** Thème des terminaux xterm : sur fond clair, les couleurs ANSI pâles deviennent lisibles. */
export function terminalTheme(t: LabTheme): Record<string, string> {
  const base = { background: t.surface, foreground: t.text, cursor: t.cursor, cursorAccent: t.surface, selectionBackground: t.selection };
  if (t.name === "sombre") return base;
  return {
    ...base,
    black: "#12171c", brightBlack: "#5b5f66",
    red: "#b91c1c", brightRed: "#c0392b",
    green: "#2e7d32", brightGreen: "#256b29",
    yellow: "#8a5d10", brightYellow: "#7a5718",
    blue: "#2f5aa8", brightBlue: "#244b8f",
    magenta: "#8e3a8e", brightMagenta: "#7a2f7a",
    cyan: "#1f6f7a", brightCyan: "#195e68",
    white: "#5b5f66", brightWhite: "#12171c",
  };
}
