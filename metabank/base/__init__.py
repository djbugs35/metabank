"""Base locale data/metabank.db (SQLite), reconstruisible à tout moment depuis les archives brutes data/archives/.

- `archives` : les fichiers entrés, gardés tels quels ; source de vérité.
- `schema` : tables et migrations, appliquées à l'ouverture.
- `lot` : ce qu'un connecteur rend, prêt à entrer en base.
- `integration` : importer un fichier, reconstruire la base.
- `montants` : centimes entiers en base, `Decimal` partout ailleurs.

Ce que le titulaire saisit (corrections, règles de classement, registre des comptes) ne vient pas des archives :
il reste dans ses propres fichiers de data/, hors de la base, pour qu'effacer la base ne perde rien.
"""
