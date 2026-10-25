// Rend les clips 3D de l'accueil (scene.html) image par image, puis les encode en WebM et MP4.
//
//   node scripts/clips-3d/rendre.mjs [dossier de sortie] [scène…]
//
// Scènes : patrouille (robot du module 11 dans sa salle, laser calculé contre les murs),
// dessus (la même salle vue d'en haut, façon RViz), bras (bras des modules 30 à 33).
// Boucle parfaite de 12 s à 24 images/s, quelle que soit la vitesse de la machine.
// three.js, urdf-loader et Playwright viennent de lab-ui (cd lab-ui && npm ci) ; ffmpeg doit être installé.
// Les URDF de urdf/ sont générés par xacro depuis les cours (à refaire si leurs modèles changent) :
//   xacro content/modules/11-gazebo/…/my_robot.urdf.xacro > urdf/robot-mobile.urdf  (départ + solution de l'exercice)
//   xacro content/modules/33-cinematique-inverse/lab/src/bras_description/urdf/bras.urdf.xacro > urdf/bras.urdf
// Puis : cp <sortie>/{patrouille,bras}.{webm,mp4,webp} contenus/academy_content/static/videos/
import { execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, extname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ICI = dirname(fileURLToPath(import.meta.url));
const LAB_UI = resolve(ICI, '../../lab-ui/node_modules');
const { chromium } = await import(join(LAB_UI, 'playwright/index.mjs'));
const SCENES = ['patrouille', 'dessus', 'bras'];
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.urdf': 'application/xml' };
const PERIODE = 12, IMAGES_PAR_S = 24;

const sortie = resolve(process.argv[2] || 'clips-3d');
const scenes = process.argv.length > 3 ? process.argv.slice(3) : SCENES;
mkdirSync(sortie, { recursive: true });

// la scène, three.js et urdf-loader servis en local : les modules ES ne se chargent pas depuis file://
const serveur = createServer((req, res) => {
  const chemin = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  const fichier = /^\/(three|urdf-loader)\//.test(chemin) ? join(LAB_UI, chemin)
    : chemin.startsWith('/urdf/') ? join(ICI, chemin) : join(ICI, 'scene.html');
  try {
    res.writeHead(200, { 'Content-Type': TYPES[extname(fichier)] || 'application/octet-stream' });
    res.end(readFileSync(fichier));
  } catch {
    res.writeHead(404).end();
  }
});
await new Promise((ok) => serveur.listen(0, '127.0.0.1', ok));
const base = `http://127.0.0.1:${serveur.address().port}/scene.html`;

const navigateur = await chromium.launch({
  executablePath: process.env.CHROMIUM || undefined,
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
});
const ffmpeg = (...args) => execFileSync('ffmpeg', ['-loglevel', 'error', '-y', ...args], { stdio: 'inherit' });
try {
  for (const scene of scenes) {
    const page = await navigateur.newPage({ viewport: { width: 1280, height: 720 } });
    page.on('pageerror', (e) => console.error(`${scene} :`, e.message));
    await page.goto(`${base}?scene=${scene}&periode=${PERIODE}`);
    await page.waitForFunction('window.pret === true', null, { timeout: 180_000 });
    const images = join(sortie, `${scene}-images`);
    rmSync(images, { recursive: true, force: true });
    mkdirSync(images);
    for (let i = 0; i < PERIODE * IMAGES_PAR_S; i++) {
      const url = await page.evaluate((t) => window.dessiner(t), i / IMAGES_PAR_S);
      writeFileSync(join(images, `${String(i).padStart(4, '0')}.png`), Buffer.from(url.split(',')[1], 'base64'));
    }
    await page.close();
    const motif = join(images, '%04d.png'), nom = join(sortie, scene);
    // WebM (VP9) d'abord, MP4 (H.264) en repli ; muets, démarrage rapide ; image d'attente en WebP
    ffmpeg('-framerate', String(IMAGES_PAR_S), '-i', motif, '-c:v', 'libvpx-vp9', '-b:v', '0', '-crf', scene === 'bras' ? '40' : '47',
      '-row-mt', '1', '-deadline', 'good', '-cpu-used', '2', '-pix_fmt', 'yuv420p', '-an', `${nom}.webm`);
    ffmpeg('-framerate', String(IMAGES_PAR_S), '-i', motif, '-c:v', 'libx264', '-crf', scene === 'bras' ? '27' : '31', '-preset', 'slow',
      '-pix_fmt', 'yuv420p', '-movflags', '+faststart', '-an', `${nom}.mp4`);
    ffmpeg('-i', join(images, '0000.png'), '-c:v', 'libwebp', '-quality', '70', `${nom}.webp`);
    rmSync(images, { recursive: true });
    console.log(`${scene} : ${nom}.webm, .mp4, .webp`);
  }
} finally {
  await navigateur.close();
  serveur.close();
}
