/** API publique du service Contenus (même origine, sans jeton). */

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

type FetchFn = (input: string, init?: RequestInit) => Promise<Response>;

export class ModuleClient {
  constructor(
    readonly moduleId: string,
    private readonly fetchFn: FetchFn = (input, init) => fetch(input, init),
  ) {}

  private async get<T>(suffix: string): Promise<T> {
    const r = await this.fetchFn(`/api/contenus/modules/${encodeURIComponent(this.moduleId)}${suffix}`, {
      credentials: "omit",
    });
    if (!r.ok) throw new Error(`module ${this.moduleId} : ${r.status}`);
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

  exercise(): Promise<ExerciseInfo> {
    return this.get("/exercice");
  }

  async hint(n: number): Promise<string> {
    return (await this.get<{ html: string }>(`/indices/${n}`)).html;
  }

  async explanation(): Promise<string> {
    return (await this.get<{ html: string }>("/explication")).html;
  }
}
