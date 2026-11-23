# metabank — plan

## But
Voir, comprendre et piloter **tout le patrimoine du foyer** : placements (assurance vie, PER, PERP, PEA), épargne
disponible (livrets), comptes courants, crédits et biens immobiliers. **Le plus simplement possible** : les mises à
jour arrivent par fichiers déposés ou, quand la banque le permet, par connexion directe ; ce qui peut se calculer
(crédits, intérêts attendus) n'a pas besoin d'import.

Contraintes permanentes :
- **Lecture seule** : aucun virement, ordre ni arbitrage n'est jamais passé par metabank.
- **En local, sans abonnement** (hors le compte Claude déjà payé) ; `data/` ne quitte pas la maison : le Mac, ou le
  NAS QNAP qui fera tourner metabank comme metascrap. Tout ce qui
  sort (connexion bancaire, cours publics, questions à Claude) est visible dans l'onglet Synoptique.
- **Chiffres calculés par du code testé**, formules écrites d'abord dans docs/MODELE.md ; l'IA commente, ne calcule pas.
- **Pas de recommandation personnalisée d'investissement** : metabank donne les faits (répartition, frais, fiscalité,
  performances comparées, simulations) ; la décision reste au titulaire, ou à un conseiller indépendant rémunéré en
  honoraires.

## Architecture : metabank, application chapeau

```
 Sources                         Connecteurs (plug-ins)              Socle metabank                       Restitution
 ───────                         ──────────────────────              ──────────────                       ───────────
 Suravenir, Cardif (PDF)    ──┐  famille « fichier » :               archives brutes (data/archives/)     application web locale
 BNP : exports CSV          ──┼─ reconnaître → lire → lot ────┐      base SQLite (data/metabank.db)       ├ Tableau de bord
 Trade Republic (CSV appli) ──┘  (dépôt unique, dossier        │      ├ comptes, opérations, soldes        ├ Budget
                                  surveillé)                   ├────► ├ positions, frais, historique   ──► ├ Synoptique
 BNP comptes, Revolut       ──── famille « direct » : DSP2 ────┤      ├ journal des imports                ├ Configuration
                                  (Enable Banking)              │      └ réglages (sans secret)             └ …
 Crédits, intérêts livrets  ──── famille « calcul » ───────────┤      analyses (code testé, MODELE.md)     rapports PDF
 Valeurs liquidatives,      ──── famille « référence » ────────┘                                           Claude : assistant et
 indices, repères publics         (option, ISIN et indices seuls)     secrets : trousseau macOS             serveur MCP local
                                                                                                            (lecture seule)
```

- **Projets externes utilisés ou envisagés** :
  - [Enable Banking](https://enablebanking.com/docs/api/linked-accounts/) : accès DSP2 aux comptes de paiement,
    mode restreint gratuit pour un usage personnel sur ses propres comptes ;
  - [pytr](https://github.com/pytr-org/pytr) : secours non officiel pour Trade Republic si l'export CSV ne suffit pas ;
  - [Finanze](https://github.com/finanze/finanze) (AGPL-3.0, local) : agrégateur libre comparable (Enable Banking,
    Trade Republic, serveur MCP), à regarder avant de coder les connecteurs ;
  - [Wealthfolio](https://github.com/wealthfolio/wealthfolio) (`compose.yml`) : conservé, plus au cœur ;
  - [Keep Your Folio](https://keepyourfolio.fr/) : simulateurs fiscaux, à évaluer.
- **Règle** : un projet externe n'est intégré que s'il garde les données en local ; on ne le modifie pas, on lit ses
  exports ou on l'alimente par ses imports. Le modèle et les chiffres de référence restent ceux de metabank.

## Connecteurs : une approche par plug-ins

Repris de metascrap (`acces/contrat.py`, `acces/registre.py`, `acces/journal.py`) : **un seul contrat** pour tous les
imports, qu'ils viennent d'un fichier ou d'une connexion directe.

| Famille | Rôle | Exemples |
|---|---|---|
| fichier | reconnaît un fichier à son contenu, puis le lit | relevé annuel Suravenir (PDF), situation Cardif (PDF), export BNP (CSV), export Trade Republic (CSV) |
| direct | interroge un service, avec l'accord du titulaire | Enable Banking (DSP2) pour BNP et Revolut ; pytr en secours pour Trade Republic |
| calcul | produit une donnée sans import | capital restant dû projeté, intérêts attendus des livrets |
| référence | données publiques, sans rien de personnel | valeurs liquidatives par ISIN, indices, rendement moyen des fonds en euros, inflation, taux réglementés |

Le contrat d'un connecteur :
- **description** : nom, libellé, famille, établissements et types de comptes couverts, réseau utilisé (`local`,
  `dsp2`, `public`), réglages attendus (dont ceux qui sont des secrets) ;
- **fichier** : `reconnaitre(fichier)` rend l'établissement, le compte et le titulaire, ou rien ; `lire(fichier)` rend un
  **lot** normalisé (comptes, soldes, opérations avec identifiant stable, positions, frais) ;
- **direct** : `synchroniser(compte, depuis)` rend un lot ; `etat()` rend joignable, échéance de l'accord, message ;
- **actif = réglages renseignés** (comme metascrap) : un connecteur sans ses réglages est grisé, sans autre interrupteur.

Le **registre** liste les connecteurs et, pour chaque compte, un accès **principal** et un accès **de secours** (BNP :
DSP2, sinon export CSV). Le **journal** garde chaque import ou synchronisation : date, connecteur, compte, résultat,
nombre d'éléments, erreur. Ajouter un établissement revient à écrire un module dans `metabank/connecteurs/`, sans
toucher au reste.

## Base de données

**Décision : oui, une base SQLite locale, en gardant les fichiers bruts.**
- **Pourquoi** : la connexion directe produit des données sans fichier ; l'historique du patrimoine demande des
  instantanés datés ; un même mouvement peut arriver par l'export CSV et par la DSP2 et ne doit compter qu'une fois ;
  le journal, les réglages et les règles de classement ont besoin d'un endroit sûr. Relire tous les fichiers à chaque
  lancement ne tiendra plus.
- **SQLite** : fournie avec Python (aucune dépendance), un seul fichier `data/metabank.db`, simple à sauvegarder.
- **Archives brutes** : tout ce qui entre (PDF, CSV, réponse d'API en JSON) est copié tel quel dans `data/archives/`.
  **La base se reconstruit entièrement depuis les archives** : en cas de doute, on la jette et on la refait.
- **Exactitude** : montants en centimes (entiers), quantités et valeurs liquidatives en texte décimal ; schéma
  versionné, migrations automatiques au lancement.
- **Secrets hors base** : clé privée Enable Banking et identifiants dans le trousseau macOS ; la base ne garde qu'une
  référence. Chiffrement du disque par FileVault ; sauvegarde chiffrée sur le NAS.
- **Tables** : titulaires, établissements, comptes, connecteurs et réglages, imports (journal), opérations, soldes
  datés, positions (ISIN, parts, valeur liquidative), frais, biens, règles de classement, repères publics, instantanés.

## Onglets à ajouter

### Configuration
- **Titulaires et comptes** : le registre des comptes (titulaire, type, établissement, numéro masqué, accès principal
  et de secours, fréquence de mise à jour attendue), modifiable ; remplace le sens porté par les noms de dossiers.
- **Connecteurs** : une fiche par connecteur, générée depuis ses réglages. Enable Banking : identifiant
  d'application, import de la clé privée dans le trousseau, comptes liés, bouton « Relier » ou « Renouveler
  l'accord », test de connexion, échéance des 180 jours. Trade Republic : export CSV ou pytr. Données publiques :
  activées ou non, source choisie.
- **Dossiers** : dossier de dépôt surveillé, dossier de sauvegarde sur le NAS.
- **Paramètres** : taux réglementés, coussin de sécurité, assistant Claude activé ou non.

### Synoptique
Comme celui de metascrap : **une ligne par compte, une colonne par étape**, du compte jusqu'aux écrans.

```
 Compte               Accès principal → secours        Réseau   Dernière donnée      Alimente                 30 jours
 BNP courant ****2513 DSP2 Enable Banking → CSV        dsp2     il y a 2 j  ●        solde, opérations        28 ✓ 0 ✗
 BNP Livret A ****1229 export CSV                      local    il y a 11 mois ●     solde, intérêts          1 ✓
 Suravenir AV …2854   relevé annuel PDF                local    31/12/2025 ●         valeur, fonds, frais     —
 Crédit RP ****6783   calcul (amortissement)           local    ce mois ●            capital restant dû       —
 PEA TR (Cédric)      export CSV de l'appli → pytr     local    jamais ○             positions, opérations    —
 Cours et repères     données publiques                public   hier ●               valeurs liquidatives     ISIN seuls
 Assistant Claude     claude -p, sans outil            claude   —                    questions                chiffres, sans numéro
```
- Pastille de fraîcheur selon la fréquence attendue du compte (vert, orange, rouge, jamais) ;
- clic sur une ligne : le journal de ses imports, le mode d'emploi pour récupérer le fichier, l'état de l'accord ;
- colonne réseau : ce qui sort de la machine, et vers où.

## Performance comparée aux repères publics

Pour chaque année et chaque vue (foyer, personne, contrat, PEA), le rendement obtenu face à :
- le **rendement moyen des fonds en euros** (ACPR, France Assureurs) ;
- le **rendement moyen des unités de compte**, au total et par catégorie (actions, diversifiés, obligataires,
  immobilier…), publié par France Assureurs — avant frais du contrat, donc corrigé de ces frais pour comparer ;
- un **repère pondéré par votre propre répartition** : la moyenne de chaque catégorie, au poids qu'elle a dans le
  contrat (une assurance vie à 70 % obligataire est comparée à la moyenne obligataire, pas aux actions) ;
- les **indices** pour le PEA et la part actions (MSCI World, CAC 40, dividendes réinvestis) ;
- le **Livret A** et l'**inflation** (Insee) ;
- la **performance publique de chaque fonds** (valeurs liquidatives par ISIN), pour vérifier les relevés et comparer
  chaque fonds à sa catégorie.

Les repères annuels sont publics et datés : ils vivent dans le dépôt (`metabank/references/`, avec leur source),
mis à jour une fois par an ; les valeurs liquidatives passent par le connecteur « référence », en option.
Formules dans docs/MODELE.md avant le code.

## Exécution sur le NAS QNAP, comme metascrap

metabank doit tourner sur le NAS QNAP, de la même façon que metascrap (`/share/…/metascrap`, environnement Python
dédié `run_qnap`, tâches planifiées par la crontab du QNAP), en plus du Mac.
- **Même code, deux machines** : ce qui change passe par la configuration (dossier `data/`, adresse et port d'écoute),
  jamais par le code. Le cœur reste en Python standard, sans dépendance propre au Mac.
- **Installation sans git** : le QNAP n'a pas `git` (constaté pour metascrap) ; le dépôt est copié depuis le Mac par
  un script d'installation, l'environnement Python est recréé sur place, `data/` n'est jamais écrasé.
- **À vérifier sur le QNAP** avant d'y basculer : version de Python (≥ 3.12), `pdftotext` (poppler) pour les relevés
  PDF, sinon lecture des PDF sur le Mac et dépôt du résultat.
- **Secrets** : pas de trousseau macOS sur le NAS. Les connecteurs demandent leurs secrets à un coffre abstrait :
  trousseau sur le Mac, fichier chiffré ou à droits 600 hors du dépôt sur le NAS (choix à faire à l'étape 4).
- **Accès** : écoute sur 127.0.0.1 par défaut ; l'ouverture au réseau local est un choix explicite, avec
  authentification, jamais exposée sur Internet.
- **Assistant** : `claude -p` reste sur le Mac ; sur le NAS, l'assistant est désactivé ou délégué au Mac.

## Mise à jour automatique des connexions directes

Quand un compte a une connexion directe (Enable Banking, pytr), metabank se met à jour **sans intervention** :
- **synchronisation planifiée** (chaque nuit par la crontab du QNAP, ou au lancement sur le Mac), compte par compte,
  par l'accès principal puis l'accès de secours ; chaque essai entre au journal et au synoptique ;
- **respect des limites DSP2** : sans le titulaire, une banque n'accepte que quelques consultations par jour (4 en
  général) ; une synchronisation par nuit suffit ;
- **accord bancaire de 180 jours** : il ne se renouvelle qu'avec le titulaire ; rappel avant l'échéance, et le compte
  passe en orange dans le synoptique s'il n'est plus à jour ;
- **après chaque synchronisation** : réponses archivées, base mise à jour, calculs refaits (crédits, instantané du
  patrimoine) ;
- toujours en **lecture seule**.

## Déjà en place (novembre 2026)

| Domaine | Contenu |
|---|---|
| Relevés d'assureurs | lecture des relevés annuels Suravenir et des situations Cardif ; contrôles de cohérence ; corrections saisies |
| Placements | versé, valeur, gagné et frais par année et depuis l'ouverture ; rentabilité annualisée ; frais fonds par fonds et rétrocessions |
| Application web | `metabank web` : tableau de bord (foyer, personne, contrat), budget, relevés, corrections, simulation des frais, assistant Claude, export PDF |
| Comptes BNP | exports CSV des comptes courants, compte locatif, Livret A et LDD : budget du foyer, dépenses par catégorie, frais bancaires, argent qui dort, intérêts et plafonds des livrets |
| Crédits | capital restant dû, taux, mensualité, fin et intérêts restants estimés ; lien avec les échéances prélevées |
| Patrimoine | actifs par famille, crédits, patrimoine net avec la valeur des biens saisie ; synthèse de l'épargne disponible |

## Feuille de route

Ordre retenu le 2026-11-22 : d'abord les fondations (base, connecteurs, configuration, synoptique), puis la
simplicité d'usage, puis le pilotage. Chaque étape est livrable seule.

### Étape 1 — Fondations

| Fonction | Détail | Fait quand | État |
|---|---|---|---|
| Base SQLite et archives | `data/metabank.db` reconstruisible depuis `data/archives/` ; schéma versionné ; montants en centimes | une base effacée se reconstruit à l'identique | fait (`metabank/base/`, `metabank reconstruire`) |
| Contrat des connecteurs | familles fichier, direct, calcul, référence ; registre principal et secours ; journal des imports | un connecteur s'ajoute en un module | fait (`metabank/connecteurs/`, journal dans `metabank/base/journal.py`) |
| Lecteurs existants en connecteurs | Suravenir PDF, Cardif PDF, BNP CSV (comptes, livrets, crédits) passés au contrat ; mêmes chiffres qu'avant | tous les tests actuels passent sur la nouvelle base | fait : connecteurs `bnp_csv`, `suravenir_pdf`, `cardif_pdf` ; écrans, ligne de commande et dépôt sur la base (`metabank/donnees.py`) ; état des écrans identique sur les vraies données le 2026-11-23 |
| Onglet Configuration | titulaires, registre des comptes, fiches des connecteurs, dossiers, paramètres ; secrets dans le trousseau | un compte se déclare et se corrige depuis la page | à faire |
| Onglet Synoptique | une ligne par compte : accès, réseau, fraîcheur, ce qui est alimenté, journal 30 jours | chaque compte montre comment et quand il est mis à jour | à faire |

### Étape 2 — Mises à jour sans effort

| Fonction | Détail | Fait quand | État |
|---|---|---|---|
| Dépôt unique | PDF et CSV glissés dans la page ou posés dans le dossier surveillé ; reconnus par les connecteurs, archivés, dédoublonnés | un fichier quelconque est pris en compte sans intervention | à faire |
| Crédits tenus à jour | capital restant dû projeté chaque mois (connecteur « calcul ») | le capital affiché suit le mois en cours | à faire |
| Historique du patrimoine | instantané à chaque mise à jour ; 13 derniers mois reconstitués ; courbe du patrimoine net | courbe mensuelle au tableau de bord | à faire |
| Performance comparée, première version | repères annuels publics : fonds en euros, unités de compte, Livret A, inflation, MSCI World | chaque rendement annuel est affiché face à ses repères | à faire |
| Règles de dépenses dans la page | créer, modifier, tester une règle de classement | une dépense non classée se classe en deux clics | à faire |

### Étape 3 — PEA

| Fonction | Détail | Fait quand | État |
|---|---|---|---|
| Connecteur Trade Republic | export CSV de l'application (Profil > Relevés > Export des transactions), relevé sur un vrai fichier avant d'écrire le lecteur ; pytr en secours | les opérations des deux PEA sont lues sans doublon | à faire |
| Positions et performance | lignes, prix de revient, plus-values latentes, dividendes, frais ; rentabilité face au MSCI World et au CAC 40 | le PEA apparaît au tableau de bord comme les autres placements | à faire |
| Règles du PEA | versements face au plafond de 150 000 € ; compteur des 5 ans à partir du premier versement | plafond restant et date des 5 ans affichés | à faire |

### Étape 4 — Connexion directe et valeurs au jour

| Fonction | Détail | Fait quand | État |
|---|---|---|---|
| Connecteur Enable Banking | application en mode restreint au nom du titulaire, réglée depuis l'onglet Configuration ; comptes BNP (et Revolut si couvert) ; l'export CSV reste en secours | les comptes courants se mettent à jour d'un clic | à faire |
| Mise à jour automatique | synchronisation planifiée des comptes en connexion directe (nuit sur le NAS, lancement sur le Mac), accès de secours, journal, calculs refaits ensuite ; dans les limites DSP2 | les comptes en connexion directe sont à jour chaque matin sans rien faire | à faire |
| Renouvellement | rappel avant l'échéance de l'accord bancaire (180 jours), visible dans le synoptique | rappel affiché à temps | à faire |
| Livrets | vérifier si la BNP les expose en DSP2 (a priori non : ce ne sont pas des comptes de paiement) ; sinon export annuel | décision notée ci-dessous | à faire |
| Connecteur « référence » | valeurs liquidatives par ISIN et indices, depuis une source publique, en option ; cache en base | assurance vie, PER et PEA affichent une valeur estimée datée | à faire |
| Téléchargement assisté | récupération guidée des relevés Suravenir, Cardif et Trade Republic dans le navigateur, titulaire présent | un relevé se récupère sans chercher où il est | à évaluer |

### Étape 5 — Pilotage

| Fonction | Détail | Fait quand | État |
|---|---|---|---|
| Allocation et arbitrage | classement de chaque fonds par type d'après son ISIN et sa fiche DIC ; vue globale toutes enveloppes ; alertes de concentration ; comparaison des frais avec les autres supports du contrat ; **simulateur d'arbitrage** (frais, coût fiscal, effet à 15 ans) ; **répartition cible fixée par le titulaire** et rééquilibrage par les versements ; fiche de préparation des rendez-vous. Faits et simulations seulement, aucune recommandation | la répartition globale et une simulation d'arbitrage sont visibles | à faire |
| Performance comparée, version complète | repère pondéré par la répartition de chaque contrat ; performance publique de chaque fonds face à sa catégorie | chaque contrat et chaque fonds a son écart au repère | à faire |
| Fiscalité et échéances | 5 ans des PEA, 8 ans des assurances vie, abattement après 8 ans, plafond de déduction PER saisi depuis l'avis d'impôt face aux versements de l'année, frais de transfert PER et PERP et leur date de gratuité, rappels de fin d'année | chaque échéance a sa date et son rappel | à faire |
| Projection retraite | capital estimé à l'âge de départ selon plusieurs hypothèses de rendement, de versements et d'inflation ; capital ou rente | trois scénarios comparés | à faire |
| Crédits | tableau d'amortissement ; rembourser par anticipation ou placer ; coût de l'assurance emprunteur | comparaison chiffrée disponible | à faire |
| Bien locatif | loyers, charges, prêt, intérêts : rendement brut et net, trésorerie mensuelle | rendement et trésorerie affichés | à faire |
| Budget | abonnements récurrents repérés, objectif par catégorie, comparaison d'une année sur l'autre | dépassements signalés | à faire |

### Étape 6 — IA et confort

| Fonction | Détail | Fait quand | État |
|---|---|---|---|
| Serveur MCP local | metabank expose en lecture seule ses chiffres et ses simulations ; Claude les interroge au lieu de recevoir un résumé figé | une question obtient une réponse chiffrée par metabank | à faire |
| Revue mensuelle | PDF et courte liste d'actions (fichiers à déposer, échéances, alertes) | revue produite chaque mois | à faire |
| Sauvegarde | copie chiffrée de `data/` sur le NAS, depuis l'onglet Configuration | restauration testée | à faire |
| Exécution sur le NAS QNAP | comme metascrap : dépôt copié sans git, environnement Python dédié, crontab, `data/` sur le NAS, secrets hors trousseau ; application servie sur le réseau local avec authentification | metabank tourne sur le QNAP et s'ouvre depuis le téléphone à la maison | à faire |
| Autres comptes | Revolut, compte-titres d'entreprise, relevés annuels Cardif | chacun a son connecteur | à faire |

## Jalons passés

| # | Jalon | État |
|---|---|---|
| 1 | Déploiement de Wealthfolio (`compose.yml`, `.env`) | conservé, mis de côté |
| 2-5 | Prise en main et convertisseurs vers Wealthfolio (Trade Republic, Revolut) | remplacés par les étapes 3 et 6 |
| 6 | Relevés d'assureurs, bilan par contrat, frais support par support | fait |
| 7 | Analyse et arbitrage | frais faits ; le reste devient l'étape 5 |
| 7 bis | Tableau de bord, puis application web locale, export PDF | fait |
| 8 | Comptes BNP, budget, livrets, crédits, patrimoine net | fait ; rapport IA mensuel repris en étape 6 |
| 9 | NAS | repris en étape 6 |

## Décisions prises
- **2026-11-22 — Base SQLite et archives brutes.** La base (stdlib, `data/metabank.db`) se reconstruit depuis
  `data/archives/` ; secrets dans le trousseau macOS, jamais en base.
- **2026-11-22 — Ce qui est saisi reste hors de la base.** Corrections, règles de classement, registre des comptes
  et réglages ne viennent d'aucune archive : ils restent dans leurs fichiers de `data/` (JSON, écriture atomique),
  pour qu'effacer la base ne perde rien. La base ne contient que ce qui se refait depuis `data/archives/`, journal
  compris (la date d'un import est celle de son archive). Archives rangées par provenance,
  `data/archives/<titulaire>/<dossier du compte>/<fichier>`, rejouées dans l'ordre de leur date de modification ;
  un fichier non reconnu n'est pas archivé.
- **2026-11-22 — metabank tourne aussi sur le NAS QNAP**, comme metascrap, et met à jour seul les comptes en
  connexion directe. Conséquence dès maintenant : cœur en Python standard sans dépendance au Mac, secrets demandés
  à un coffre abstrait (trousseau sur le Mac, autre coffre sur le NAS).
- **2026-11-22 — Imports par connecteurs (plug-ins)**, sur le modèle de metascrap : un contrat, quatre familles
  (fichier, direct, calcul, référence), un registre avec accès principal et de secours, un journal.
- **2026-11-22 — Onglets Configuration et Synoptique** ; le synoptique montre aussi ce qui sort de la machine.
- **2026-11-22 — Performance comparée aux repères publics**, pondérés par la répartition réelle de chaque contrat.
- **2026-11-22 — Feuille de route en six étapes** : fondations, mises à jour sans effort, PEA, connexion directe,
  pilotage, IA et confort. Le module « Allocation et arbitrage » peut remonter si le titulaire le demande.
- **2026-11-22 — Connexion directe par Enable Banking.** GoCardless Bank Account Data (ex-Nordigen) n'accepte plus
  de nouveaux inscrits ; Enable Banking propose un mode restreint gratuit pour un usage personnel sur ses propres
  comptes, déjà utilisé par Firefly III, Actual et Finanze. La DSP2 ne couvre que les comptes de paiement : assurances
  vie, PER, PERP et crédits restent sur fichiers et calcul. L'accord bancaire est à renouveler tous les 180 jours.
- **2026-11-22 — Trade Republic par l'export CSV de l'application** (disponible depuis avril 2026), pytr en secours.
- **2026-11-22 — Agrégateurs en ligne écartés** (Finary, Zenmoney…) : données hors de la machine et abonnement.
  Aucun plugin ou skill du catalogue ne couvre la gestion de patrimoine locale.
- **2026-11-22 — Pas de conseil personnalisé.** metabank donne répartition, frais, fiscalité, performances comparées
  et simulations ; la décision d'arbitrage revient au titulaire ou à un conseiller indépendant rémunéré en honoraires.
- **2026-11-22 — Application web locale plutôt que Wealthfolio** comme cœur de metabank (remplace la décision du
  2026-11-11) ; Wealthfolio reste disponible pour un portefeuille boursier détaillé.
- **2026-11-22 — metabank devient l'application chapeau.** Il réutilise les projets existants quand ils conviennent
  et garde son propre tableau de bord, seul à montrer les frais cachés et les rétrocessions lus dans les relevés.
- **2026-11-22 — Les contrats « BNP » sont en fait chez Suravenir (via Vie Plus) et Cardif.** Suravenir ne fournit
  que des relevés annuels PDF (pas de dates d'opérations) : rendement annuel estimé par Dietz modifié (docs/MODELE.md).
- **2026-11-22 — BNP en premier.** Assurances vie et PER portent les plus gros montants et les plus longs historiques.
- **2026-11-11 — BNP via woob abandonné.** Le pare-feu Akamai de mabanque.bnpparibas refuse woob dès la première
  requête ; on ne contourne pas une protection anti-robot de sa banque. Le connecteur woob reste dans l'historique
  git (commit 37e319d).
- **2026-11-11 — Wealthfolio plutôt qu'un tableau de bord maison** (remplacée le 2026-11-22).

## Suggestions retenues

| Suggestion | Étape | État |
|---|---|---|
| Frais annuels en euros par enveloppe comme indicateur principal | — | fait (`metabank bilan`, `metabank frais`) |
| Frais cachés des supports et rétrocessions, simulation de supports moins chers | — | fait (`metabank frais`) |
| Application web locale : tableau de bord, dépôt de relevés, corrections, simulation, assistant Claude | — | fait (`metabank web`) |
| Export PDF de tout ou partie des synthèses (une page A4 par vue, prénoms masquables) | — | fait |
| Comptes bancaires BNP (courant, locatif, Livret A, LDD) : budget, dépenses par catégorie, frais, argent qui dort | — | fait |
| Crédits immobiliers : capital restant dû, taux, fin et intérêts restants estimés ; patrimoine net avec valeur des biens | — | fait |
| Patrimoine complet et synthèse de l'épargne dans le tableau de bord ; onglet Budget | — | fait |
| Base SQLite reconstruisible depuis les archives brutes | 1 | fait |
| Connecteurs (plug-ins) fichier, direct, calcul, référence ; registre et journal | 1 | fait (contrat, registre, journal ; aucun connecteur réel encore) |
| Onglet Configuration (comptes, connecteurs, dossiers, paramètres) | 1 | à faire |
| Onglet Synoptique (accès, réseau, fraîcheur, journal) | 1 | à faire |
| Dépôt unique avec rangement automatique et dossier surveillé | 2 | à faire |
| Historique et courbe du patrimoine net | 2 | à faire |
| Performance comparée aux repères publics (fonds en euros, unités de compte, indices, Livret A, inflation) | 2, 5 | à faire |
| Règles de classement des dépenses modifiables depuis la page | 2 | à faire |
| PEA Trade Republic : positions, plafond, compteur des 5 ans | 3 | à faire |
| Connexion directe DSP2 (Enable Banking) et rappel des 180 jours | 4 | à faire |
| Mise à jour automatique des comptes en connexion directe (synchronisation planifiée) | 4 | à faire |
| Valeur au jour des contrats par les valeurs liquidatives publiques (option) | 4 | à faire |
| Allocation globale, alertes de concentration, simulateur d'arbitrage, répartition cible | 5 | à faire |
| Alerte quand une enveloppe dérive de l'allocation cible au-delà d'un seuil | 5 | à faire |
| Rééquilibrage par les versements (sans vente) plutôt que par arbitrage | 5 | à faire |
| Compteurs fiscaux : 5 ans du PEA, 8 ans de l'assurance vie, plafond PER, gratuité des transferts | 5 | à faire |
| Projection retraite : capital à l'échéance selon plusieurs hypothèses | 5 | à faire |
| Crédits : remboursement anticipé ou placement, assurance emprunteur | 5 | à faire |
| Bien locatif : rendement et trésorerie | 5 | à faire |
| Serveur MCP local en lecture seule pour l'assistant | 6 | à faire |
| Revue mensuelle automatique (PDF et liste d'actions) | 6 | à faire |
| Sauvegarde chiffrée de `data/` sur le NAS | 6 | à faire |
| Exécution sur le NAS QNAP comme metascrap (crontab, sans git, réseau local authentifié) | 6 | à faire |

## Sources consultées (2026-11-22)
- [GoCardless : nouvelles inscriptions fermées](https://bankaccountdata.gocardless.com/new-signups-disabled)
- [Open Banking Tracker : API gratuites en 2026](https://www.openbankingtracker.com/guides/free-open-banking-apis)
- [Enable Banking : comptes liés en mode restreint](https://enablebanking.com/docs/api/linked-accounts/) et
  [spécificités françaises](https://enablebanking.com/docs/markets/fr/)
- [Firefly III : mise en place d'Enable Banking](https://docs.firefly-iii.org/tutorials/data-importer/eb/)
- [Export CSV Trade Republic](https://acutic.io/blog/trade-republic-csv-export)
- [AMF : PEA et premier versement](https://www.amf-france.org/fr/le-mediateur/journal-de-bord-du-mediateur/dossiers-du-mois/pea-et-pea-pme-limportance-du-premier-versement-pour-valider-la-date-douverture)
- [Transfert d'un PERP vers un PER](https://www.lesclesdelabanque.com/particulier/transformer-perp-en-per/)
- [EBA : exemption d'authentification portée à 180 jours](https://www.eba.europa.eu/eba-publishes-final-report-amendment-its-technical-standards-exemption-strong-customer)
- Repères de performance : [fonds en euros 2025 (ACPR, Moneyvox)](https://www.moneyvox.fr/assurance-vie/actualites/108096/le-taux-moyen-reste-a-2-63-en-2025-comme-en-2024-selon-acpr),
  [unités de compte 2024-2025 (France Assureurs)](https://www.toutsurmesfinances.com/actualites/?p=629),
  [unités de compte 2023 (France Assureurs)](https://www.boursedirect.fr/fr/actualites/categorie/placements/assurance-vie-les-uc-ont-brille-l-an-dernier-bourse-direct-7fb9b8dfe00ac50f809c3d60e2c2ba26ea2ebc7b),
  [inflation (Insee)](https://www.insee.fr/en/statistiques/8726604),
  [taux du Livret A (economie.gouv.fr)](https://www.economie.gouv.fr/actualites/epargne-reglementee-de-nouveaux-taux-pour-le-livret-et-le-lep-au-1er-fevrier-2026)
