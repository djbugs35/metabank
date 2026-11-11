# metabank

Vision globale et analyse de mon patrimoine financier — comptes courants, assurances vie, PER, PEA —
en local, sans abonnement, avec l'aide de l'IA pour la synthèse. **Lecture seule : aucun ordre n'est jamais passé.**

Plan et jalons : [docs/PLAN.md](docs/PLAN.md). Format des données : [docs/FORMATS.md](docs/FORMATS.md).

## Installer

macOS : double-clic sur `installer.command` (ou `./installer.command`). Windows : `installer.bat`.

L'installeur :
1. installe uv s'il manque, puis les dépendances (`uv sync`) ;
2. télécharge les modules woob (`uv run woob config update`) ;
3. propose de déclarer l'accès BNP (`uv run woob config add bnporc`) : identifiant, mot de passe,
   site « pp » (particuliers). Ces identifiants restent dans `~/.config/woob/backends`, jamais dans ce dépôt ;
   l'installeur restreint ce fichier à votre seul compte (droits 600).

## Premier inventaire

```sh
uv run woob bank list -b bnporc
uv run python -m metabank inventaire --interactif
```

La première commande vérifie que woob voit les comptes BNP ; la seconde collecte et écrit l'instantané.

`--interactif` autorise un code SMS ou une validation sur l'application BNP : à utiliser quand vous êtes devant
l'écran. Sans cette option (tâche planifiée), la collecte s'arrête proprement et dit de relancer en interactif.

La commande affiche chaque compte (type, libellé, quatre derniers chiffres, solde, nombre de supports) et écrit
un instantané daté dans `data/instantanes/`, ignoré par git.

## Développer

```sh
uv run pytest -q
uv run ruff check metabank tests && uv run ruff format metabank tests
```

Consignes du projet : [CLAUDE.md](CLAUDE.md).
