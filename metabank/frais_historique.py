"""Frais depuis l'ouverture de chaque contrat : ceux du relevé (exacts) et ceux des fonds (estimés). MODELE § 5."""

from dataclasses import dataclass
from decimal import Decimal

from metabank.releves import ReleveRange
from metabank.releves.modele import Releve, cle_du_contrat

ZERO = Decimal(0)
CENT = Decimal(100)


@dataclass(frozen=True)
class AnneeFrais:
    """Frais d'une année civile d'un contrat, en euros."""

    annee: int
    frais_releve: Decimal
    frais_fonds: Decimal
    supports_taux_estime: int

    @property
    def total(self) -> Decimal:
        """Rendre frais du relevé + frais des fonds."""
        return self.frais_releve + self.frais_fonds


@dataclass(frozen=True)
class HistoriqueFrais:
    """Frais année par année d'un contrat, depuis son premier relevé annuel."""

    titulaire: str
    produit: str
    numero: str
    annees: tuple[AnneeFrais, ...]

    @property
    def cumul_releve(self) -> Decimal:
        """Rendre la somme des frais annoncés par les relevés (exacts)."""
        return sum((a.frais_releve for a in self.annees), ZERO)

    @property
    def cumul_fonds(self) -> Decimal:
        """Rendre la somme des frais des fonds (estimés)."""
        return sum((a.frais_fonds for a in self.annees), ZERO)

    @property
    def cumul(self) -> Decimal:
        """Rendre le total des frais depuis le premier relevé."""
        return self.cumul_releve + self.cumul_fonds


def historiques_frais(releves: list[ReleveRange]) -> list[HistoriqueFrais]:
    """Rendre l'historique des frais de chaque contrat à relevés annuels, trié par titulaire puis produit."""
    par_contrat: dict[tuple[str, str], list[Releve]] = {}
    for range_ in releves:
        if range_.releve.est_annuel:
            par_contrat.setdefault((range_.titulaire, cle_du_contrat(range_.releve.numero)), []).append(range_.releve)
    historiques = []
    for (titulaire, numero), liste in sorted(par_contrat.items()):
        liste.sort(key=lambda r: r.date_arrete)
        taux = _taux_fonds_par_isin(liste)
        # Taux de repli d'une année sans aucun fonds au taux connu : la moyenne du dernier relevé.
        repli = _taux_moyen({s.isin: s.valeur for s in liste[-1].supports if s.isin}, taux)
        annees = tuple(
            _annee(precedent, releve, taux, repli) for precedent, releve in zip([None, *liste], liste, strict=False)
        )
        historiques.append(HistoriqueFrais(titulaire, liste[-1].produit, numero, annees))
    return historiques


def _taux_fonds_par_isin(releves: list[Releve]) -> dict[str, Decimal]:
    """Rendre les frais de gestion de chaque fonds, le tableau le plus récent l'emportant. MODELE § 5.1."""
    taux: dict[str, Decimal] = {}
    for releve in releves:
        taux.update({frais.isin: frais.frais_support for frais in releve.frais_supports})
    return taux


def _annee(precedent: Releve | None, releve: Releve, taux: dict[str, Decimal], repli: Decimal) -> AnneeFrais:
    """Rendre les frais d'une année : encours moyen de chaque fonds fois ses frais de gestion. MODELE § 5.2."""
    debut = {s.isin: s.valeur for s in precedent.supports if s.isin} if precedent else {}
    fin = {s.isin: s.valeur for s in releve.supports if s.isin}
    moyenne_connue = _taux_moyen(fin, taux) or repli
    frais, estimes = ZERO, 0
    for isin in debut.keys() | fin.keys():
        encours_moyen = (debut.get(isin, ZERO) + fin.get(isin, ZERO)) / 2
        if isin not in taux:
            estimes += 1
        frais += encours_moyen * taux.get(isin, moyenne_connue) / CENT
    frais_releve = releve.frais.total if releve.frais else ZERO
    return AnneeFrais(releve.date_arrete.year, frais_releve, frais, estimes)


def _taux_moyen(valeurs: dict[str, Decimal], taux: dict[str, Decimal]) -> Decimal:
    """Rendre le taux moyen pondéré des fonds au taux connu : il remplace celui d'un fonds vendu avant 2025."""
    connus = {isin: valeur for isin, valeur in valeurs.items() if isin in taux}
    total = sum(connus.values(), ZERO)
    if not total:
        return ZERO
    return sum((valeur * taux[isin] for isin, valeur in connus.items()), ZERO) / total
