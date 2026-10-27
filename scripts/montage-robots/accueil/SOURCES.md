# Montage du bandeau d'accueil : sources

`contenus/academy_content/static/videos/robots.{webm,mp4,webp}` : un extrait de 2,5 s de chaque vidéo
ci-dessous, dans cet ordre. Les fichiers `.debut` (début de l'extrait, en secondes) et `.cadrage`
(position de la fenêtre 16:9 dans une vidéo verticale) de ce dossier règlent chaque extrait.

| Fichier | Robot | Source | Licence |
|---|---|---|---|
| 01-drone.mp4 | Drone agricole qui pulvérise un champ | [Pexels : Aerial drone spraying technology on farm field](https://www.pexels.com/video/aerial-drone-spraying-technology-on-farm-field-34182418/) (fichier 14490138, 960×540) | [Licence Pexels](https://www.pexels.com/license/) |
| 02-quadrupede.mp4 | Robot quadrupède avec lidar | [Pexels : Advanced robot dog navigating indoors](https://www.pexels.com/video/advanced-robot-dog-navigating-indoors-33837506/) (fichier 14360262, 1280×720) | [Licence Pexels](https://www.pexels.com/license/) |
| 03-bras.mp4 | Bras robotique qui joue aux échecs (vertical) | [Pexels : A robot playing chess](https://www.pexels.com/video/a-robot-playing-chess-8327801/) (fichier 8328103, 720×1280) | [Licence Pexels](https://www.pexels.com/license/) |
| 04-livraison.mp4 | Robot de livraison sur un trottoir | [Pexels : A robot rover on the road](https://www.pexels.com/video/a-robot-rover-on-the-road-8566713/) (fichier 8566722, 1920×1080) | [Licence Pexels](https://www.pexels.com/license/) |
| 05-humanoide.mp4 | Humanoïde « Orion » (vertical) | [Pexels : Innovative humanoid robot demonstration](https://www.pexels.com/video/innovative-humanoid-robot-demonstration-40495901/) (fichier 17305853, 1080×1920) | [Licence Pexels](https://www.pexels.com/license/) |
| 06-sousmarin.mp4 | Robot sous-marin (ROV) qui explore une épave | [Pixabay : Robot underwater exploration](https://pixabay.com/videos/robot-underwater-exploration-321165/) (fichier 321165, 1280×720) | [Licence Pixabay](https://pixabay.com/service/license-summary/) |

Les deux licences permettent l'usage commercial, gratuit et sans attribution obligatoire. Les vidéos
sources ne sont pas dans le dépôt (plusieurs Mo chacune) : téléchargez-les depuis ces pages, renommez-les
comme ci-dessus dans ce dossier, puis :

```bash
scripts/montage-robots/monter.sh scripts/montage-robots/accueil /tmp/robots
cp /tmp/robots.{webm,mp4,webp} /tmp/robots-mobile.{webm,mp4} contenus/academy_content/static/videos/
```
