# metabank — consignes projet

## Objet
Vision globale et analyse de mon patrimoine financier (comptes courants, assurance vie, PER, PEA), **en local**.
Le stockage, le tableau de bord et la performance sont confiés à **Wealthfolio**, déployé par `compose.yml` ;
metabank l'alimente (convertisseurs vers son import CSV) et ajoute l'analyse française et le rapport IA.
Plan, architecture et jalons : docs/PLAN.md.
- **Lecture seule** : aucun virement, ordre de bourse ni arbitrage, jamais, même « pour tester ».
- On ne modifie pas Wealthfolio : on le déploie et on l'alimente. Un besoin qu'il ne couvre pas devient un outil
  metabank ou, à défaut, un add-on Wealthfolio (SDK TypeScript officiel).
- **Proposer au fil de l'eau de nouvelles fonctions** : par défaut, toute suggestion est ajoutée au tableau
  docs/PLAN.md § Suggestions retenues (jalon, état) ; passer son état à « fait » quand elle est livrée.

## Données personnelles et secrets
- Le dépôt reste **privé**. Même privé, il ne contient aucune donnée personnelle : `data/` (base Wealthfolio),
  `.env`, exports CSV et relevés PDF sont ignorés par git.
- Identifiants des sources : uniquement dans leur propre outil (`~/.pytr/`, trousseau macOS). Jamais dans le code,
  la configuration, un test, un commit, un journal ou un prompt.
- `.env` est créé par `outils/preparer_env.sh` (droits 600) ; on ne le lit pas, on ne le recopie pas, on n'affiche
  jamais `WF_SECRET_KEY` ni l'empreinte du mot de passe.
- Ni numéro de compte complet ni IBAN dans les sorties ; les tests n'utilisent que des données fictives.
- L'IA ne reçoit qu'un extrait chiffré (montants, allocations, frais) : ni identifiant ni numéro.

## Déploiement
- `compose.yml` est la seule définition du service, identique sur Mac et NAS ; ce qui change d'une machine à
  l'autre passe par `.env` (`WF_BIND`, `WF_PORT`, `WF_CORS_ALLOW_ORIGINS`, `WF_VERSION`).
- Écoute sur 127.0.0.1 par défaut ; l'ouverture au réseau local est un choix explicite (`preparer_env.sh reseau`).
- Toute variable ajoutée à `.env` figure dans `.env.exemple` avec une phrase qui l'explique.
- Avant de changer `WF_VERSION`, sauvegarder `data/` (Wealthfolio migre sa base au démarrage).

## Exigences de calcul (convertisseurs et analyse, à venir)
- Python ≥ 3.12, dépendances gérées par uv.
- Montants en `Decimal`, jamais en float ; devise toujours portée avec le montant.
- Avant d'écrire un convertisseur, relever le format réel attendu par Wealthfolio et produit par la source,
  sur de vraies données, en local, sans les copier dans le dépôt.
- Un import ne doit jamais créer de doublon : identifiant stable par opération source, testé.
- Toute valeur calculée vient du code testé, **jamais du modèle de langage** ; le rapport IA commente des chiffres
  déjà calculés et n'en invente aucun. Chaque formule d'analyse est écrite dans docs/MODELE.md avant d'entrer
  dans le code et cite son paragraphe.

## Conventions (reprises de cap-prepa, metascrap et egide)
- Le code est lu par quelqu'un qui a oublié le contexte : la règle qui sert le lecteur gagne.
- Domaine en français ; en Python, identifiants sans accents : `verbe_complement()`, prédicats `est_x()`,
  `_prive`, `MAJUSCULES`. Booléens nommés par ce qu'ils affirment. Pas d'abréviations hors domaine.
- Fonctions ≤ 50 lignes ; > 80 refusé sur du code neuf. Module > 800 lignes : à découper.
- Docstring Google sur toute fonction publique : 1re ligne = ce qu'elle rend, à l'infinitif ;
  puis seulement le non-évident, dont la devise ou l'unité de chaque grandeur.
- Commentaires : le pourquoi (chiffre mesuré, ce qui casse si on l'enlève), jamais le quoi.
- Erreurs : attraper le type qu'on sait traiter, jamais `except Exception` hors frontière journalisée.
- Scripts shell en sh POSIX, lisibles au double-clic (`.command`), sans commentaire en fin de ligne de commande
  dans la documentation (zsh les refuse).
- Tests : un test par comportement, nommé par ce qu'il garantit ; aucun test ne touche au réseau.
- Écritures de fichiers atomiques (temporaire puis renommage).

## Façon de travailler
- Frugalité en tokens : filtrer les sorties avant de les lire, ne pas relire un fichier qu'on vient d'éditer.
- Utiliser Serena (outils symboliques) pour naviguer et modifier le code plutôt que relire des fichiers entiers.
- Faire une liste de tâches pour les demandes complexes ; analyser les données avant de choisir une solution.
- Ne pas modifier README ni docs/PLAN.md § Jalons sans demande.
- **README : mis à jour seulement lors de la pose d'un tag de version**, jamais entre deux tags.
- Ne jamais tuer un processus qu'on n'a pas lancé soi-même ; `docker compose down` seulement sur demande.

## Vérifications avant commit
- `sh -n` sur les scripts touchés ; `docker compose config -q` si `compose.yml` change.
- Dès qu'il y a du Python : `uv run pytest -q`, `uv run ruff check` et `uv run ruff format`.
- Conventional commits en français (`feat:`, `fix:`, `docs:`, `chore:`), une branche par fonctionnalité,
  PR avec description et liste de contrôle.
