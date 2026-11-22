# metabank — plan

## But
Voir, comprendre et piloter **tout le patrimoine du foyer** : placements (assurance vie, PER, PERP, PEA), épargne
disponible (livrets), comptes courants, crédits et biens immobiliers. **Le plus simplement possible** : les mises à
jour arrivent par fichiers déposés ou, quand la banque le permet, par connexion directe ; ce qui peut se calculer
(crédits, intérêts attendus) n'a pas besoin d'import.

Contraintes permanentes :
- **Lecture seule** : aucun virement, ordre ni arbitrage n'est jamais passé par metabank.
- **En local, sans abonnement** (hors le compte Claude déjà payé) ; `data/` ne quitte pas la machine.
- **Chiffres calculés par du code testé**, formules écrites d'abord dans docs/MODELE.md ; l'IA commente, ne calcule pas.
- **Pas de recommandation personnalisée d'investissement** : metabank donne les faits (répartition, frais, fiscalité,
  simulations) ; la décision reste au titulaire, ou à un conseiller indépendant rémunéré en honoraires.

## Architecture : metabank, application chapeau

```
 Sources                         Collecte                               Socle metabank                 Restitution
 ───────                         ────────                               ──────────────                 ───────────
 Suravenir, Cardif (PDF)    ──┐
 BNP : exports CSV          ──┼─ dépôt unique (page ou dossier surveillé) ─┐
 Trade Republic (CSV appli) ──┘  reconnaissance source/compte/titulaire    │
                                                                           ├─► modèle unique ─► analyses ─┬─► application web locale
 BNP comptes, Revolut       ──── connexion directe DSP2 (Enable Banking) ──┤   contrôles        (patrimoine,├─► rapports PDF
 Crédits, intérêts livrets  ──── calcul (amortissement, taux réglementés) ─┘   historique       budget,    └─► Claude : assistant et
 Valeurs liquidatives, cours ─── source publique (option, ISIN seulement)       (base locale)   frais,          serveur MCP local
                                                                                                 arbitrage)      (lecture seule)
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

## Déjà en place (novembre 2026)

| Domaine | Contenu |
|---|---|
| Relevés d'assureurs | lecture des relevés annuels Suravenir et des situations Cardif ; contrôles de cohérence ; corrections saisies |
| Placements | versé, valeur, gagné et frais par année et depuis l'ouverture ; rentabilité annualisée ; frais fonds par fonds et rétrocessions |
| Application web | `metabank web` : tableau de bord (foyer, personne, contrat), relevés, corrections, simulation des frais, assistant Claude, export PDF |
| Comptes BNP | exports CSV des comptes courants, compte locatif, Livret A et LDD : budget du foyer, dépenses par catégorie, frais bancaires, argent qui dort, intérêts et plafonds des livrets |
| Crédits | capital restant dû, taux, mensualité, fin et intérêts restants estimés ; lien avec les échéances prélevées |
| Patrimoine | actifs par famille, crédits, patrimoine net avec la valeur des biens saisie ; synthèse de l'épargne disponible |

## Feuille de route

Ordre retenu le 2026-11-22 : de la simplicité d'usage vers le pilotage. Chaque étape est livrable seule.

### Étape 1 — Mises à jour sans effort

| Fonction | Détail | Fait quand | État |
|---|---|---|---|
| Dépôt unique | PDF et CSV glissés dans la page ou posés dans un dossier surveillé ; banque, compte et titulaire reconnus au contenu ; rangement et dédoublonnage automatiques ; plus aucun dossier à créer à la main | un fichier quelconque est rangé au bon endroit sans intervention | à faire |
| Registre des comptes | liste des comptes (titulaire, type, établissement, numéro masqué, source, fréquence attendue) modifiable dans la page ; remplace le sens porté par les noms de dossiers | les comptes existants y figurent et se corrigent depuis la page | à faire |
| Page « Mises à jour » | date de dernière mise à jour par compte, retards, prochaines échéances (relevé annuel en février…), mode d'emploi pour récupérer chaque fichier | chaque compte affiche sa fraîcheur | à faire |
| Crédits tenus à jour | capital restant dû projeté chaque mois depuis l'amortissement, sans réimport | le capital affiché suit le mois en cours | à faire |
| Historique du patrimoine | instantané à chaque mise à jour ; 13 derniers mois reconstitués depuis les exports ; courbe du patrimoine net | courbe mensuelle visible au tableau de bord | à faire |
| Règles de dépenses dans la page | créer, modifier, tester une règle de classement sans éditer `data/categories.json` | une dépense non classée se classe en deux clics | à faire |

### Étape 2 — PEA

| Fonction | Détail | Fait quand | État |
|---|---|---|---|
| Import Trade Republic | export CSV de l'application (Profil > Relevés > Export des transactions), relevé sur un vrai fichier avant d'écrire le lecteur | les opérations des deux PEA sont lues sans doublon | à faire |
| Positions et performance | lignes, prix de revient, plus-values latentes, dividendes, frais ; rentabilité annualisée | le PEA apparaît au tableau de bord comme les autres placements | à faire |
| Règles du PEA | versements face au plafond de 150 000 € ; compteur des 5 ans à partir du premier versement | plafond restant et date des 5 ans affichés | à faire |
| Cours | source publique en option (seuls les ISIN sortent), sinon saisie de la valeur | valeur au jour disponible, l'option désactivée par défaut | à faire |

### Étape 3 — Connexion directe

| Fonction | Détail | Fait quand | État |
|---|---|---|---|
| Enable Banking | application en mode restreint au nom du titulaire, clé privée dans le trousseau macOS, comptes BNP (et Revolut si couvert) liés ; l'export CSV reste en secours | les comptes courants se mettent à jour d'un clic | à faire |
| Renouvellement | rappel avant l'échéance de l'accord bancaire (180 jours) | rappel affiché dans la page « Mises à jour » | à faire |
| Livrets | vérifier si la BNP les expose en DSP2 (a priori non : ce ne sont pas des comptes de paiement) ; sinon export annuel | décision notée ci-dessous | à faire |
| Valeur au jour des contrats | parts × valeur liquidative publique des fonds + versements depuis le relevé, en option ; ou saisie rapide de la valeur lue sur l'espace client | assurance vie et PER affichent une valeur estimée datée | à faire |
| Téléchargement assisté | récupération guidée des relevés Suravenir, Cardif et Trade Republic dans le navigateur, titulaire présent | un relevé se récupère sans chercher où il est | à évaluer |

### Étape 4 — Pilotage

| Fonction | Détail | Fait quand | État |
|---|---|---|---|
| Allocation et arbitrage | classement de chaque fonds par type (obligations, actions, non coté, structurés, fonds en euros, or, immobilier, liquidités) d'après son ISIN et sa fiche DIC ; vue globale toutes enveloppes ; alertes de concentration (fonds, secteur) ; comparaison des frais avec les autres supports du contrat ; **simulateur d'arbitrage** (montant, fonds de départ et d'arrivée, frais annuels, coût fiscal, effet à 15 ans) ; **répartition cible fixée par le titulaire** et rééquilibrage par les versements ; fiche de préparation des rendez-vous avec le conseiller. Faits et simulations seulement, aucune recommandation | la répartition globale et une simulation d'arbitrage sont visibles | à faire |
| Fiscalité et échéances | 5 ans des PEA, 8 ans des assurances vie, abattement annuel après 8 ans, plafond de déduction PER saisi depuis l'avis d'impôt face aux versements de l'année, frais de transfert PER et PERP et leur date de gratuité, rappels de fin d'année | chaque échéance a sa date et son rappel | à faire |
| Projection retraite | capital estimé à l'âge de départ selon plusieurs hypothèses de rendement, de versements et d'inflation ; sortie en capital ou en rente | trois scénarios comparés | à faire |
| Crédits | tableau d'amortissement ; rembourser par anticipation ou placer ; coût de l'assurance emprunteur | comparaison chiffrée disponible | à faire |
| Bien locatif | loyers, charges, prêt, intérêts : rendement brut et net, trésorerie mensuelle | rendement et trésorerie affichés | à faire |
| Budget | abonnements récurrents repérés, objectif par catégorie, comparaison d'une année sur l'autre | dépassements signalés | à faire |

### Étape 5 — IA et confort

| Fonction | Détail | Fait quand | État |
|---|---|---|---|
| Serveur MCP local | metabank expose en lecture seule ses chiffres et ses simulations ; Claude les interroge au lieu de recevoir un résumé figé | une question obtient une réponse chiffrée par metabank | à faire |
| Revue mensuelle | PDF et courte liste d'actions (fichiers à déposer, échéances, alertes) | revue produite chaque mois | à faire |
| Base locale | historique et journal des imports en SQLite, schéma versionné | les instantanés survivent aux réimports | à faire |
| Sauvegarde | copie chiffrée de `data/` sur le NAS | restauration testée | à faire |
| Accès à la maison | application servie par le NAS sur le réseau local, avec authentification | accessible depuis le téléphone à la maison | à évaluer |
| Autres comptes | Revolut, compte-titres d'entreprise, relevés annuels Cardif | chacun lu ou saisi | à faire |

## Jalons passés

| # | Jalon | État |
|---|---|---|
| 1 | Déploiement de Wealthfolio (`compose.yml`, `.env`) | conservé, mis de côté |
| 2-5 | Prise en main et convertisseurs vers Wealthfolio (Trade Republic, Revolut) | remplacés par les étapes 2 et 5 |
| 6 | Relevés d'assureurs, bilan par contrat, frais support par support | fait |
| 7 | Analyse et arbitrage | frais faits ; le reste devient l'étape 4 |
| 7 bis | Tableau de bord, puis application web locale, export PDF | fait |
| 8 | Comptes BNP, budget, livrets, crédits, patrimoine net | fait ; rapport IA mensuel repris en étape 5 |
| 9 | NAS | repris en étape 5 |

## Décisions prises
- **2026-11-22 — Feuille de route en cinq étapes** : mises à jour sans effort, PEA, connexion directe, pilotage,
  IA et confort. Le module « Allocation et arbitrage » peut remonter si le titulaire le demande.
- **2026-11-22 — Connexion directe par Enable Banking.** GoCardless Bank Account Data (ex-Nordigen) n'accepte plus
  de nouveaux inscrits ; Enable Banking propose un mode restreint gratuit pour un usage personnel sur ses propres
  comptes, déjà utilisé par Firefly III, Actual et Finanze. La DSP2 ne couvre que les comptes de paiement : assurances
  vie, PER, PERP et crédits restent sur fichiers et calcul. L'accord bancaire est à renouveler tous les 180 jours.
- **2026-11-22 — Trade Republic par l'export CSV de l'application** (disponible depuis avril 2026), pytr en secours.
- **2026-11-22 — Agrégateurs en ligne écartés** (Finary, Zenmoney…) : données hors de la machine et abonnement.
  Aucun plugin ou skill du catalogue ne couvre la gestion de patrimoine locale.
- **2026-11-22 — Pas de conseil personnalisé.** metabank donne répartition, frais, fiscalité et simulations ; la
  décision d'arbitrage revient au titulaire ou à un conseiller indépendant rémunéré en honoraires.
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
| Dépôt unique avec rangement automatique, registre des comptes, page « Mises à jour » | 1 | à faire |
| Historique et courbe du patrimoine net | 1 | à faire |
| Règles de classement des dépenses modifiables depuis la page | 1 | à faire |
| PEA Trade Republic : positions, plafond, compteur des 5 ans | 2 | à faire |
| Connexion directe DSP2 (Enable Banking) et rappel des 180 jours | 3 | à faire |
| Valeur au jour des contrats par les valeurs liquidatives publiques (option) | 3 | à faire |
| Allocation globale, alertes de concentration, simulateur d'arbitrage, répartition cible | 4 | à faire |
| Alerte quand une enveloppe dérive de l'allocation cible au-delà d'un seuil | 4 | à faire |
| Rééquilibrage par les versements (sans vente) plutôt que par arbitrage | 4 | à faire |
| Compteurs fiscaux : 5 ans du PEA, 8 ans de l'assurance vie, plafond PER, gratuité des transferts | 4 | à faire |
| Projection retraite : capital à l'échéance selon plusieurs hypothèses | 4 | à faire |
| Crédits : remboursement anticipé ou placement, assurance emprunteur | 4 | à faire |
| Bien locatif : rendement et trésorerie | 4 | à faire |
| Serveur MCP local en lecture seule pour l'assistant | 5 | à faire |
| Revue mensuelle automatique (PDF et liste d'actions) | 5 | à faire |
| Base locale SQLite, sauvegarde chiffrée de `data/` sur le NAS | 5 | à faire |

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
