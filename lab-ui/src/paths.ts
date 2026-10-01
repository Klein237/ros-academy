/** Chemins relatifs à /home/etudiant, tels que les attend l'API jupyter-server. */

export class PathError extends Error {}

export function normalizePath(path: string): string {
  const parts: string[] = [];
  for (const part of path.replace(/^~(?=\/|$)/, "").split("/")) {
    if (part === "" || part === ".") continue;
    if (part === "..") throw new PathError(`chemin interdit : ${path}`);
    parts.push(part);
  }
  return parts.join("/");
}

export function joinPath(...parts: string[]): string {
  return normalizePath(parts.filter(Boolean).join("/"));
}

export function parentOf(path: string): string {
  const parts = normalizePath(path).split("/");
  parts.pop();
  return parts.join("/");
}

export function baseName(path: string): string {
  const parts = normalizePath(path).split("/");
  return parts[parts.length - 1] ?? "";
}

/** Encode chaque segment pour une URL d'API (espaces, accents, #, ?). */
export function encodePath(path: string): string {
  return normalizePath(path).split("/").map(encodeURIComponent).join("/");
}

/** Nom saisi par l'étudiant pour un nouveau fichier ou dossier. */
export function isValidName(name: string): boolean {
  return name.length > 0 && name.length <= 255 && !/[/\\\0]/.test(name) && name !== "." && name !== "..";
}
