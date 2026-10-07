/** API du cours (service Contenus, même origine, session de l'étudiant). Indices et explication : voir comptes.ts. */

export interface ModuleFile {
  path: string;
  content: string;
  executable?: boolean;
}

export interface ModuleInfo {
  id: string;
  titre: string;
  resume: string;
  duree: string;
}

export interface ExerciseInfo {
  enonce_html: string;
  files: ModuleFile[];
  indices: number;
}

import { NoAccount } from "./comptes";

export class ModuleHttpError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

type FetchFn = (input: string, init?: RequestInit) => Promise<Response>;

export class ModuleClient {
  constructor(
    readonly moduleId: string,
    private readonly fetchFn: FetchFn = (input, init) => fetch(input, init),
  ) {}

  private async get<T>(suffix: string): Promise<T> {
    const r = await this.fetchFn(`/api/contenus/modules/${encodeURIComponent(this.moduleId)}${suffix}`, {
      credentials: "same-origin", // le cours est réservé aux étudiants connectés (session de Comptes)
    });
    if (r.status === 401) throw new NoAccount("session de Comptes absente ou expirée");
    if (!r.ok) throw new ModuleHttpError(r.status, `module ${this.moduleId} : ${r.status}`);
    return (await r.json()) as T;
  }

  info(): Promise<ModuleInfo> {
    return this.get("");
  }

  async labFiles(): Promise<ModuleFile[]> {
    return (await this.get<{ files: ModuleFile[] }>("/lab")).files;
  }

  async courseFiles(): Promise<ModuleFile[]> {
    return (await this.get<{ files: ModuleFile[] }>("/cours-fichiers")).files;
  }

  /** null : module de cours, sans exercice (noté sur son QCM). */
  async exercise(): Promise<ExerciseInfo | null> {
    try {
      return await this.get<ExerciseInfo>("/exercice");
    } catch (e) {
      if (e instanceof ModuleHttpError && e.status === 404) return null;
      throw e;
    }
  }
}
