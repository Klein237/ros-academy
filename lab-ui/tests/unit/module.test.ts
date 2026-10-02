import { describe, expect, it, vi } from "vitest";
import { HttpError } from "../../src/api/hub";
import { readConfig } from "../../src/config";
import {
  cleanOutput,
  ensureCourseFile,
  findExitCode,
  installExerciseFiles,
  installLab,
  installLabWithRetry,
  isTransient,
  resetLab,
  scriptCommand,
} from "../../src/module";

/** Système de fichiers en mémoire, avec l'interface de ContentsClient utilisée par module.ts. */
class FakeContents {
  files = new Map<string, string>();
  dirs = new Set<string>();
  async exists(p: string) {
    return this.files.has(p) || this.dirs.has(p);
  }
  async mkdirp(p: string) {
    const parts = p.split("/");
    for (let i = 1; i <= parts.length; i++) this.dirs.add(parts.slice(0, i).join("/"));
  }
  async writeFile(p: string, c: string) {
    await this.mkdirp(p.split("/").slice(0, -1).join("/"));
    this.files.set(p, c);
  }
  async rename(from: string, to: string) {
    for (const [k, v] of [...this.files]) {
      if (k === from || k.startsWith(`${from}/`)) {
        this.files.delete(k);
        this.files.set(to + k.slice(from.length), v);
      }
    }
    for (const d of [...this.dirs]) {
      if (d === from || d.startsWith(`${from}/`)) {
        this.dirs.delete(d);
        this.dirs.add(to + d.slice(from.length));
      }
    }
  }
}

const LAB = [
  { path: "src/my_pkg/setup.py", content: "setup()\n" },
  { path: "src/my_pkg/package.xml", content: "<package/>\n" },
];

describe("installLab", () => {
  it("copie lab/ dans ~/ws/<id> la première fois", async () => {
    const fs = new FakeContents();
    expect(await installLab(fs, "02-noeud", LAB)).toBe("installe");
    expect(fs.files.get("ws/02-noeud/src/my_pkg/setup.py")).toBe("setup()\n");
  });

  it("n'écrase jamais un workspace existant", async () => {
    const fs = new FakeContents();
    await fs.writeFile("ws/02-noeud/src/my_pkg/setup.py", "mon travail\n");
    expect(await installLab(fs, "02-noeud", LAB)).toBe("existant");
    expect(fs.files.get("ws/02-noeud/src/my_pkg/setup.py")).toBe("mon travail\n");
    expect(fs.files.has("ws/02-noeud/src/my_pkg/package.xml")).toBe(false);
  });
});

describe("installLabWithRetry", () => {
  const noWait = { wait: async () => {} };

  /** Écritures qui échouent `failures` fois (la n-ième écriture de la tentative). */
  function flaky(fs: FakeContents, failures: number, error: unknown, at = 1) {
    const write = fs.writeFile.bind(fs);
    let count = 0;
    fs.writeFile = async (p: string, c: string) => {
      count += 1;
      if (failures > 0 && count === at) {
        failures -= 1;
        count = 0;
        throw error;
      }
      return write(p, c);
    };
  }

  it("complète une installation interrompue par une erreur passagère", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const fs = new FakeContents();
    flaky(fs, 1, new HttpError(502, "PUT : 502"), 2); // setup.py écrit, package.xml échoue
    expect(await installLabWithRetry(fs, "02-noeud", async () => LAB, noWait)).toBe("installe");
    expect(fs.files.get("ws/02-noeud/src/my_pkg/setup.py")).toBe("setup()\n");
    expect(fs.files.get("ws/02-noeud/src/my_pkg/package.xml")).toBe("<package/>\n");
  });

  it("retente le chargement des fichiers du module", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const fs = new FakeContents();
    const load = vi.fn().mockRejectedValueOnce(new TypeError("Failed to fetch")).mockResolvedValue(LAB);
    const delays: number[] = [];
    const wait = async (ms: number) => void delays.push(ms);
    expect(await installLabWithRetry(fs, "02-noeud", load, { delays: [10, 20], wait })).toBe("installe");
    expect(load).toHaveBeenCalledTimes(2);
    expect(delays).toEqual([10]);
  });

  it("ne réécrit pas le travail de l'étudiant lors d'une reprise", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const fs = new FakeContents();
    await fs.writeFile("ws/02-noeud/src/my_pkg/setup.py", "mon travail\n");
    const load = vi.fn().mockRejectedValueOnce(new HttpError(503, "503")).mockResolvedValue(LAB);
    expect(await installLabWithRetry(fs, "02-noeud", load, noWait)).toBe("existant");
    expect(fs.files.get("ws/02-noeud/src/my_pkg/setup.py")).toBe("mon travail\n");
    expect(fs.files.has("ws/02-noeud/src/my_pkg/package.xml")).toBe(false);
  });

  it("abandonne après la dernière tentative ou sur une erreur définitive", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const down = vi.fn().mockRejectedValue(new HttpError(0, "injoignable"));
    await expect(installLabWithRetry(new FakeContents(), "02-noeud", down, { delays: [1, 1], ...noWait })).rejects.toThrow(
      "injoignable",
    );
    expect(down).toHaveBeenCalledTimes(3);
    const refused = vi.fn().mockRejectedValue(new HttpError(403, "refusé"));
    await expect(installLabWithRetry(new FakeContents(), "02-noeud", refused, noWait)).rejects.toThrow("refusé");
    expect(refused).toHaveBeenCalledTimes(1);
  });

  it("isTransient", () => {
    expect(isTransient(new HttpError(0, ""))).toBe(true);
    expect(isTransient(new HttpError(500, ""))).toBe(true);
    expect(isTransient(new HttpError(404, ""))).toBe(false);
    expect(isTransient(new TypeError("Failed to fetch"))).toBe(true);
    expect(isTransient(new Error("autre"))).toBe(false);
  });
});

describe("ensureCourseFile", () => {
  const COURSE = [{ path: "src/my_pkg/my_pkg/node.py", content: "print(1)\n" }];

  it("crée un fichier du cours absent du workspace", async () => {
    const fs = new FakeContents();
    expect(await ensureCourseFile(fs, "02-noeud", "ws/02-noeud/src/my_pkg/my_pkg/node.py", COURSE)).toBe(true);
    expect(fs.files.get("ws/02-noeud/src/my_pkg/my_pkg/node.py")).toBe("print(1)\n");
  });

  it("ne touche pas à un fichier existant", async () => {
    const fs = new FakeContents();
    await fs.writeFile("ws/02-noeud/src/my_pkg/my_pkg/node.py", "ma version\n");
    expect(await ensureCourseFile(fs, "02-noeud", "ws/02-noeud/src/my_pkg/my_pkg/node.py", COURSE)).toBe(false);
    expect(fs.files.get("ws/02-noeud/src/my_pkg/my_pkg/node.py")).toBe("ma version\n");
  });

  it("ignore les chemins hors du workspace du module ou inconnus du cours", async () => {
    const fs = new FakeContents();
    expect(await ensureCourseFile(fs, "02-noeud", "ws/03-service/src/my_pkg/my_pkg/node.py", COURSE)).toBe(false);
    expect(await ensureCourseFile(fs, "02-noeud", "ws/02-noeud/src/autre.py", COURSE)).toBe(false);
    expect(fs.files.size).toBe(0);
  });
});

it("installe les fichiers de l'exercice dans ~/.academy/<id>", async () => {
  const fs = new FakeContents();
  await installExerciseFiles(fs, "02-noeud", [
    { path: "check.sh", content: "#!/usr/bin/env bash\n" },
    { path: "depart/src/a.py", content: "x\n" },
  ]);
  expect([...fs.files.keys()].sort()).toEqual([".academy/02-noeud/check.sh", ".academy/02-noeud/depart/src/a.py"]);
});

it("réinitialiser renomme l'ancien dossier puis réinstalle", async () => {
  const fs = new FakeContents();
  await fs.writeFile("ws/02-noeud/src/my_pkg/setup.py", "mon travail\n");
  const backup = await resetLab(fs, "02-noeud", LAB, new Date("2026-10-02T09:15:30Z"));
  expect(backup).toBe("ws/02-noeud.ancien-20261002-091530");
  expect(fs.files.get(`${backup}/src/my_pkg/setup.py`)).toBe("mon travail\n");
  expect(fs.files.get("ws/02-noeud/src/my_pkg/setup.py")).toBe("setup()\n");
});

describe("exécution des scripts", () => {
  it("la commande ne contient pas le marqueur en clair (l'écho du terminal ne le déclenche pas)", () => {
    const cmd = scriptCommand("02-noeud", "check.sh", "abc123");
    expect(cmd).toContain('EXERCICE="$HOME/.academy/02-noeud" WS="$HOME/ws/02-noeud-exercice"');
    expect(cmd).toContain('bash "$HOME/.academy/02-noeud/check.sh"');
    expect(findExitCode(cmd, "abc123")).toBeNull();
  });

  it("dans un vrai bash, le marqueur donne le code de sortie du script", async () => {
    const { execFileSync } = await import("node:child_process");
    const { mkdtempSync, mkdirSync, writeFileSync } = await import("node:fs");
    const { tmpdir } = await import("node:os");
    const { join } = await import("node:path");
    const home = mkdtempSync(join(tmpdir(), "academy-"));
    mkdirSync(join(home, ".academy/02-noeud"), { recursive: true });
    writeFileSync(join(home, ".academy/02-noeud/check.sh"), 'echo "WS=$WS"; exit 3\n');
    const cmd = scriptCommand("02-noeud", "check.sh", "n0nce").replace(/^clear; /, "");
    const out = execFileSync("bash", ["-c", cmd], { env: { HOME: home, PATH: process.env.PATH }, encoding: "utf8" });
    expect(findExitCode(out, "n0nce")).toBe(3);
    expect(cleanOutput(out, "n0nce")).toBe(`WS=${home}/ws/02-noeud-exercice`);
  });

  it("lit le code de sortie et nettoie la sortie", () => {
    const out = '\x1b[32m$\x1b[0m clear; env … echo "__ACADEMY_""abc123_$?__"\r\nLe robot n\'avance pas.\r\n__ACADEMY_abc123_1__\r\n';
    expect(findExitCode(out, "abc123")).toBe(1);
    expect(findExitCode("__ACADEMY_autre_0__", "abc123")).toBeNull();
    expect(cleanOutput(out, "abc123")).toBe("Le robot n'avance pas.");
  });
});

it("lit ?module et ?exercice, et refuse les identifiants invalides", () => {
  expect(readConfig("?module=02-noeud&exercice=1")).toMatchObject({ moduleId: "02-noeud", exercice: true });
  expect(readConfig("?module=../etc").moduleId).toBeNull();
  expect(readConfig("?module=02_noeud").moduleId).toBeNull();
  expect(readConfig("").exercice).toBe(false);
});
