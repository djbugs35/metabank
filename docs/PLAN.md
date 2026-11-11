# metabank — plan

## But
Un seul outil, en local et sans abonnement (hors le compte Claude déjà payé), pour :
1. **voir** tout le patrimoine financier au même endroit : comptes courants, livrets, assurances vie, PER, PEA, CTO ;
2. **mesurer** le gain réel de chaque enveloppe : performance nette des apports, frais payés en euros, fiscalité ;
3. **comparer et arbitrer** entre assurance vie, PER et PEA : où placer le prochain euro, quel support coûte trop cher ;
4. **lire** le tout dans un tableau de bord graphique, avec une synthèse rédigée par l'IA.

metabank **ne passe jamais d'ordre** : ni virement, ni achat, ni arbitrage. Il lit, calcule et propose ; je décide.

## Architecture en quatre couches

```
 Sources                 Collecte                 Entrepôt                 Analyse            Restitution
 ───────                 ────────                 ────────                 ───────            ───────────
 BNP (courant, AV, PER) ─ woob (bnp) ─┐
 Trade Republic (PEA)   ─ pytr          ─┼─► instantanés JSON ─► SQLite ─► Python pur ─┬─► tableau de bord local
 Revolut                ─ export CSV    ─┤   (bruts, datés)      (historique) (testé)   └─► rapport Claude (claude -p)
 Autres / manquants     ─ saisie CSV    ─┘
```

- **Collecte** (`metabank/connecteurs/`) : un module par source, qui traduit vers `metabank/modele.py`.
  Les identifiants restent dans l'outil de chaque source (configuration woob, `~/.pytr/`), jamais dans le dépôt.
- **Entrepôt** : chaque collecte écrit un instantané JSON brut daté (`data/instantanes/`, format dans
  docs/FORMATS.md) ; une base SQLite historisée est reconstruite à partir d'eux. Un instantané n'est jamais modifié.
- **Analyse** (`metabank/analyse/`, à venir) : Python pur, sans réseau, testé contre des cas calculés à la main.
  Les chiffres viennent toujours d'ici, **jamais du modèle de langage**.
- **Restitution** : tableau de bord local (graphiques, valeur exacte au survol) et rapport mensuel rédigé par Claude
  à partir d'un JSON de synthèse — Claude ne voit ni identifiants ni numéros de compte.

## Jalons

| # | Jalon | Contenu | État |
|---|---|---|---|
| 1 | Squelette + woob | dépôt, conventions, modèle commun, collecte BNP via woob, instantané JSON | fait |
| 2 | Premier inventaire réel | `woob config add bnp`, collecte sur mes vrais comptes, ajuster la traduction (types, fonds euros) | bloqué (voir ci-dessous) |
| 2 bis | BNP par relevés | lecture des relevés PDF d'assurance vie et de PER téléchargés depuis l'espace client ; repli CSV trimestriel | à faire |
| 3 | Trade Republic | connecteur pytr (positions et flux du PEA) ; tester d'abord si woob a un module Trade Republic | à faire |
| 4 | Revolut + saisie manuelle | lecture de l'export CSV Revolut ; CSV de saisie pour ce qu'aucun connecteur n'atteint | à faire |
| 5 | Entrepôt SQLite | historique des valorisations et des flux, reconstruit depuis les instantanés | à faire |
| 6 | Analyse | valeur, allocation par classe d'actif, frais annuels en euros, TRI (XIRR) par enveloppe, gain réel net des apports | à faire |
| 7 | Arbitrage | comparaison AV / PER / PEA (frais, fiscalité, horizon), destination du prochain versement, supports trop chers | à faire |
| 8 | Tableau de bord | page locale : évolution, allocation, frais, performance par enveloppe | à faire |
| 9 | Rapport IA | synthèse mensuelle via `claude -p` sur le JSON d'analyse | à faire |
| 10 | Planification | collecte et rapport automatiques (NAS ou PC), avec repli quand une banque demande une validation | à faire |

## Décisions prises
- **2026-11-11 — BNP via woob bloqué.** Le pare-feu Akamai de mabanque.bnpparibas répond « Access Denied »
  (référence errors.edgesuite.net) dès la première requête de woob, avant toute connexion. On ne contourne pas
  une protection anti-robot de sa banque : BNP passe par ses relevés (jalon 2 bis). Le connecteur woob reste,
  pour d'autres établissements ou si le module redevient utilisable ; un ticket peut être ouvert chez woob.

## Décisions à prendre
- **Tableau de bord** : page statique servie en local comme Égide (bibliothèque de graphiques copiée dans `vendor/`)
  ou Streamlit (plus rapide à écrire, moins personnalisable). Proposition : page statique, par cohérence.
- **Où tourne la collecte planifiée** : PC ou NAS. La double authentification BNP impose parfois une validation
  sur téléphone : la collecte planifiée doit savoir s'arrêter proprement et me prévenir.

## Suggestions retenues

| Suggestion | Jalon | État |
|---|---|---|
| Frais annuels en euros par enveloppe comme indicateur principal | 6 | à faire |
| Alerte quand une enveloppe dérive de l'allocation cible au-delà d'un seuil | 6 | à faire |
| Compteurs fiscaux : date des 5 ans du PEA, des 8 ans de l'assurance vie | 7 | à faire |
| Rééquilibrage par les versements (sans vente) plutôt que par arbitrage | 7 | à faire |
| Projection retraite : capital à l'échéance selon plusieurs hypothèses de rendement | 7 | à faire |
