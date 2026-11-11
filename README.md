# metabank

Vision globale et analyse de mon patrimoine financier — comptes courants, assurance vie, PER, PEA —
en local et sans abonnement. Le tableau de bord est [Wealthfolio](https://github.com/wealthfolio/wealthfolio)
(open source, données sur la machine) ; metabank le déploie et l'alimente. **Lecture seule : aucun ordre n'est jamais passé.**

Plan et jalons : [docs/PLAN.md](docs/PLAN.md).

## Lancer Wealthfolio

Prérequis sur Mac : Docker Desktop lancé, et deux outils :

```sh
brew install argon2 openssl
```

Puis double-clic sur `lancer.command`, ou :

```sh
./lancer.command
```

Au premier lancement, `outils/preparer_env.sh` demande un mot de passe pour Wealthfolio et crée `.env`
(clé secrète et empreinte du mot de passe, droits 600, jamais versionné). Wealthfolio s'ouvre ensuite sur
http://localhost:8088.

Arrêter :

```sh
./lancer.command arreter
```

## Où sont les données

Dans `data/` : la base Wealthfolio (`wealthfolio.db`) et ses secrets chiffrés. Ce dossier n'est jamais versionné :
c'est lui qu'il faut sauvegarder, avec le fichier `.env` (sans `WF_SECRET_KEY`, les secrets deviennent illisibles).

## Sur le NAS

Le même `compose.yml` tourne sous Container Station. Pour l'ouvrir au réseau local :

```sh
./outils/preparer_env.sh reseau
```

Consignes du projet : [CLAUDE.md](CLAUDE.md).
