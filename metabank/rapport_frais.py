"""Mise en forme de l'analyse des frais support par support."""

from decimal import Decimal

from metabank.frais import AnalyseFrais, LigneFrais
from metabank.rapport import euros


def points(taux: Decimal | None) -> str:
    """Rendre « 1,40 % » pour 1.40 points, ou « ? »."""
    return "?" if taux is None else f"{taux:.2f} %".replace(".", ",")


def formater_frais(analyses: list[AnalyseFrais]) -> str:
    """Rendre un bloc par contrat : tableau des supports du plus coûteux au moins coûteux, puis synthèse."""
    return "\n\n".join(_formater_contrat(analyse) for analyse in analyses)


def _formater_contrat(a: AnalyseFrais) -> str:
    titre = f"{a.titulaire} — {a.produit} : frais par support (relevé {a.annee})"
    lignes = [titre, "-" * len(titre)]
    lignes.append(
        f"{'Support':<34}{'Valeur':>10}{'Support':>9}{'dont rétro':>11}{'Contrat':>9}{'Total':>8}"
        f"{'Coût/an':>9}{'Perf. nette':>12}{'5 ans':>9}"
    )
    lignes.extend(_ligne(l) for l in sorted(a.lignes, key=lambda l: l.cout_annuel or Decimal(0), reverse=True))
    inconnus = [l.libelle for l in a.lignes if l.frais_totaux is None]
    lignes += [
        "",
        (
            f"Encours {euros(a.encours)}. Au rythme actuel, tous frais compris : {euros(a.cout_total)} par an "
            f"(taux moyen {points(a.taux_moyen)})"
        ),
        f"  frais de gestion du contrat (prélevés par l'assureur, visibles) : {euros(a.frais_contrat_estimes)}",
        f"  frais des supports (déjà déduits des cours, absents du relevé) : {euros(a.frais_dans_supports)}",
        f"    dont reversés à l'assureur et au distributeur (rétrocessions) : {euros(a.retrocessions)}",
        (
            f"Pour mémoire, frais annoncés par le relevé {a.annee}, y compris sur versements et arbitrages : "
            f"{euros(a.frais_releve)}"
        ),
        (
            f"Simulation : supports à {points(a.frais_support_cible)} de frais au lieu des actuels → "
            f"{euros(a.economie_annuelle)} de moins par an ; sur {a.horizon_ans} ans "
            f"à {points(a.rendement_brut_hypothese)} brut, sans nouveau versement : "
            f"{euros(a.ecart_projete)} de plus à l'arrivée."
        ),
    ]
    if inconnus:
        lignes.append(f"  ⚠ frais inconnus (non comptés) : {', '.join(inconnus)}")
    return "\n".join(lignes)


def _ligne(l: LigneFrais) -> str:
    return (
        f"{l.libelle[:33]:<34}{euros(l.valeur):>10}{points(l.frais_support):>9}{points(l.retrocessions):>11}"
        f"{points(l.frais_contrat):>9}{points(l.frais_totaux):>8}{euros(l.cout_annuel):>9}"
        f"{points(l.performance_finale):>12}{points(l.performance_finale_5_ans):>9}"
    )
