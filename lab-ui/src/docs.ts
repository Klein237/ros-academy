/** Fichiers ouverts : texte enregistré et texte courant, pour la pastille « non enregistré ». */
export class OpenDocuments {
  private saved = new Map<string, string>();
  private current = new Map<string, string>();

  open(path: string, text: string): void {
    this.saved.set(path, text);
    this.current.set(path, text);
  }

  update(path: string, text: string): void {
    if (this.saved.has(path)) this.current.set(path, text);
  }

  markSaved(path: string, text: string): void {
    this.saved.set(path, text);
    this.current.set(path, text);
  }

  close(path: string): void {
    this.saved.delete(path);
    this.current.delete(path);
  }

  isOpen(path: string): boolean {
    return this.saved.has(path);
  }

  isDirty(path: string): boolean {
    return this.saved.has(path) && this.saved.get(path) !== this.current.get(path);
  }

  dirtyPaths(): string[] {
    return [...this.saved.keys()].filter((p) => this.isDirty(p));
  }

  paths(): string[] {
    return [...this.saved.keys()];
  }
}
