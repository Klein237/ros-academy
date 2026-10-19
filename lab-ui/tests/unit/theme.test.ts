import { afterEach, expect, it, vi } from "vitest";
import { currentTheme, onThemeChange, terminalTheme, THEMES } from "../../src/ui/theme";

/** matchMedia simulé : `sombre` dit si le système est en mode sombre ; `bascule` le change. */
function systeme(sombre: boolean) {
  const listeners = new Set<() => void>();
  const q = {
    get matches() {
      return sombre;
    },
    addEventListener: (_: string, l: () => void) => listeners.add(l),
    removeEventListener: (_: string, l: () => void) => listeners.delete(l),
  };
  vi.stubGlobal("window", { matchMedia: (media: string) => (media === "(prefers-color-scheme: dark)" ? q : null) });
  return {
    bascule(v: boolean) {
      sombre = v;
      listeners.forEach((l) => l());
    },
    abonnes: () => listeners.size,
  };
}

afterEach(() => vi.unstubAllGlobals());

it("suit le thème du système", () => {
  systeme(false);
  expect(currentTheme().name).toBe("clair");
  systeme(true);
  expect(currentTheme().name).toBe("sombre");
});

it("sans matchMedia (tests, vieux navigateur) : le thème sombre d'avant", () => {
  expect(currentTheme()).toBe(THEMES.sombre);
});

it("prévient quand le système change, jusqu'au désabonnement", () => {
  const s = systeme(true);
  const vus: string[] = [];
  const stop = onThemeChange((t) => vus.push(t.name));
  s.bascule(false);
  s.bascule(true);
  stop();
  s.bascule(false);
  expect(vus).toEqual(["clair", "sombre"]);
  expect(s.abonnes()).toBe(0);
});

it("terminal clair : couleurs ANSI foncées, lisibles sur le fond clair", () => {
  const sombre = terminalTheme(THEMES.sombre);
  expect(sombre.background).toBe("#101114");
  expect(sombre.white).toBeUndefined(); // palette par défaut d'xterm, faite pour le sombre
  const clair = terminalTheme(THEMES.clair);
  expect(clair.background).toBe("#fbfaf6");
  expect(clair.foreground).toBe("#12171c");
  for (const c of ["white", "yellow", "brightYellow", "cyan"]) {
    expect(luminance(clair[c])).toBeLessThan(0.2); // ≥ 4,5:1 sur #fbfaf6
  }
});

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
