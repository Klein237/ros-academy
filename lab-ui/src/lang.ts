/** Langage Monaco selon le nom de fichier. */
const BY_NAME: Record<string, string> = {
  "CMakeLists.txt": "cmake",
  "package.xml": "xml",
  "setup.cfg": "ini",
  "Makefile": "shell",
};

const BY_EXTENSION: Record<string, string> = {
  py: "python",
  cpp: "cpp",
  cc: "cpp",
  cxx: "cpp",
  hpp: "cpp",
  h: "cpp",
  hh: "cpp",
  c: "cpp",
  xml: "xml",
  urdf: "xml",
  xacro: "xml",
  sdf: "xml",
  launch: "xml",
  yaml: "yaml",
  yml: "yaml",
  sh: "shell",
  bash: "shell",
  md: "markdown",
  cfg: "ini",
  ini: "ini",
  msg: "plaintext",
  srv: "plaintext",
  action: "plaintext",
};

export function languageFor(path: string): string {
  const name = path.split("/").pop() ?? "";
  if (BY_NAME[name]) return BY_NAME[name];
  const dot = name.lastIndexOf(".");
  if (dot <= 0) return "plaintext";
  return BY_EXTENSION[name.slice(dot + 1).toLowerCase()] ?? "plaintext";
}
