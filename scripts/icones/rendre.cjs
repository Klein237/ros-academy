// PNG et favicon.ico depuis les SVG de generer.py (Playwright de lab-ui, Python + Pillow pour l'.ico).
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const { chromium } = require(path.join(__dirname, "../../lab-ui/node_modules/playwright"));
const SORTIE = path.join(__dirname, "../../contenus/academy_content/static/icones");
const enc = (f) => "data:image/svg+xml;base64," + fs.readFileSync(f).toString("base64");
const rendus = [
  [path.join(SORTIE, "favicon.svg"), 16, "favicon-16.png"], [path.join(SORTIE, "favicon.svg"), 32, "favicon-32.png"],
  [path.join(__dirname, "icone-carree.svg"), 180, "apple-touch-icon.png"],
  [path.join(__dirname, "icone-complete.svg"), 192, "icone-192.png"], [path.join(__dirname, "icone-complete.svg"), 512, "icone-512.png"],
];
(async () => {
  const b = await chromium.launch();
  for (const [src, t, nom] of rendus) {
    const p = await b.newPage({ viewport: { width: t, height: t } });
    await p.setContent(`<body style="margin:0"><img src="${enc(src)}" style="width:${t}px;height:${t}px;display:block"></body>`);
    await p.screenshot({ path: path.join(SORTIE, nom), omitBackground: true });
    await p.close();
  }
  await b.close();
  // favicon.ico (16 et 32 px) pour les navigateurs qui demandent /favicon.ico ; les PNG intermédiaires partent
  execFileSync("python3", ["-c", `from PIL import Image; d='${SORTIE}/'
Image.open(d+'favicon-32.png').save(d+'favicon.ico', sizes=[(16,16),(32,32)], append_images=[Image.open(d+'favicon-16.png')])`]);
  for (const f of ["favicon-16.png", "favicon-32.png"]) fs.rmSync(path.join(SORTIE, f));
  console.log("apple-touch-icon.png, icone-192.png, icone-512.png, favicon.ico");
})();
