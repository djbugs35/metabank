"""Patrimoine complet du foyer et de chaque personne : placements, épargne disponible, comptes courants. MODELE § 8."""

from decimal import Decimal

from metabank.banque.modele import TYPES_COURANTS, Compte
from metabank.bilan import BilanContrat
from metabank.rapport import nom_contrat

ZERO = Decimal(0)
PLACEMENTS, EPARGNE, COURANTS = "Placements", "Épargne disponible", "Comptes courants"
FAMILLES = (PLACEMENTS, EPARGNE, COURANTS)
EXPLICATIONS = {
    PLACEMENTS: "assurance vie, PER, PERP : valeur au dernier relevé",
    EPARGNE: "Livret A, LDD : disponible à tout moment",
    COURANTS: "solde au dernier export",
}


def patrimoines(bilans: list[BilanContrat], comptes: list[Compte]) -> dict[str, dict]:
    """Rendre le patrimoine du foyer (clé « foyer ») et de chaque personne (clé « p:<prénom> »)."""
    lignes = [(b.titulaire, PLACEMENTS, nom_contrat(b), b.valeur, b.date_valeur.isoformat()) for b in bilans]
    lignes += [
        (
            c.titulaire,
            COURANTS if c.type_compte in TYPES_COURANTS else EPARGNE,
            c.libelle,
            c.solde,
            c.date_solde.isoformat(),
        )
        for c in comptes
    ]
    resultat = {"foyer": _patrimoine(lignes)}
    for titulaire in sorted({ligne[0] for ligne in lignes}):
        resultat[f"p:{titulaire}"] = _patrimoine([ligne for ligne in lignes if ligne[0] == titulaire])
    return resultat


def _patrimoine(lignes: list[tuple]) -> dict:
    """Rendre total, familles et lignes, chaque montant en euros avec sa part du total (fraction)."""
    total = sum((ligne[3] for ligne in lignes), ZERO)

    def part(montant: Decimal) -> float | None:
        return round(float(montant / total), 6) if total else None

    familles = []
    for famille in FAMILLES:
        montant = sum((ligne[3] for ligne in lignes if ligne[1] == famille), ZERO)
        if montant:
            familles.append({"famille": famille, "montant": round(float(montant), 2), "part": part(montant),
                             "explication": EXPLICATIONS[famille]})  # fmt: skip
    return {
        "total": round(float(total), 2),
        "familles": familles,
        "lignes": [
            {"titulaire": t, "famille": f, "nom": nom, "valeur": round(float(v), 2), "part": part(v), "date": jour}
            for t, f, nom, v, jour in sorted(lignes, key=lambda ligne: (FAMILLES.index(ligne[1]), -ligne[3]))
        ],
    }
