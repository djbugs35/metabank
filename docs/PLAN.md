# metabank — plan

## But
Voir et analyser tout le patrimoine financier (comptes courants, assurance vie, PER, PEA), en local,
sans abonnement (hors le compte Claude déjà payé). **Lecture seule : aucun ordre n'est jamais passé.**

## Architecture

```
 Sources                      Alimentation (metabank)              Wealthfolio (local)          IA
 ───────                      ───────────────────────              ───────────────────          ──
 Trade Republic (PEA, CC) ─── pytr → convertisseur CSV ─┐
 Revolut                  ─── export CSV → convertisseur ┼──► import CSV ─► base SQLite ─► rapport Claude
 BNP (courant, AV, PER)   ─── saisie 2 à 4 fois par an ─┘     tableau de bord,          (claude -p sur un
                                                                performance, allocation   extrait chiffré)
```

- **Wealthfolio** ([wealthfolio/wealthfolio](https://github.com/wealthfolio/wealthfolio), AGPL-3.0) fait le stockage,
  le tableau de bord et les calculs de performance (pondérée dans le temps et par les flux). On ne le modifie pas :
  on le déploie (`compose.yml`) et on l'alimente.
- **metabank** ne contient que ce que Wealthfolio n'a pas : déploiement, convertisseurs vers son import CSV,
  analyse et arbitrage propres à la fiscalité française, rapport IA.
- L'abonnement Wealthfolio Connect (synchronisation de courtiers) n'est pas utilisé : il ne couvre ni Trade Republic
  ni BNP à notre connaissance.

## Jalons

| # | Jalon | Contenu | État |
|---|---|---|---|
| 1 | Déploiement | `compose.yml`, `.env` généré (mot de passe Argon2id, clé secrète), lancement Mac ; NAS ensuite | à tester sur le Mac |
| 2 | Prise en main | créer les comptes (PEA, CTO, courants, AV, PER), saisir quelques opérations, choisir comment représenter fonds euros et unités de compte | à faire |
| 3 | Format d'import | relever le format CSV attendu par Wealthfolio sur un export réel (colonnes, types d'opérations, devises) | à faire |
| 4 | Trade Republic | convertisseur pytr → CSV Wealthfolio (achats, ventes, dépôts, dividendes, intérêts, frais), sans doublon d'un import à l'autre | à faire |
| 5 | Revolut | convertisseur de l'export CSV Revolut | à faire |
| 6 | BNP | gabarit de saisie AV / PER (valorisation par support) ; aide à la lecture des relevés PDF | à faire |
| 7 | Analyse et arbitrage | frais annuels en euros par enveloppe, comparaison AV / PER / PEA, destination du prochain versement, compteurs fiscaux | à faire |
| 8 | Rapport IA | synthèse mensuelle via `claude -p` sur un extrait chiffré (sans identifiant) | à faire |
| 9 | NAS | même `compose.yml` sur le QNAP (Container Station), accès réseau local, sauvegarde de `data/` | à faire |

## Décisions prises
- **2026-11-11 — BNP via woob abandonné.** Le pare-feu Akamai de mabanque.bnpparibas refuse woob dès la première
  requête ; on ne contourne pas une protection anti-robot de sa banque. BNP passe par saisie (jalon 6).
  Le connecteur woob reste dans l'historique git (commit 37e319d) si un jour il redevient utile.
- **2026-11-11 — Wealthfolio plutôt qu'un tableau de bord maison.** Local, gratuit, déjà solide sur la performance ;
  metabank se concentre sur l'alimentation et l'analyse.

## Suggestions retenues

| Suggestion | Jalon | État |
|---|---|---|
| Frais annuels en euros par enveloppe comme indicateur principal | 7 | à faire |
| Alerte quand une enveloppe dérive de l'allocation cible au-delà d'un seuil | 7 | à faire |
| Compteurs fiscaux : date des 5 ans du PEA, des 8 ans de l'assurance vie | 7 | à faire |
| Rééquilibrage par les versements (sans vente) plutôt que par arbitrage | 7 | à faire |
| Projection retraite : capital à l'échéance selon plusieurs hypothèses de rendement | 7 | à faire |
| Sauvegarde automatique de `data/` (base Wealthfolio) sur le NAS | 9 | à faire |
