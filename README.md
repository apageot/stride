# Stride

Ton coach running perso : un plan qui s'adapte, des séances qui arrivent toutes seules sur ta Garmin, et un bilan clair après chaque sortie.

## Comment ça marche

- **Pas de jours fixes** : chaque semaine (du lundi au dimanche), il y a 3 séances à faire quand tu veux :
  - un footing ;
  - une séance clé ;
  - une sortie longue.

  S'y ajoute un footing bonus facultatif, jamais compté comme manqué. Chaque sortie Garmin est associée automatiquement à la séance qui lui ressemble : fractionné → séance clé, sortie longue en durée → sortie longue, sinon → footing.
- **Plan** : des cycles de 4 semaines.
  - Séance clé : VMA (semaine 1), puis seuil (semaine 2), puis allure 10 km (semaine 3).
  - Semaine 4 : semaine allégée. Un cycle sur deux, elle contient un test sur 5 km (soit toutes les 8 semaines).
- **Allures** :
  - elles sont calculées à partir de tes chronos, puis mises à jour par les tests et par tes fractions réussies (seulement à la hausse) ;
  - les séances allure 10 km partent de ton allure actuelle et se rapprochent de 4:30/km à chaque cycle.
- **Endurance au cardio** : footings et sorties longues ont une cible en bpm, entre 65 et 77 % de ta FC max. Celle-ci est lue dans tes sorties Garmin, ou réglée avec `fc_max` dans `config.json`. Le bilan donne ton écart en bpm.
- **Garmin** : rien ne part tout seul. Le bouton **Envoyer sur la montre** d'une séance l'ajoute à ton calendrier Garmin Connect, à la date du jour, en 2 minutes environ. Si le plan change, une séance déjà envoyée est mise à jour.
- **Bilan** : après chaque sortie, tu as tes écarts à la cible, fraction par fraction pour les séances clés, et en bpm pour l'endurance.
- **Adaptation** :
  - séance réussie → la prochaine du même type monte d'un cran ;
  - séance difficile → elle reste au même niveau ;
  - deux séances dures ratées d'affilée → semaine allégée ;
  - séance manquée → pas de rattrapage.
- **Synchro** : elle tourne toute seule sur GitHub toutes les 3 h, de 6 h à 22 h.

## Style
Un seul style : fond photo sombre qui se floute au scroll, typo blanche, accents bleu clair.

**Photo de fond** : c'est le fichier `docs/img/fond.jpg`. Remplace-le par une de tes photos, même nom, de préférence floue de mouvement. Le dépôt étant public, utilise une photo dont tu as les droits (la tienne, idéalement).

## Installation (15 min, une seule fois)

### 1. Dépôt GitHub
Crée un dépôt **public** nommé `stride`, puis mets-y tous les fichiers de ce dossier : glisse-les dans GitHub via *Add file › Upload files*, en gardant les dossiers.

> Le dépôt doit être public pour que GitHub Pages soit gratuit. Tes sorties (distances, allures, fréquence cardiaque) seront donc visibles par qui a le lien, mais pas tes traces GPS ni tes identifiants.

### 2. Connexion Garmin (sur ton Mac)
```bash
python3 --version                     # il faut 3.12 ou plus (sinon : brew install python@3.12)
curl -LsSf https://astral.sh/uv/install.sh | sh
~/.local/bin/uv run --python 3.12 --with garminconnect --with curl_cffi scripts/connexion_garmin.py
```
Le script te demande ton email, ton mot de passe et, si tu l'as activé, le code de double authentification. Il affiche ensuite un bloc de texte : copie-le en entier. Ton mot de passe n'est enregistré nulle part.

### 3. Secrets GitHub
Dans le dépôt, va dans *Settings › Secrets and variables › Actions › New repository secret* :
- `GARMIN_TOKENS_JSON` : le bloc copié à l'étape 2.
- *(facultatif, en secours)* `GARMIN_EMAIL` et `GARMIN_PASSWORD`, seulement si tu n'as pas la double authentification.

### 4. Publier l'app
*Settings › Pages* : Source = *Deploy from a branch*, Branch = `main`, dossier = `/docs`.
L'app sera en ligne à l'adresse `https://TON-PSEUDO.github.io/stride/`.

### 5. Première synchro
Va dans l'onglet *Actions*, ouvre **Synchro Garmin**, puis clique sur *Run workflow*. Au bout d'environ 2 minutes, l'app affiche ton vrai plan à la place des données de démo, et les séances apparaissent dans Garmin Connect.

### 6. Sur ton iPhone
Ouvre l'adresse dans Safari, puis *Partager › Sur l'écran d'accueil*.

**Pour que le bouton « Envoyer sur la montre » marche** : crée un jeton GitHub dans *Settings › Developer settings › Fine-grained tokens*, limité au dépôt `stride`, avec la permission *Actions : Read and write*. La première fois que tu appuies sur le bouton, l'app te demande ce jeton : colle-le, il reste sur ton téléphone.

## Réglages : `config.json`
Modifie ce fichier directement sur GitHub (icône crayon).

| Clé | Rôle |
|---|---|
| `records` | Tes chronos de départ, qui servent à calculer les allures. Ils sont ensuite remplacés par les tests 5 km. |
| `debut` | Date de début du plan (un lundi). |
| `date_course` | `null` tant que tu n'as pas de course. Mets par exemple `"2027-03-14"` : la semaine d'avant devient allégée, et la semaine de la course contient un rappel d'allure puis la course. |
| `objectif` | Distance et temps visés. |
| `fc_max` | Ta FC max en bpm. Laisse `null` pour que l'app la lise dans tes sorties. |

Les semaines terminées restent figées. Seules la semaine en cours et les suivantes sont recalculées.

## Séance du jour sur la montre
Ouvre *Entraînement › Calendrier* (ou *Séances*) et lance la séance. Chaque fraction devient alors un tour, ce qui permet l'analyse fraction par fraction. Pour le test 5 km, appuie sur **Tour** à la fin de l'échauffement pour lancer le chrono.

## Si ça casse
La connexion Garmin passe par une bibliothèque non officielle (`python-garminconnect`) : si Garmin change quelque chose de son côté, elle peut tomber en panne temporairement. Dans ce cas, l'app affiche un bandeau rouge. Pour réparer :
1. Relance l'étape 2 et mets à jour le secret `GARMIN_TOKENS_JSON`.
2. Si ça ne suffit pas, mets à jour la bibliothèque (`garminconnect` dans `requirements.txt`).

## Tester en local
```bash
python3 -m engine.demo                         # régénère les données de démo
cd docs && python3 -m http.server 8000         # puis ouvre http://localhost:8000
```

## Chaleur
Au-dessus de 15 °C ressentis, les allures cibles sont ralenties de 0,5 % par degré (max +10 %).
La température vient d'Open-Meteo (gratuit, sans clé) pour le `lieu` de `config.json` : l'app l'affiche dans la fiche séance,
et quand tu appuies sur « Envoyer sur la montre », la séance part avec les allures corrigées (le titre indique la température).
Les footings pilotés au cardio ne changent pas : le cardio tient déjà compte de la chaleur.

## Ressenti
Après une séance, touche Facile / OK / Dur dans le bilan. « Dur » sur une séance tenue = on consolide au même niveau ;
« Facile » = le niveau peut monter plus vite à partir de tes fractions.
