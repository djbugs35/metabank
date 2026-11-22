# metabank — plan

## But
Voir et analyser tout le patrimoine financier (comptes courants, assurance vie, PER, PEA), en local,
sans abonnement (hors le compte Claude déjà payé). **Lecture seule : aucun ordre n'est jamais passé.**

## Architecture : metabank, application chapeau

metabank est le point d'entrée unique. Il orchestre des projets existants quand ils font bien une partie du travail,
et ne code lui-même que ce qu'aucun ne fait (lecture des relevés d'assureurs, frais cachés, arbitrage à la française).

```
 Sources                    Collecte (connecteurs)            Socle metabank                 Restitution
 ───────                    ──────────────────────            ──────────────                 ───────────
 Suravenir, Cardif (PDF) ── lecteurs metabank ─────────┐
 Trade Republic (PEA)    ── pytr (projet externe) ─────┼──► modèle unique ─► analyses ──┬─► tableau de bord metabank
 Revolut                 ── export CSV ────────────────┘    contrôles        (bilan,     ├─► synthèse Claude (claude -p)
                                                            data/ (local)    frais,      └─► exports vers outils tiers
                                                                             arbitrage)      (Wealthfolio, Keep Your Folio…)
```

- **Projets externes utilisés ou envisagés** :
  - [pytr](https://github.com/pytr-org/pytr) : historique Trade Republic ;
  - [Wealthfolio](https://github.com/wealthfolio/wealthfolio) (AGPL-3.0, `compose.yml`) : suivi au cours du marché
    d'un portefeuille de titres cotés (PEA, CTO), le jour où il sera garni ;
  - [Keep Your Folio](https://keepyourfolio.fr/) (AGPL-3.0, local) : simulateurs fiscaux AV / PER / PEA, à évaluer.
- **Règle** : on n'intègre un projet externe que s'il garde les données en local ; on ne le modifie pas, on l'alimente
  par ses formats d'import ou on lit ses exports. Le modèle et les chiffres de référence restent ceux de metabank.

## Jalons

| # | Jalon | Contenu | État |
|---|---|---|---|
| 1 | Déploiement | `compose.yml`, `.env` généré (mot de passe Argon2id, clé secrète), lancement Mac ; NAS ensuite | à tester sur le Mac |
| 2 | Prise en main | créer les comptes (PEA, CTO, courants, AV, PER), saisir quelques opérations, choisir comment représenter fonds euros et unités de compte | à faire |
| 3 | Format d'import | relever le format CSV attendu par Wealthfolio sur un export réel (colonnes, types d'opérations, devises) | à faire |
| 4 | Trade Republic | convertisseur pytr → CSV Wealthfolio (achats, ventes, dépôts, dividendes, intérêts, frais), sans doublon d'un import à l'autre | à faire |
| 5 | Revolut | convertisseur de l'export CSV Revolut | à faire |
| 6 | Assurances vie et retraite (priorité) | lecteur des relevés annuels Suravenir et des situations Cardif, bilan par contrat (gain, rendement, frais), contrôles de cohérence, frais support par support | fait |
| 7 | Analyse et arbitrage | frais annuels en euros par enveloppe, comparaison AV / PER / PEA, destination du prochain versement, compteurs fiscaux | à faire |
| 7 bis | Tableau de bord | page locale générée par metabank : vue d'ensemble du foyer, évolution, frais visibles et cachés, répartition, pistes d'arbitrage | à faire |
| 8 | Rapport IA | synthèse mensuelle via `claude -p` sur un extrait chiffré (sans identifiant) | à faire |
| 9 | NAS | même `compose.yml` sur le QNAP (Container Station), accès réseau local, sauvegarde de `data/` | à faire |

## Décisions prises
- **2026-11-22 — metabank devient l'application chapeau.** Il réutilise les projets existants quand ils conviennent
  (pytr, Wealthfolio, Keep Your Folio à évaluer) et garde son propre tableau de bord, seul à montrer les frais cachés
  et les rétrocessions lus dans les relevés.
- **2026-11-22 — Les contrats « BNP » sont en fait chez Suravenir (via Vie Plus) et Cardif.** Suravenir ne fournit
  que des relevés annuels PDF (pas de dates d'opérations) : rendement annuel estimé par Dietz modifié (docs/MODELE.md).
- **2026-11-22 — BNP en premier.** Assurances vie et PER portent les plus gros montants et les plus longs historiques :
  le jalon 6 passe avant Trade Republic et Revolut. On part des vrais documents BNP déposés dans `data/bnp/`.
- **2026-11-11 — BNP via woob abandonné.** Le pare-feu Akamai de mabanque.bnpparibas refuse woob dès la première
  requête ; on ne contourne pas une protection anti-robot de sa banque. BNP passe par saisie (jalon 6).
  Le connecteur woob reste dans l'historique git (commit 37e319d) si un jour il redevient utile.
- **2026-11-11 — Wealthfolio plutôt qu'un tableau de bord maison.** Local, gratuit, déjà solide sur la performance ;
  metabank se concentre sur l'alimentation et l'analyse.

## Suggestions retenues

| Suggestion | Jalon | État |
|---|---|---|
| Frais annuels en euros par enveloppe comme indicateur principal | 7 | fait (`metabank bilan`, `metabank frais`) |
| Alerte quand une enveloppe dérive de l'allocation cible au-delà d'un seuil | 7 | à faire |
| Compteurs fiscaux : date des 5 ans du PEA, des 8 ans de l'assurance vie | 7 | à faire |
| Rééquilibrage par les versements (sans vente) plutôt que par arbitrage | 7 | à faire |
| Projection retraite : capital à l'échéance selon plusieurs hypothèses de rendement | 7 | à faire |
| Sauvegarde automatique de `data/` (base Wealthfolio) sur le NAS | 9 | à faire |
| Frais cachés des supports et rétrocessions, simulation de supports moins chers | 7 | fait (`metabank frais`) |
