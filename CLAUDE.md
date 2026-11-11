# metabank — consignes projet

## Objet
Vision globale et analyse de mon patrimoine financier (comptes courants, livrets, assurances vie, PER, PEA, CTO),
**en local**, avec l'aide de l'IA pour la synthèse. Plan, architecture et jalons : docs/PLAN.md.
- **Lecture seule** : aucun virement, ordre de bourse ni arbitrage, jamais, même « pour tester ».
- **Proposer au fil de l'eau de nouvelles fonctions** : par défaut, toute suggestion est ajoutée au tableau
  docs/PLAN.md § Suggestions retenues (jalon, état) ; passer son état à « fait » quand elle est livrée.

## Données personnelles et secrets
- Le dépôt reste **privé**. Même privé, il ne contient aucune donnée personnelle : `data/` est ignoré par git.
- Identifiants bancaires : uniquement dans l'outil de chaque source (`~/.config/woob/backends` en droits 600,
  `~/.pytr/`). Jamais dans le code, la configuration, un test, un commit, un journal ou un prompt.
- Ni numéro de compte complet ni IBAN dans les sorties : `numero_masque` (quatre derniers caractères) suffit.
- Les tests n'utilisent que des comptes fictifs et ne touchent jamais au réseau.
- L'IA ne reçoit qu'un JSON de synthèse (montants, allocations, frais) : ni identifiant ni numéro.

## Exigences de calcul
- Montants en `Decimal`, jamais en float ; arrondi seulement à l'affichage. Devise toujours portée avec le montant.
- Toute valeur calculée (performance, frais, allocation) vient du code Python testé, **jamais du modèle de langage** ;
  le rapport IA commente des chiffres déjà calculés et n'en invente aucun.
- Chaque formule d'analyse (TRI, frais, fiscalité) est écrite dans docs/MODELE.md (à créer au jalon 6) avant d'entrer
  dans le code, et cite son paragraphe (`# MODELE § 2.1`).
- Dates avec fuseau (`datetime.now().astimezone()`), règle ruff DTZ.
- Un instantané brut n'est jamais modifié : on corrige la traduction, puis on reconstruit la base.

## Choix techniques
- Python ≥ 3.12, dépendances gérées par uv (`uv sync`, `uv run …`).
- Un connecteur = un module sous `metabank/connecteurs/`, séparé en deux : traduction pure (testée avec de vrais
  objets de la source construits à la main) et collecte (frontière réseau, erreurs traduites en `ErreurCollecte`
  avec un message qui dit quoi faire).
- woob : backends déclarés par `uv run woob config add <module>` ; metabank ne fait que les charger par leur nom
  (`config/metabank.json`). Hors `--interactif`, woob ne déclenche aucune double authentification.
- Configuration : toutes les clés lues par le code figurent dans `config/metabank.json` avec une phrase dans `_aide` ;
  `config/local.json` (ignoré par git) surcharge clé par clé.
- Bibliothèques web tierces copiées dans `vendor/`, jamais de CDN (les montants ne doivent fuiter vers personne).

## Conventions (reprises de cap-prepa, metascrap et egide)
- Le code est lu par quelqu'un qui a oublié le contexte : la règle qui sert le lecteur gagne.
- Domaine en français ; en Python, identifiants sans accents : `verbe_complement()`, prédicats `est_x()`,
  `_prive`, `MAJUSCULES`. Booléens nommés par ce qu'ils affirment. Pas d'abréviations hors domaine.
- Fonctions ≤ 50 lignes ; > 80 refusé sur du code neuf. Module > 800 lignes : à découper.
- Docstring Google sur toute fonction publique : 1re ligne = ce qu'elle rend, à l'infinitif ;
  puis seulement le non-évident, dont la devise ou l'unité de chaque grandeur.
- Commentaires : le pourquoi (chiffre mesuré, ce qui casse si on l'enlève), jamais le quoi.
- Erreurs : attraper le type qu'on sait traiter, jamais `except Exception` hors frontière journalisée.
- Imports en tête de module. Deux fois on note, trois fois on factorise. Un nom = un concept.
- Tests : un test par comportement, nommé par ce qu'il garantit ; le test d'un bug corrigé reproduit le
  bug et son docstring raconte ce qui s'était passé ; aucun test ne touche au réseau.
- Écritures de fichiers atomiques (temporaire puis renommage).

## Façon de travailler
- Frugalité en tokens : filtrer les sorties avant de les lire, ne pas relire un fichier qu'on vient d'éditer.
- Utiliser Serena (outils symboliques) pour naviguer et modifier le code plutôt que relire des fichiers entiers.
- Faire une liste de tâches pour les demandes complexes ; analyser les données avant de choisir une solution.
- Avant d'écrire un connecteur, regarder les vraies données de la source (en local, sans les copier dans le dépôt).
- Lancer seulement les tests des fichiers touchés.
- Ne pas modifier README ni docs/PLAN.md § Jalons sans demande ; docs/FORMATS.md et docs/MODELE.md se mettent à jour
  avec le code qui les applique.
- **README : mis à jour seulement lors de la pose d'un tag de version**, jamais entre deux tags.
- Ne jamais tuer un processus qu'on n'a pas lancé soi-même.

## Vérifications avant commit
- `uv run pytest -q`
- `uv run ruff check metabank tests` et `uv run ruff format metabank tests`
- Conventional commits en français (`feat:`, `fix:`, `docs:`, `chore:`), une branche par fonctionnalité,
  PR avec description et liste de contrôle.
