import { expect, it, vi } from "vitest";
import { BinaryFile, ContentsClient, FileTooLarge, NotFound } from "../../src/api/contents";
import { json } from "./fakes";

function client(...responses: Response[]) {
  const request = vi.fn(async () => responses.shift() ?? json(500));
  const hub = { request, serverPath: (p: string) => `/user/alice/${p}` };
  return { c: new ContentsClient(hub as never), request };
}

it("liste un dossier : dossiers d'abord, puis ordre alphabétique", async () => {
  const { c, request } = client(
    json(200, {
      content: [
        { name: "b.py", path: "ws/b.py", type: "file", size: 1 },
        { name: "src", path: "ws/src", type: "directory", size: null },
        { name: "a.py", path: "ws/a.py", type: "file", size: 1 },
      ],
    }),
  );
  expect((await c.list("ws")).map((e) => e.name)).toEqual(["src", "a.py", "b.py"]);
  expect((request.mock.calls[0] as unknown as [string])[0]).toBe("/user/alice/api/contents/ws?type=directory&content=1");
});

it("refuse d'ouvrir un fichier de plus de 1 Mo", async () => {
  const { c } = client(json(200, { type: "file", size: 2_000_000 }));
  await expect(c.read("ws/big.bag")).rejects.toBeInstanceOf(FileTooLarge);
});

it("refuse d'ouvrir un fichier binaire", async () => {
  const { c } = client(json(200, { type: "file", size: 10 }), json(400));
  await expect(c.read("ws/a.so")).rejects.toBeInstanceOf(BinaryFile);
});

it("lit un fichier texte", async () => {
  const { c } = client(json(200, { type: "file", size: 9 }), json(200, { content: "print(1)\n", format: "text" }));
  expect(await c.read("ws/a.py")).toBe("print(1)\n");
});

it("fichier absent → NotFound", async () => {
  const { c } = client(json(404));
  await expect(c.read("ws/x.py")).rejects.toBeInstanceOf(NotFound);
});

it("enregistre en texte avec PUT", async () => {
  const { c, request } = client(json(200));
  await c.save("ws/mon nœud.py", "x");
  const [url, init] = request.mock.calls[0] as unknown as [string, RequestInit];
  expect(url).toBe("/user/alice/api/contents/ws/mon%20n%C5%93ud.py");
  expect(init.method).toBe("PUT");
  expect(JSON.parse(String(init.body))).toEqual({ type: "file", format: "text", content: "x" });
});

it("ne remplace pas un fichier existant à la création", async () => {
  const { c, request } = client(json(200, { type: "file", size: 1 }));
  await expect(c.createFile("ws/a.py")).rejects.toThrow(/existe déjà/);
  expect(request).toHaveBeenCalledTimes(1);
});
