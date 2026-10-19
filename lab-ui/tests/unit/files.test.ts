// @vitest-environment jsdom
import { expect, it } from "vitest";
import type { ContentsClient, Entry } from "../../src/api/contents";
import { FileTree } from "../../src/ui/files";

/** Dossier personnel avec deux parcours. */
const TREE: Record<string, string[]> = {
  "": ["ws/"],
  ws: ["ros2-fondamentaux/", "bras-robotique/"],
  "ws/ros2-fondamentaux": ["05-noeud/"],
  "ws/bras-robotique": ["31-bras-urdf/", "31-bras-urdf-exercice/"],
  "ws/bras-robotique/31-bras-urdf": ["bras.urdf"],
  "ws/bras-robotique/31-bras-urdf-exercice": [],
};

function client(): ContentsClient {
  const list = async (dir: string): Promise<Entry[]> =>
    (TREE[dir] ?? []).map((n) => {
      const name = n.replace(/\/$/, "");
      return { name, path: dir ? `${dir}/${name}` : name, type: n.endsWith("/") ? "directory" : "file", size: null };
    });
  return { list } as unknown as ContentsClient;
}

const noms = (tree: FileTree) => [...tree.el.querySelectorAll(".tree-row .name")].map((e) => e.textContent);

it("dans un parcours, les autres parcours ne sont pas visibles", async () => {
  const tree = new FileTree({ client: client(), root: "ws/bras-robotique/31-bras-urdf", base: "ws/bras-robotique", onOpen: () => {} });
  await tree.load();
  expect(noms(tree)).toEqual(["31-bras-urdf", "bras.urdf", "31-bras-urdf-exercice"]);
  expect(tree.el.querySelector(".files-base")?.textContent).toBe("~/ws/bras-robotique");
  // un chemin hors du parcours n'est pas déplié
  await tree.reveal("ws/ros2-fondamentaux/05-noeud");
  expect(noms(tree)).not.toContain("05-noeud");
});

it("sans parcours : tout le dossier personnel, comme avant", async () => {
  const tree = new FileTree({ client: client(), root: "ws/ros2-fondamentaux", onOpen: () => {} });
  await tree.load();
  expect(noms(tree)).toEqual(["ws", "ros2-fondamentaux", "05-noeud", "bras-robotique"]);
  expect(tree.el.querySelector(".files-base")).toBeNull();
});
