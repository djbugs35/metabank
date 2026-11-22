"""Export des opérations BNP Paribas (« Télécharger mes opérations », format CSV).

Forme relevée sur un vrai export (novembre 2026), séparateur « ; », sans guillemets :
  ligne 1 : nom du compte ; nom du compte ; ****2513 ; date du solde (JJ/MM/AAAA) ; ; solde
  ensuite : date ; type (« PAIEMENT CB ») ; sous-type (« FACTURE CARTE ») ; libellé ; montant (« -117,70 »)
Le type et le sous-type sont parfois vides (remboursement par carte). Tout écart devient une erreur, jamais un zéro.
"""

import csv
import io
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from metabank.banque.modele import Export, Operation

NUMERO_MASQUE = re.compile(r"^\*+\d{3,6}$")


class ExportIllisible(ValueError):
    """Le fichier n'a pas la forme d'un export BNP : le message dit à quelle ligne."""


def decoder(contenu: bytes) -> str:
    """Rendre le texte du fichier : UTF-8 s'il l'est, sinon Windows-1252 (accents des exports bancaires)."""
    try:
        return contenu.decode("utf-8-sig")
    except UnicodeDecodeError:
        return contenu.decode("cp1252")


def est_export_bnp(texte: str) -> bool:
    """Rendre vrai si la première ligne a la forme d'un en-tête d'export BNP."""
    premiere = texte.lstrip().split("\n", 1)[0].split(";")
    return len(premiere) >= 6 and bool(NUMERO_MASQUE.match(premiere[2].strip())) and _est_date(premiere[3])


def lire_export_bnp(texte: str, fichier: str = "") -> Export:
    """Rendre l'export lu : solde à sa date et opérations, du plus ancien au plus récent.

    Raises:
        ExportIllisible: en-tête absent, date ou montant illisible, ligne d'un autre format.
    """
    if not est_export_bnp(texte):
        raise ExportIllisible(f"{fichier} : en-tête d'export BNP non reconnu")
    lignes = [ligne for ligne in csv.reader(io.StringIO(texte), delimiter=";") if any(c.strip() for c in ligne)]
    entete = lignes[0]
    operations = []
    for rang, ligne in enumerate(lignes[1:], start=2):
        if len(ligne) != 5:
            raise ExportIllisible(f"{fichier} : ligne {rang}, {len(ligne)} champs au lieu de 5")
        jour, type_banque, sous_type, libelle, montant = (champ.strip() for champ in ligne)
        operations.append(Operation(_date(jour, fichier, rang), type_banque, sous_type,
                                    re.sub(r"\s+", " ", libelle), _montant(montant, fichier, rang)))  # fmt: skip
    operations.sort(key=lambda o: o.jour)
    return Export(
        nom=entete[0].strip(),
        numero_masque=entete[2].strip(),
        date_solde=_date(entete[3], fichier, 1),
        solde=_montant(entete[5], fichier, 1),
        operations=tuple(operations),
        fichier=fichier,
    )


DATE = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")


def _en_date(texte: str) -> date | None:
    trouve = DATE.match(texte.strip())
    if not trouve:
        return None
    try:
        return date(int(trouve.group(3)), int(trouve.group(2)), int(trouve.group(1)))
    except ValueError:
        return None


def _est_date(texte: str) -> bool:
    return _en_date(texte) is not None


def _date(texte: str, fichier: str, rang: int) -> date:
    jour = _en_date(texte)
    if jour is None:
        raise ExportIllisible(f"{fichier} : ligne {rang}, date illisible « {texte} »")
    return jour


def _montant(texte: str, fichier: str, rang: int) -> Decimal:
    propre = re.sub(r"[\s\u00a0\u202f]", "", texte).replace(",", ".")
    try:
        return Decimal(propre)
    except InvalidOperation as erreur:
        raise ExportIllisible(f"{fichier} : ligne {rang}, montant illisible « {texte} »") from erreur
