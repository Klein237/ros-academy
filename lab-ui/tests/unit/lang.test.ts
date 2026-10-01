import { expect, it } from "vitest";
import { languageFor } from "../../src/lang";

it.each([
  ["ws/src/pkg/pkg/talker.py", "python"],
  ["ws/src/pkg/launch/robot.launch.py", "python"],
  ["ws/src/pkg/src/node.cpp", "cpp"],
  ["ws/src/pkg/include/pkg/node.hpp", "cpp"],
  ["ws/src/pkg/CMakeLists.txt", "cmake"],
  ["ws/src/pkg/package.xml", "xml"],
  ["ws/src/pkg/urdf/robot.urdf.xacro", "xml"],
  ["ws/src/pkg/config/params.YAML", "yaml"],
  ["ws/src/pkg/setup.cfg", "ini"],
  ["build.sh", "shell"],
  ["README.md", "markdown"],
  [".bashrc", "plaintext"],
  ["notes", "plaintext"],
])("%s → %s", (path, lang) => {
  expect(languageFor(path)).toBe(lang);
});
