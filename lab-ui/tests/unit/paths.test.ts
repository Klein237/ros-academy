import { describe, expect, it } from "vitest";
import { baseName, encodePath, isValidName, joinPath, normalizePath, parentOf, PathError } from "../../src/paths";

describe("chemins", () => {
  it("normalise les chemins relatifs à /home/etudiant", () => {
    expect(normalizePath("~/ws//module-02/./src/")).toBe("ws/module-02/src");
    expect(normalizePath("/ws/a.py")).toBe("ws/a.py");
    expect(normalizePath("")).toBe("");
  });

  it("refuse de sortir du dossier personnel", () => {
    expect(() => normalizePath("ws/../../etc/passwd")).toThrow(PathError);
    expect(() => joinPath("ws", "..")).toThrow(PathError);
  });

  it("parent, nom et encodage", () => {
    expect(parentOf("ws/src/a.py")).toBe("ws/src");
    expect(parentOf("a.py")).toBe("");
    expect(baseName("ws/src/a.py")).toBe("a.py");
    expect(encodePath("ws/mon nœud#1.py")).toBe("ws/mon%20n%C5%93ud%231.py");
  });

  it("valide les noms saisis", () => {
    expect(isValidName("talker.py")).toBe(true);
    for (const bad of ["", ".", "..", "a/b", "a\\b"]) expect(isValidName(bad)).toBe(false);
  });
});
