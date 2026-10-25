# Montage du bandeau d'accueil : sources

`contenus/academy_content/static/videos/robots.{webm,mp4,webp}` : un extrait de 2,5 s de chaque vidéo
ci-dessous, dans cet ordre. Les fichiers `.debut` (début de l'extrait, en secondes) et `.cadrage`
(position de la fenêtre 16:9 dans une vidéo verticale) de ce dossier règlent chaque extrait.

| Fichier | Robot | Source | Licence |
|---|---|---|---|
| 01-drone.mp4 | Drone agricole qui pulvérise un champ | [Pexels 14490138](https://www.pexels.com/video/14490138/) (fichier 960×540) | [Licence Pexels](https://www.pexels.com/license/) |
| 02-quadrupede.mp4 | Robot quadrupède avec lidar | [Pexels 14360262](https://www.pexels.com/video/14360262/) (1280×720) | [Licence Pexels](https://www.pexels.com/license/) |
| 03-bras.mp4 | Bras robotique qui joue aux échecs (vertical) | [Pexels 8328103](https://www.pexels.com/video/8328103/) (720×1280) | [Licence Pexels](https://www.pexels.com/license/) |
| 04-livraison.mp4 | Robot de livraison sur un trottoir | [Pexels 8566722](https://www.pexels.com/video/8566722/) (1920×1080) | [Licence Pexels](https://www.pexels.com/license/) |
| 05-humanoide.mp4 | Humanoïde « Orion » (vertical) | [Pexels 17305853](https://www.pexels.com/video/17305853/) (1080×1920) | [Licence Pexels](https://www.pexels.com/license/) |
| 06-sousmarin.mp4 | Robot sous-marin (ROV) qui explore une épave | [Pixabay 321165](https://pixabay.com/videos/id-321165/) (1280×720) | [Licence Pixabay](https://pixabay.com/service/license-summary/) |

Les deux licences permettent l'usage commercial, gratuit et sans attribution obligatoire. Les vidéos
sources ne sont pas dans le dépôt (plusieurs Mo chacune) : téléchargez-les depuis ces pages, renommez-les
comme ci-dessus dans ce dossier, puis :

```bash
scripts/montage-robots/monter.sh scripts/montage-robots/accueil /tmp/robots
cp /tmp/robots.{webm,mp4,webp} contenus/academy_content/static/videos/
```
