/** Types minimaux de noVNC (le paquet n'en fournit pas) ; voir docs/API.md du paquet. */
declare module "@novnc/novnc" {
  export default class RFB extends EventTarget {
    constructor(target: HTMLElement, url: string, options?: { shared?: boolean; credentials?: { password?: string } });
    scaleViewport: boolean;
    resizeSession: boolean;
    disconnect(): void;
    focus(): void;
  }
}
