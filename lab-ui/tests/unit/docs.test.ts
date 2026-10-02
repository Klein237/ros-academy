import { expect, it } from "vitest";
import { OpenDocuments } from "../../src/docs";

it("un fichier modifié est non enregistré jusqu'à sa sauvegarde", () => {
  const d = new OpenDocuments();
  d.open("a.py", "print(1)\n");
  expect(d.isDirty("a.py")).toBe(false);
  d.update("a.py", "print(2)\n");
  expect(d.isDirty("a.py")).toBe(true);
  expect(d.dirtyPaths()).toEqual(["a.py"]);
  d.markSaved("a.py", "print(2)\n");
  expect(d.isDirty("a.py")).toBe(false);
});

it("revenir au texte enregistré efface la pastille", () => {
  const d = new OpenDocuments();
  d.open("a.py", "x");
  d.update("a.py", "xy");
  d.update("a.py", "x");
  expect(d.isDirty("a.py")).toBe(false);
});

it("ignore les fichiers non ouverts et oublie les fichiers fermés", () => {
  const d = new OpenDocuments();
  d.update("b.py", "x");
  expect(d.isOpen("b.py")).toBe(false);
  d.open("a.py", "x");
  d.update("a.py", "y");
  d.close("a.py");
  expect(d.dirtyPaths()).toEqual([]);
});
