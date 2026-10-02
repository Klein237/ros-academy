/** API fichiers de jupyter-server (/user/<nom>/api/contents). */
import { MAX_TEXT_FILE_BYTES } from "../config";
import { encodePath, normalizePath } from "../paths";
import { HttpError, type HubClient } from "./hub";

export interface Entry {
  name: string;
  path: string;
  type: "directory" | "file" | "notebook";
  size: number | null;
}

export class FileTooLarge extends Error {}
export class BinaryFile extends Error {}
export class NotFound extends Error {}

type HubLike = Pick<HubClient, "request" | "serverPath">;

export class ContentsClient {
  constructor(private readonly hub: HubLike) {}

  private url(path: string, query = ""): string {
    return this.hub.serverPath(`api/contents/${encodePath(path)}${query}`);
  }

  private async call(path: string, init: RequestInit = {}, query = ""): Promise<Response> {
    const r = await this.hub.request(this.url(path, query), init);
    if (r.status === 404) throw new NotFound(normalizePath(path));
    if (!r.ok) throw new HttpError(r.status, `${init.method ?? "GET"} ${path} : ${r.status}`);
    return r;
  }

  async list(dir: string): Promise<Entry[]> {
    const r = await this.call(dir, {}, "?type=directory&content=1");
    const body = (await r.json()) as { content: Entry[] };
    return body.content
      .map(({ name, path, type, size }) => ({ name, path, type, size }))
      .sort((a, b) =>
        a.type === b.type ? a.name.localeCompare(b.name, "fr") : a.type === "directory" ? -1 : 1,
      );
  }

  async exists(path: string): Promise<boolean> {
    try {
      await this.call(path, {}, "?content=0");
      return true;
    } catch (e) {
      if (e instanceof NotFound) return false;
      throw e;
    }
  }

  /** Contenu texte ; refuse les fichiers trop gros ou binaires. */
  async read(path: string): Promise<string> {
    const meta = (await (await this.call(path, {}, "?content=0")).json()) as Entry;
    if (meta.type === "directory") throw new HttpError(400, `${path} est un dossier`);
    if ((meta.size ?? 0) > MAX_TEXT_FILE_BYTES) throw new FileTooLarge(path);
    let r: Response;
    try {
      r = await this.call(path, {}, "?type=file&format=text&content=1");
    } catch (e) {
      // jupyter-server répond 400 quand le fichier n'est pas de l'UTF-8
      if (e instanceof HttpError && e.status === 400) throw new BinaryFile(path);
      throw e;
    }
    const body = (await r.json()) as { content: string; format: string };
    if (body.format !== "text") throw new BinaryFile(path);
    return body.content;
  }

  async save(path: string, content: string): Promise<void> {
    await this.call(path, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type: "file", format: "text", content }),
    });
  }

  async createFile(path: string): Promise<void> {
    if (await this.exists(path)) throw new HttpError(409, `${path} existe déjà`);
    await this.save(path, "");
  }

  async createDirectory(path: string): Promise<void> {
    if (await this.exists(path)) throw new HttpError(409, `${path} existe déjà`);
    await this.call(path, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type: "directory" }),
    });
  }

  /** Crée le dossier et ses parents manquants. */
  async mkdirp(path: string): Promise<void> {
    let current = "";
    for (const part of normalizePath(path).split("/").filter(Boolean)) {
      current = current ? `${current}/${part}` : part;
      if (!(await this.exists(current))) await this.createDirectory(current);
    }
  }

  /** Écrit un fichier texte, en créant ses dossiers parents. */
  async writeFile(path: string, content: string): Promise<void> {
    const parent = normalizePath(path).split("/").slice(0, -1).join("/");
    if (parent) await this.mkdirp(parent);
    await this.save(path, content);
  }

  async rename(from: string, to: string): Promise<void> {
    await this.call(from, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: normalizePath(to) }),
    });
  }

  async remove(path: string): Promise<void> {
    await this.call(path, { method: "DELETE" });
  }
}
