// Rend les icônes en verre de scene.html en PNG transparents (Chromium sans écran, WebGL logiciel).
//
//   node scripts/icones-3d/rendre.mjs [dossier de sortie] [objet…]
//   python3 scripts/icones-3d/webp.py <dossier des PNG> contenus/academy_content/static/icones
//
// three.js et Playwright viennent de lab-ui (cd lab-ui && npm ci). Sans objet nommé : tous.
import { createServer } from 'node:http';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, extname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ICI = dirname(fileURLToPath(import.meta.url));
const LAB_UI = resolve(ICI, '../../lab-ui/node_modules');
const { chromium } = await import(join(LAB_UI, 'playwright/index.mjs'));
const OBJETS = ['robot', 'bras', 'conteneur', 'bouclier', 'terminal', 'ampoule', 'medaille', 'noeuds'];
const TYPES = { '.html': 'text/html', '.js': 'text/javascript' };

const sortie = resolve(process.argv[2] || 'icones-png');
const objets = process.argv.length > 3 ? process.argv.slice(3) : OBJETS;
mkdirSync(sortie, { recursive: true });

// la scène et three.js servis en local : les modules ES ne se chargent pas depuis file://
const serveur = createServer((req, res) => {
  const chemin = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  const fichier = chemin.startsWith('/three/') ? join(LAB_UI, chemin) : join(ICI, 'scene.html');
  try {
    res.writeHead(200, { 'Content-Type': TYPES[extname(fichier)] || 'application/octet-stream' });
    res.end(readFileSync(fichier));
  } catch {
    res.writeHead(404).end();
  }
}).listen(0, '127.0.0.1');
await new Promise((ok) => serveur.once('listening', ok));
const base = `http://127.0.0.1:${serveur.address().port}/`;

const navigateur = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
const page = await navigateur.newPage();
page.on('pageerror', (e) => console.error(e.message));
for (const objet of objets) {
  await page.goto(`${base}scene.html?objet=${objet}&taille=640`);
  await page.waitForFunction(() => window.rendu, null, { timeout: 120000 });
  const donnees = await page.evaluate(() => window.rendu);
  writeFileSync(join(sortie, `${objet}.png`), Buffer.from(donnees.split(',')[1], 'base64'));
  console.log('rendu', objet);
}
await navigateur.close();
serveur.close();
