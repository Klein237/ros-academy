/** Installer le module dans le conteneur de l'étudiant, sans jamais écraser son travail. */
import type { ContentsClient } from "./api/contents";
import { HttpError } from "./api/hub";
import type { ModuleClient, ModuleFile } from "./api/module";
import { sleep } from "./backoff";
import { joinPath, normalizePath } from "./paths";

type Contents = Pick<ContentsClient, "exists" | "mkdirp" | "writeFile" | "rename">;

export const labDir = (id: string) => `ws/${id}`;
export const exerciseDir = (id: string) => `ws/${id}-exercice`;
export const academyDir = (id: string) => `.academy/${id}`;

/**
 * Copie lab/ dans ~/ws/<id> seulement si ce dossier n'existe pas encore.
 * `reprise` : le dossier a été créé par une tentative précédente interrompue ;
 * on complète alors les fichiers absents, sans réécrire ceux déjà présents.
 */
export async function installLab(
  contents: Contents,
  id: string,
  files: ModuleFile[],
  reprise = false,
): Promise<"installe" | "existant"> {
  const dir = labDir(id);
  if (!reprise && (await contents.exists(dir))) return "existant";
  await contents.mkdirp(dir);
  for (const f of files) {
    const path = joinPath(dir, f.path);
    if (reprise && (await contents.exists(path))) continue;
    await contents.writeFile(path, f.content);
  }
  return "installe";
}

/** Erreur passagère (réseau, serveur qui démarre) : la requête peut être retentée. */
export function isTransient(e: unknown): boolean {
  if (e instanceof HttpError) return e.status === 0 || e.status >= 500;
  return e instanceof TypeError; // fetch : réseau coupé
}

/**
 * installLab avec nouvelles tentatives sur erreur passagère (juste après le démarrage du conteneur).
 * Si ~/ws/<id> n'existait pas au départ, tout ce qu'il contient vient de nos tentatives :
 * une nouvelle tentative complète l'installation au lieu de la croire terminée.
 */
export async function installLabWithRetry(
  contents: Contents,
  id: string,
  load: () => Promise<ModuleFile[]>,
  { delays = [500, 1000, 2000, 4000], wait = sleep }: { delays?: number[]; wait?: (ms: number) => Promise<void> } = {},
): Promise<"installe" | "existant"> {
  let neuf: boolean | null = null;
  for (let attempt = 0; ; attempt++) {
    try {
      if (neuf === null) neuf = !(await contents.exists(labDir(id)));
      return await installLab(contents, id, await load(), neuf);
    } catch (e) {
      if (attempt >= delays.length || !isTransient(e)) throw e;
      console.warn(`Installation du module ${id}, tentative ${attempt + 1} échouée :`, e);
      await wait(delays[attempt]);
    }
  }
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

/** Sauvegardes de « Réinitialiser » : dossier caché, pour ne pas encombrer ~/ws. */
export const BACKUP_DIR = "ws/.anciens";

/** Réinitialiser : l'ancien dossier est mis de côté (rien n'est supprimé), puis lab/ est réinstallé. */
export async function resetLab(contents: Contents, id: string, files: ModuleFile[], now = new Date()): Promise<string> {
  const stamp = now.toISOString().slice(0, 19).replace(/[-:]/g, "").replace("T", "-");
  const backup = `${BACKUP_DIR}/${id}-${stamp}`;
  if (await contents.exists(labDir(id))) {
    await contents.mkdirp(BACKUP_DIR);
    await contents.rename(labDir(id), backup);
  }
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

export type ModuleClientLike = Pick<ModuleClient, "labFiles" | "courseFiles" | "exercise">;
