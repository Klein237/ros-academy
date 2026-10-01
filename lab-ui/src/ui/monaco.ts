/** Chargé à la demande : Monaco pèse plusieurs Mo, le terminal ne doit pas l'attendre. */
import * as monaco from "monaco-editor/editor/editor.api.js";
import EditorWorker from "monaco-editor/editor/editor.worker.js?worker";
import "monaco-editor/languages/definitions/cpp/register.js";
import "monaco-editor/languages/definitions/ini/register.js";
import "monaco-editor/languages/definitions/markdown/register.js";
import "monaco-editor/languages/definitions/python/register.js";
import "monaco-editor/languages/definitions/shell/register.js";
import "monaco-editor/languages/definitions/xml/register.js";
import "monaco-editor/languages/definitions/yaml/register.js";

(self as unknown as { MonacoEnvironment: unknown }).MonacoEnvironment = {
  getWorker: () => new EditorWorker(),
};

// CMakeLists.txt : coloration minimale (Monaco n'a pas de CMake).
monaco.languages.register({ id: "cmake", filenames: ["CMakeLists.txt"], extensions: [".cmake"] });
monaco.languages.setMonarchTokensProvider("cmake", {
  ignoreCase: true,
  tokenizer: {
    root: [
      [/#.*$/, "comment"],
      [/"/, "string", "@string"],
      [/\$\{[^}]*\}/, "variable"],
      [/\b[a-z_][a-z0-9_]*(?=\s*\()/, "keyword"],
      [/\b[A-Z_][A-Z0-9_]+\b/, "type"],
    ],
    string: [
      [/\$\{[^}]*\}/, "variable"],
      [/[^"$]+/, "string"],
      [/"/, "string", "@pop"],
      [/./, "string"],
    ],
  },
});
monaco.languages.setLanguageConfiguration("cmake", {
  comments: { lineComment: "#" },
  brackets: [["(", ")"]],
  autoClosingPairs: [
    { open: "(", close: ")" },
    { open: '"', close: '"' },
  ],
});

export { monaco };
