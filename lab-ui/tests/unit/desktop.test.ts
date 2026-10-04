// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DesktopPanel, type RfbLike } from "../../src/ui/desktop";

class FakeRfb implements RfbLike {
  static all: FakeRfb[] = [];
  scaleViewport = false;
  resizeRequests = 0; // chaque « resizeSession = true » redemande la taille du bureau (noVNC)
  private resize = false;
  disconnected = false;
  focused = 0;
  private listeners: Record<string, ((ev: Event) => void)[]> = {};

  constructor(
    readonly target: HTMLElement,
    readonly url: string,
  ) {
    FakeRfb.all.push(this);
  }

  get resizeSession(): boolean {
    return this.resize;
  }

  set resizeSession(v: boolean) {
    this.resize = v;
    if (v) this.resizeRequests += 1;
  }

  addEventListener(type: string, listener: (ev: Event) => void): void {
    (this.listeners[type] ??= []).push(listener);
  }

  emit(type: "connect" | "disconnect"): void {
    for (const l of this.listeners[type] ?? []) l(new Event(type));
  }

  disconnect(): void {
    this.disconnected = true;
  }

  focus(): void {
    this.focused += 1;
  }
}

const last = () => FakeRfb.all[FakeRfb.all.length - 1]!;

function panel(url = async () => "wss://lab/user/u1/bureau/?token=t") {
  return new DesktopPanel({ url, rfb: (target, u) => new FakeRfb(target, u) });
}

beforeEach(() => {
  FakeRfb.all = [];
  vi.useFakeTimers();
  vi.spyOn(console, "warn").mockImplementation(() => {});
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("DesktopPanel", () => {
  it("se connecte à la première ouverture seulement, écran mis à l'échelle et redimensionné", async () => {
    const p = panel();
    expect(p.el.hidden).toBe(true);
    expect(FakeRfb.all).toHaveLength(0); // rien tant que le bureau n'est pas ouvert
    p.show();
    await vi.advanceTimersByTimeAsync(0);
    expect(p.el.hidden).toBe(false);
    expect(FakeRfb.all).toHaveLength(1);
    expect(last().url).toBe("wss://lab/user/u1/bureau/?token=t");
    expect(last().scaleViewport && last().resizeSession).toBe(true);
    expect(p.status).toBe("connexion");
    last().emit("connect");
    expect(p.status).toBe("connecte");
    p.hide();
    p.show(); // la même connexion est gardée
    expect(FakeRfb.all).toHaveLength(1);
    expect(last().focused).toBe(1);
  });

  it("redemande la taille du bureau peu après la connexion (demande perdue par noVNC)", async () => {
    const p = panel();
    p.show();
    await vi.advanceTimersByTimeAsync(0);
    const rfb = last();
    expect(rfb.resizeRequests).toBe(1);
    rfb.emit("connect");
    await vi.advanceTimersByTimeAsync(600);
    expect(rfb.resizeRequests).toBe(2);
    await vi.advanceTimersByTimeAsync(5000);
    expect(rfb.resizeRequests).toBe(4); // 0,6 s, 2 s et 5 s après la connexion
  });

  it("se reconnecte avec un délai croissant tant que le bureau est voulu", async () => {
    const p = panel();
    p.show();
    await vi.advanceTimersByTimeAsync(0);
    last().emit("disconnect"); // le bureau démarre encore, par exemple
    expect(p.status).toBe("reconnexion");
    await vi.advanceTimersByTimeAsync(999);
    expect(FakeRfb.all).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(FakeRfb.all).toHaveLength(2);
    last().emit("disconnect");
    await vi.advanceTimersByTimeAsync(1999);
    expect(FakeRfb.all).toHaveLength(2);
    await vi.advanceTimersByTimeAsync(1);
    expect(FakeRfb.all).toHaveLength(3);
    last().emit("connect");
    expect(p.status).toBe("connecte");
  });

  it("nouvel essai si l'adresse ne peut pas être obtenue (jeton)", async () => {
    let fail = true;
    const p = panel(async () => {
      if (fail) throw new Error("jeton");
      return "wss://ok";
    });
    p.show();
    await vi.advanceTimersByTimeAsync(0);
    expect(FakeRfb.all).toHaveLength(0);
    expect(p.status).toBe("reconnexion");
    fail = false;
    await vi.advanceTimersByTimeAsync(1000);
    expect(last().url).toBe("wss://ok");
  });

  it("dispose ferme la connexion et arrête les nouveaux essais", async () => {
    const p = panel();
    p.show();
    await vi.advanceTimersByTimeAsync(0);
    const first = last();
    first.emit("disconnect");
    p.dispose();
    await vi.advanceTimersByTimeAsync(60_000);
    expect(FakeRfb.all).toHaveLength(1);
    expect(p.status).toBe("arrete");
    p.show();
    await vi.advanceTimersByTimeAsync(0);
    last().emit("connect");
    p.dispose();
    expect(last().disconnected).toBe(true);
  });

  it("Reconnecter remplace la connexion en cours", async () => {
    const p = panel();
    p.show();
    await vi.advanceTimersByTimeAsync(0);
    const first = last();
    p.reconnect();
    await vi.advanceTimersByTimeAsync(0);
    expect(first.disconnected).toBe(true);
    expect(FakeRfb.all).toHaveLength(2);
    first.emit("disconnect"); // l'ancienne connexion ne déclenche plus rien
    await vi.advanceTimersByTimeAsync(20_000);
    expect(FakeRfb.all).toHaveLength(2);
  });

  it("fenêtre séparée : lâche la connexion, puis la reprend quand on ramène le bureau", async () => {
    let reattach = 0;
    const p = new DesktopPanel({
      url: async () => "wss://ok",
      rfb: (target, u) => new FakeRfb(target, u),
      onDetach: () => {},
      onReattach: () => (reattach += 1),
    });
    p.show();
    await vi.advanceTimersByTimeAsync(0);
    const first = last();
    first.emit("connect");
    p.setDetached(true);
    expect(first.disconnected).toBe(true);
    expect(p.status).toBe("separe");
    first.emit("disconnect"); // pas de nouvel essai pendant que l'autre fenêtre a le bureau
    p.hide();
    p.show();
    await vi.advanceTimersByTimeAsync(30_000);
    expect(FakeRfb.all).toHaveLength(1);
    const back = [...p.el.querySelectorAll("button")].find((b) => b.textContent === "Ramener ici")!;
    back.click();
    expect(reattach).toBe(1);
    p.setDetached(false);
    await vi.advanceTimersByTimeAsync(0);
    expect(FakeRfb.all).toHaveLength(2);
    expect(p.status).toBe("connexion");
  });

  it("détaché pendant l'attente du jeton : aucune connexion ouverte", async () => {
    let release: (u: string) => void = () => {};
    const p = new DesktopPanel({
      url: () => new Promise<string>((res) => (release = res)),
      rfb: (target, u) => new FakeRfb(target, u),
    });
    p.show();
    await vi.advanceTimersByTimeAsync(0);
    p.setDetached(true);
    release("wss://tard");
    await vi.advanceTimersByTimeAsync(0);
    expect(FakeRfb.all).toHaveLength(0);
  });

  it("boutons Agrandir et Fenêtre séparée seulement quand la page les gère", () => {
    const labels = (p: DesktopPanel) => [...p.el.querySelectorAll("button")].map((b) => b.textContent);
    expect(labels(panel())).not.toContain("Agrandir");
    let maximized = 0;
    const p = new DesktopPanel({
      url: async () => "wss://ok",
      rfb: (target, u) => new FakeRfb(target, u),
      onMaximize: () => (maximized += 1),
      onDetach: () => {},
    });
    expect(labels(p)).toEqual(expect.arrayContaining(["Agrandir", "Fenêtre séparée"]));
    [...p.el.querySelectorAll("button")].find((b) => b.textContent === "Agrandir")!.click();
    expect(maximized).toBe(1);
    p.setMaximized(true);
    expect(labels(p)).toContain("Réduire");
  });
});
