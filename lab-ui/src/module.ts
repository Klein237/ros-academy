/** Installer le module dans le conteneur de l'étudiant, sans jamais écraser son travail. */
import type { ContentsClient } from "./api/contents";
import type { ModuleClient, ModuleFile } from "./api/module";
import { joinPath, normalizePath } from "./paths";

type Contents = Pick<ContentsClient, "exists" | "mkdirp" | "writeFile" | "rename">;

export const labDir = (id: string) => `ws/${id}`;
export const exerciseDir = (id: string) => `ws/${id}-exercice`;
export const academyDir = (id: string) => `.academy/${id}`;

/** Copie lab/ dans ~/ws/<id> seulement si ce dossier n'existe pas encore. */
export async function installLab(contents: Contents, id: string, files: ModuleFile[]): Promise<"installe" | "existant"> {
  const dir = labDir(id);
  if (await contents.exists(dir)) return "existant";
  await contents.mkdirp(dir);
  for (const f of files) await contents.writeFile(joinPath(dir, f.path), f.content);
  return "installe";
}

/**
 * « Ouvrir dans le lab » : si le fichier demandé n'existe pas et que le cours le fournit,
 * il est créé avec le contenu du cours. Un fichier existant n'est jamais modifié.
 */
export async function ensureCourseFile(
  contents: Contents,
  id: string,
  path: string,
  courseFiles: ModuleFile[],
): Promise<boolean> {
  const target = normalizePath(path);
  const prefix = `${labDir(id)}/`;
  if (!target.startsWith(prefix) || (await contents.exists(target))) return false;
  const file = courseFiles.find((f) => normalizePath(f.path) === target.slice(prefix.length));
  if (!file) return false;
  await contents.writeFile(target, file.content);
  return true;
}

/** Copie les fichiers de l'exercice (scripts, départ) dans ~/.academy/<id>, à chaque démarrage. */
export async function installExerciseFiles(contents: Contents, id: string, files: ModuleFile[]): Promise<void> {
  for (const f of files) await contents.writeFile(joinPath(academyDir(id), f.path), f.content);
}

/** Réinitialiser : l'ancien dossier est renommé (rien n'est supprimé), puis lab/ est réinstallé. */
export async function resetLab(contents: Contents, id: string, files: ModuleFile[], now = new Date()): Promise<string> {
  const stamp = now.toISOString().slice(0, 19).replace(/[-:]/g, "").replace("T", "-");
  const backup = `${labDir(id)}.ancien-${stamp}`;
  if (await contents.exists(labDir(id))) await contents.rename(labDir(id), backup);
  await installLab(contents, id, files);
  return backup;
}

/** Commande tapée dans un terminal pour lancer setup.sh ou check.sh. */
export function scriptCommand(id: string, script: "setup.sh" | "check.sh", nonce: string): string {
  const env = `EXERCICE="$HOME/${academyDir(id)}" WS="$HOME/${exerciseDir(id)}"`;
  // Marqueur de fin masqué (séquence « invisible ») ; les guillemets vides empêchent
  // l'écho de la commande tapée de contenir le marqueur.
  return `clear; env ${env} bash "$HOME/${academyDir(id)}/${script}"; printf '\\033[8m__ACADEMY_'"${nonce}"'_%s__\\033[0m\\n' "$?"`;
}

/** Code de sortie lu dans la sortie du terminal, ou null si le script n'a pas fini. */
export function findExitCode(output: string, nonce: string): number | null {
  const m = new RegExp(`__ACADEMY_${nonce}_(\\d+)__`).exec(output);
  return m ? Number(m[1]) : null;
}

/** Texte lisible de la sortie d'un script (sans séquences ANSI ni marqueur). */
export function cleanOutput(output: string, nonce: string): string {
  return output
    .replace(/\x1b\[[0-9;?]*[ -/]*[@-~]/g, "")
    .replace(/\x1b\][^\x07]*\x07/g, "")
    .replace(/\r/g, "")
    .split("\n")
    .filter((l) => !l.includes(`__ACADEMY_`) && !l.includes(nonce))
    .filter((l) => !/^[\w.-]+@[\w.-]+:.*[$#] ?$/.test(l)) // invite du shell
    .join("\n")
    .trim();
}

export type ModuleClientLike = Pick<ModuleClient, "labFiles" | "courseFiles" | "exercise" | "hint" | "explanation">;
