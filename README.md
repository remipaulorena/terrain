# TERRAIN

Veille sport business en une seule information. Le moteur agrège les flux RSS des médias spécialisés de l'industrie du sport, fait trancher un modèle qui joue le rôle de rédacteur en chef, et affiche l'unique sujet qui structure le marché à cet instant.

Deux marchés : **FR** (sport business francophone) et **INT** (industrie mondiale). Bascule par les boutons ou par swipe sur mobile.

## Fichiers

- `engine.py` : agrégation RSS, scoring business, sélection par le modèle, serveur HTTP, planification
- `app.html` : interface servie par le moteur
- `index.html` : copie identique, pour un hébergement statique sans moteur
- `requirements.txt` : dépendances

## Installation locale

```bash
pip install -r requirements.txt
export GEMINI_API_KEY="votre_cle"
python engine.py
```

L'application est disponible sur `http://localhost:10000`.

## Variables d'environnement

- `GEMINI_API_KEY` : clé Google Gemini
- `ANTHROPIC_API_KEY` : clé Claude, utilisée en secours si Gemini ne répond pas
- `LLM_PROVIDER` : mettre `anthropic` pour inverser l'ordre et passer Claude en premier
- `PORT` : port d'écoute, 10000 par défaut

Une seule des deux clés suffit pour faire tourner l'application.

## Vérifier les flux avant déploiement

Les URL de flux RSS changent régulièrement chez les éditeurs. Cette commande teste chaque source et affiche le nombre d'entrées récupérées.

```bash
python engine.py --test-sources
```

Remplacez ou retirez dans `engine.py` toute source qui ressort en erreur. Les listes `SOURCES_FR` et `SOURCES_INT` se modifient en une ligne.

## Déploiement

Le moteur écoute sur `PORT` et sert lui-même l'interface, il fonctionne tel quel sur Render, Railway ou Fly.

- Build : `pip install -r requirements.txt`
- Start : `python engine.py`

Trois routes utiles :

- `/` : l'application
- `/api/news` : le JSON courant, pour brancher un widget ou un écran d'accueil
- `/ping` : déclenche une actualisation immédiate, à appeler depuis un cron externe

L'actualisation automatique tourne à `:00` et `:30` de chaque heure.

## Personnalisation

- **Nom** : constante `APP_NAME` dans `engine.py`, balise `.logo` et `<title>` dans les deux HTML
- **Couleur** : variable CSS `--accent`, réglée sur `#5B8CFF`, un bleu fluo dérivé de la teinte du logo ESG Sport
- **Catégories** : ensembles `CATEGORIES_FR` et `CATEGORIES_INT` dans `engine.py`, à répercuter dans le prompt
- **Ligne éditoriale** : fonction `build_prompt`, c'est là que se règle ce qui mérite d'être retenu
- **Filtrage** : `BUSINESS_SIGNALS_*` remonte les titres à signal économique, `NOISE_*` fait redescendre les résultats sportifs et les comptes rendus de match

## Fonctionnement du tri

Chaque titre reçoit un score avant d'être soumis au modèle. Un point par signal business détecté, un point de bonus s'il figure en tête de flux, deux points retirés par marqueur de bruit sportif. Les 28 meilleurs titres partent au modèle avec un badge `[SIGNAL_FORT]` ou `[SECONDAIRE]`. Le modèle applique ensuite la règle du consensus et rend une catégorie, un titre de 50 à 75 caractères et un lien source.
