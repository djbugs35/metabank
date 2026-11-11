# Formats

## Instantané (`data/instantanes/AAAA-MM-JJ_HHMM_<source>.json`)

Photo de tous les comptes d'une source à un instant. Écrit par `metabank/instantane.py`, jamais modifié ensuite.

```json
{
  "format": 1,
  "source": "woob",
  "date_collecte": "2026-11-11T15:30:00+01:00",
  "comptes": [
    {
      "source": "woob:bnp",
      "identifiant": "bnp:<id woob>",
      "libelle": "Multiplacements 2",
      "type_compte": "assurance_vie",
      "solde": "15234.56",
      "devise": "EUR",
      "numero_masque": "…5678",
      "lignes": [
        {
          "libelle": "Fonds actions monde",
          "valorisation": "8000.10",
          "isin": "FR0010315770",
          "quantite": "42.5",
          "valeur_unitaire": "188.24",
          "prix_revient_unitaire": null,
          "plus_value": null,
          "date_valeur": "2026-11-06"
        }
      ]
    }
  ]
}
```

- Montants en **texte** (décimaux exacts), dans la devise du compte ; `null` = inconnu de la source.
- `type_compte` : une valeur de `TYPES_COMPTE` (`metabank/modele.py`).
- `numero_masque` : quatre derniers caractères seulement ; ni numéro complet ni IBAN ne sont écrits.
- `isin` : rempli seulement si le code de la source a la forme d'un ISIN (un fonds en euros n'en a pas).
- `identifiant` contient l'identifiant interne de la source : le dossier `data/` ne quitte jamais la machine.
