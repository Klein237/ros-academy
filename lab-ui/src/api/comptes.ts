/**
 * Service Comptes (même origine, cookie de session) : quota de minutes, file d'attente,
 * indices comptés, réussite de l'exercice et explication.
 */

export interface Me {
  nom: string;
  email: string;
  formule: string;
  hub: string;
  /** null : formule sans limite. */
  minutes_restantes: number | null;
  minutes_utilisees: number;
}

export interface QueueTicket {
  ticket: string;
  position: number;
  a_vous: boolean;
}

export interface ExerciseState {
  indices: number;
  reussi: boolean;
}

/** Pas de session Comptes : l'étudiant doit se reconnecter. */
export class NoAccount extends Error {}

export class ComptesError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

type FetchFn = (input: string, init?: RequestInit) => Promise<Response>;

export class ComptesClient {
  constructor(private readonly fetchFn: FetchFn = (input, init) => fetch(input, init)) {}

  private async call<T>(path: string, method = "GET"): Promise<T> {
    // POST / DELETE : le navigateur ajoute l'en-tête Origin, vérifié par Comptes
    const r = await this.fetchFn(`/api/comptes${path}`, { method, credentials: "same-origin", cache: "no-store" });
    if (r.status === 401) throw new NoAccount("session Comptes absente");
    if (!r.ok) throw new ComptesError(r.status, `${method} ${path} : ${r.status}`);
    return (await r.json()) as T;
  }

  me(): Promise<Me> {
    return this.call("/moi");
  }

  joinQueue(): Promise<QueueTicket> {
    return this.call("/file", "POST");
  }

  /** Battement : garde la place et renvoie la position à jour. */
  beat(ticket: string): Promise<QueueTicket> {
    return this.call(`/file/${encodeURIComponent(ticket)}`, "POST");
  }

  async leaveQueue(ticket: string): Promise<void> {
    await this.call(`/file/${encodeURIComponent(ticket)}`, "DELETE");
  }

  exercise(moduleId: string): Promise<ExerciseState> {
    return this.call(`/exercices/${encodeURIComponent(moduleId)}`);
  }

  /** L'indice n est compté (pénalité) avant d'être renvoyé ; un indice déjà vu ne coûte rien. */
  async hint(moduleId: string, n: number): Promise<string> {
    return (await this.call<{ html: string }>(`/exercices/${encodeURIComponent(moduleId)}/indices/${n}`, "POST")).html;
  }

  async reportSuccess(moduleId: string): Promise<void> {
    await this.call(`/exercices/${encodeURIComponent(moduleId)}/reussite`, "POST");
  }

  async explanation(moduleId: string): Promise<string> {
    return (await this.call<{ html: string }>(`/exercices/${encodeURIComponent(moduleId)}/explication`)).html;
  }
}

/** Page de reconnexion : Comptes ouvre une session si besoin, puis rouvre cette page du lab. */
export function reloginUrl(loc: { pathname: string; search: string } = location): string {
  return `/compte/lab?suite=${encodeURIComponent(loc.pathname + loc.search)}`;
}
