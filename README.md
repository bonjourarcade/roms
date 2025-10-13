# BonjourArcade

Merci de jouer ! :)

- **Jeu de la semaine** : sélectionné automatiquement chaque semaine via le système Plinko
- `metadata.yaml` : fichier modèle de métadonnées à placer dans
  `public/games/<game_id>/`
- ROMs: https://archive.org/details/roms_bonjourarcade

# Ajouter un nouveau jeu

1. Ajoutez la ROM dans le bon dossier `roms/<system>`.

C’est tout ! Quand vous poussez votre changement sur la branche principale, le
pipeline CI/CD le prendra en charge et exposera un endpoint correspondant à
votre ID. Par exemple : `https://bonjourarcade-abcdefgh.gitlab.io/<game_id>`.

# Faire apparaître le jeu sur la page d’accueil du site

1. Créez un dossier `public/games/<game_id>`, où `game_id` est le même nom que
   la base du fichier de votre ROM.
   - Exemple : si vous ajoutez `roms/NES/gauntlet.nes`, vous voudrez un dossier
     `public/games/gauntlet` pour y inclure les métadonnées.
2. Remplissez ensuite les métadonnées. Voir la section ci‑dessous pour plus de
   détails.

## Créer les métadonnées

Dans `public/games/<game_id>`, deux fichiers de métadonnées sont pris en charge :
- `cover.png` pour l’image de couverture du jeu
- `metadata.yaml` qui suit le [modèle](metadata.yaml)

# Définir les contrôles pour un système

Cela se fait dans [`public/config`](public/config/). Recherchez les fichiers
`controls_*.json`. Suivez la [documentation d’EmulatorJS](https://emulatorjs.org/docs4devs/control-mapping).

# Charger automatiquement une sauvegarde au démarrage d’un jeu

Créez un fichier d’état en cliquant sur le bouton « disquette » dans
l’émulateur. Déplacez puis renommez ce fichier en
`public/games/<game_id>/save.state`.

# Système « Jeu de la semaine »

Le jeu de la semaine est sélectionné automatiquement à l’aide de :
- **Système Plinko** : des graines hebdomadaires (format YYYYWW) déterminent la sélection
- **Prédictions** : jeux présélectionnés dans `public/plinko/predict/predictions.yaml`
- **Automatique** : aucune modification manuelle de fichiers nécessaire
