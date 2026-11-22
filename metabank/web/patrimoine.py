"""Patrimoine du foyer et de chaque personne : actifs (placements, épargne, comptes, immobilier), crédits, net.

MODELE § 8.
"""

from decimal import Decimal

from metabank.banque.modele import TYPES_COURANTS, Compte
from metabank.bilan import BilanContrat
from metabank.rapport import nom_contrat

ZERO = Decimal(0)
PLACEMENTS, EPARGNE, COURANTS, IMMOBILIER = "Placements", "Épargne disponible", "Comptes courants", "Immobilier"
CREDITS = "Crédits"
FAMILLES = (PLACEMENTS, EPARGNE, COURANTS, IMMOBILIER)
EXPLICATIONS = {
    PLACEMENTS: "assurance vie, PER, PERP : valeur au dernier relevé",
    EPARGNE: "Livret A, LDD : disponible à tout moment",
    COURANTS: "solde au dernier export",
    IMMOBILIER: "valeur estimée saisie dans Corrections",
}


def patrimoines(bilans: list[BilanContrat], comptes: list[Compte], biens: dict | None = None) -> dict[str, dict]:
    """Rendre le patrimoine du foyer (clé « foyer ») et de chaque personne (clé « p:<prénom> »).

    Args:
        biens: {fin du numéro du crédit : {"nom", "valeur"}} saisis dans Corrections ; le bien appartient au
            titulaire du crédit.
    """
    biens = biens or {}
    lignes = [(b.titulaire, PLACEMENTS, nom_contrat(b), b.valeur, b.date_valeur.isoformat()) for b in bilans]
    for c in comptes:
        if c.type_compte == "credit":
            lignes.append((c.titulaire, CREDITS, c.libelle, c.solde, c.date_solde.isoformat()))
            bien = biens.get(c.numero_masque.lstrip("*"))
            if bien:
                nom = f"{c.titulaire} · {bien['nom']}"
                lignes.append((c.titulaire, IMMOBILIER, nom, Decimal(str(bien["valeur"])), c.date_solde.isoformat()))
        else:
            famille = COURANTS if c.type_compte in TYPES_COURANTS else EPARGNE
            lignes.append((c.titulaire, famille, c.libelle, c.solde, c.date_solde.isoformat()))
    resultat = {"foyer": _patrimoine(lignes)}
    for titulaire in sorted({ligne[0] for ligne in lignes}):
        resultat[f"p:{titulaire}"] = _patrimoine([ligne for ligne in lignes if ligne[0] == titulaire])
    return resultat


def _patrimoine(lignes: list[tuple]) -> dict:
    """Rendre actifs, crédits et net ; chaque part est rapportée au total des actifs (fraction)."""
    actifs = sum((ligne[3] for ligne in lignes if ligne[1] != CREDITS), ZERO)
    credits = -sum((ligne[3] for ligne in lignes if ligne[1] == CREDITS), ZERO)

    def part(montant: Decimal) -> float | None:
        return round(float(montant / actifs), 6) if actifs else None

    familles = []
    for famille in FAMILLES:
        montant = sum((ligne[3] for ligne in lignes if ligne[1] == famille), ZERO)
        if montant:
            familles.append({"famille": famille, "montant": round(float(montant), 2), "part": part(montant),
                             "explication": EXPLICATIONS[famille]})  # fmt: skip
    ordre = (*FAMILLES, CREDITS)
    return {
        "total": round(float(actifs), 2),
        "credits": round(float(credits), 2),
        "part_credits": part(credits),
        "net": round(float(actifs - credits), 2),
        "immobilier_saisi": any(ligne[1] == IMMOBILIER for ligne in lignes),
        "credits_sans_bien": any(ligne[1] == CREDITS for ligne in lignes)
        and not any(ligne[1] == IMMOBILIER for ligne in lignes),
        "familles": familles,
        "lignes": [
            {"titulaire": t, "famille": f, "nom": nom, "valeur": round(float(v), 2), "part": part(abs(v)), "date": jour}
            for t, f, nom, v, jour in sorted(lignes, key=lambda ligne: (ordre.index(ligne[1]), -abs(ligne[3])))
        ],
    }
