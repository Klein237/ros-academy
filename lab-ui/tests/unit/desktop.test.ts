// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DesktopPanel, type RfbLike } from "../../src/ui/desktop";

class FakeRfb implements RfbLike {
  static all: FakeRfb[] = [];
  scaleViewport = false;
  resizeSession = false;
  disconnected = false;
  focused = 0;
  private listeners: Record<string, ((ev: Event) => void)[]> = {};

  constructor(
    readonly target: HTMLElement,
    readonly url: string,
  ) {
    FakeRfb.all.push(this);
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
});
