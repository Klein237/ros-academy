type Child = Node | string | null | undefined | false;

interface Props {
  class?: string;
  text?: string;
  title?: string;
  type?: string;
  dataset?: Record<string, string>;
  attrs?: Record<string, string>;
  on?: Partial<{ [K in keyof HTMLElementEventMap]: (ev: HTMLElementEventMap[K]) => void }>;
}

/** Petit utilitaire de création d'éléments (le texte passe toujours par textContent). */
export function h<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  props: Props = {},
  ...children: Child[]
): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag);
  if (props.class) el.className = props.class;
  if (props.text !== undefined) el.textContent = props.text;
  if (props.title) el.title = props.title;
  if (props.type) el.setAttribute("type", props.type);
  for (const [k, v] of Object.entries(props.dataset ?? {})) el.dataset[k] = v;
  for (const [k, v] of Object.entries(props.attrs ?? {})) el.setAttribute(k, v);
  for (const [event, handler] of Object.entries(props.on ?? {})) {
    el.addEventListener(event, handler as EventListener);
  }
  for (const child of children) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child);
  }
  return el;
}

export function button(label: string, onClick: () => void, props: Props = {}): HTMLButtonElement {
  return h("button", { type: "button", ...props, text: label, on: { click: () => onClick() } });
}

/** Message court en bas de l'écran. */
export function toast(message: string, kind: "info" | "error" = "info"): void {
  const el = h("div", { class: `toast toast-${kind}`, text: message, attrs: { role: "status" } });
  document.body.append(el);
  setTimeout(() => el.remove(), kind === "error" ? 6000 : 2500);
}
