"""Histogrammes SVG par année, écrits sans bibliothèque (la page doit s'ouvrir hors connexion)."""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from html import escape

ZERO = Decimal(0)
LARGEUR, HAUTEUR = 300, 200
HAUT, BAS = 36, 24
LARGEUR_BARRE_MAX = 46
ECART_EMPILEMENT = 2
HAUTEUR_LIGNE = 13


@dataclass(frozen=True)
class Serie:
    """Une série de valeurs, une par année ; None = pas de valeur cette année-là."""

    classe: str
    nom: str
    valeurs: list[Decimal | None]
    sous_etiquettes: list[str] | None = None


def histogramme(
    titre: str,
    annees: list[int],
    series: list[Serie],
    formater: Callable[[Decimal], str],
    *,
    etiquettes: list[list[str]] | None = None,
    infos: list[str] | None = None,
) -> str:
    """Rendre un histogramme par année ; plusieurs séries sont empilées, le total est écrit au-dessus.

    Args:
        etiquettes: une liste de lignes par année, à la place de la valeur formatée (ex. « 3,3 % », « +98 € »).
        infos: un texte de survol par année, à la place de « série année : valeur ».
    """
    totaux = [_somme(serie.valeurs[rang] for serie in series) for rang in range(len(annees))]
    connus = [t for t in totaux if t is not None] or [ZERO]
    bas_echelle, haut_echelle = min(*connus, ZERO), max(*connus, ZERO)
    etendue = (haut_echelle - bas_echelle) or Decimal(1)

    def y(valeur: Decimal) -> float:
        return HAUT + float((haut_echelle - valeur) / etendue) * (HAUTEUR - HAUT - BAS)

    pas = LARGEUR / len(annees)
    largeur_barre = min(LARGEUR_BARRE_MAX, pas * 0.55)
    contenu = [f'<line x1="0" y1="{y(ZERO):.1f}" x2="{LARGEUR}" y2="{y(ZERO):.1f}" class="axe"/>']
    for rang, annee in enumerate(annees):
        centre = pas * (rang + 0.5)
        info = infos[rang] if infos else None
        contenu += _barres(series, rang, (centre, largeur_barre), y, (f"{annee}", info), formater)
        total = totaux[rang]
        lignes = etiquettes[rang] if etiquettes else ["—" if total is None else formater(total)]
        contenu.append(_etiquette(centre, total, y, lignes))
        contenu.append(
            f'<text x="{centre:.1f}" y="{HAUTEUR - 6}" class="graduation" text-anchor="middle">{annee}</text>'
        )
    legende = _legende(series) if len(series) > 1 else ""
    return (f'<figure class="graphique"><figcaption>{escape(titre)}</figcaption>{legende}'
            f'<svg viewBox="0 0 {LARGEUR} {HAUTEUR}" role="img" aria-label="{escape(titre)}">{"".join(contenu)}</svg>'
            "</figure>")  # fmt: skip


def _etiquette(centre: float, total: Decimal | None, y, lignes: list[str]) -> str:
    """Rendre les lignes de texte au-dessus d'une barre positive, au-dessous d'une barre négative."""
    if (total or ZERO) >= 0:
        premiere = y(max(total or ZERO, ZERO)) - 6 - (len(lignes) - 1) * HAUTEUR_LIGNE
    else:
        premiere = y(total) + 14
    tspans = "".join(
        f'<tspan x="{centre:.1f}" dy="{0 if rang == 0 else HAUTEUR_LIGNE}">{escape(ligne)}</tspan>'
        for rang, ligne in enumerate(lignes)
    )
    return f'<text y="{premiere:.1f}" class="valeur-barre" text-anchor="middle">{tspans}</text>'


def _barres(
    series: list[Serie], rang: int, position: tuple[float, float], y, textes: tuple[str, str | None], formater
) -> list[str]:
    """Rendre les segments empilés d'une année, du bas vers le haut, séparés de 2 px."""
    centre, largeur = position
    annee, info = textes
    segments, cumul = [], ZERO
    for serie in series:
        valeur = serie.valeurs[rang]
        if valeur is None or valeur == 0:
            continue
        haut, bas = (cumul + valeur, cumul) if valeur > 0 else (cumul, cumul + valeur)
        hauteur = max(y(bas) - y(haut) - (ECART_EMPILEMENT if cumul else 0), 1)
        segments.append(
            f'<rect x="{centre - largeur / 2:.1f}" y="{y(haut):.1f}" width="{largeur:.1f}" height="{hauteur:.1f}" '
            f'rx="3" class="{serie.classe}"><title>'
            f"{escape(info or f'{serie.nom} {annee} : {formater(valeur)}')}</title></rect>"
        )
        cumul += valeur
    return segments


def _somme(valeurs) -> Decimal | None:
    connues = [v for v in valeurs if v is not None]
    return sum(connues, ZERO) if connues else None


def _legende(series: list[Serie]) -> str:
    return '<div class="legende">' + "".join(
        f'<span><i class="pastille {s.classe}"></i>{escape(s.nom)}</span>' for s in series
    ) + "</div>"  # fmt: skip


def barres_groupees(titre: str, annees: list[int], series: list[Serie], formater: Callable[[Decimal], str]) -> str:
    """Rendre un histogramme par année où les séries sont côte à côte, chaque barre avec sa valeur au-dessus."""
    largeur, hauteur, haut, bas = 600, 250, 40, 26
    valeurs = [v for s in series for v in s.valeurs if v is not None] or [ZERO]
    bas_echelle, haut_echelle = min(*valeurs, ZERO), max(*valeurs, ZERO)
    etendue = (haut_echelle - bas_echelle) or Decimal(1)

    def y(valeur: Decimal) -> float:
        return haut + float((haut_echelle - valeur) / etendue) * (hauteur - haut - bas)

    pas = largeur / len(annees)
    barre = min(64, pas * 0.7 / len(series))
    contenu = [f'<line x1="0" y1="{y(ZERO):.1f}" x2="{largeur}" y2="{y(ZERO):.1f}" class="axe"/>']
    for rang, annee in enumerate(annees):
        centre = pas * (rang + 0.5)
        gauche = centre - barre * len(series) / 2 - ECART_EMPILEMENT * (len(series) - 1) / 2
        for numero, serie in enumerate(series):
            valeur = serie.valeurs[rang]
            if valeur is None:
                continue
            x = gauche + numero * (barre + ECART_EMPILEMENT)
            dessus, dessous = (valeur, ZERO) if valeur >= 0 else (ZERO, valeur)
            texte = formater(valeur)
            contenu.append(
                f'<rect x="{x:.1f}" y="{y(dessus):.1f}" width="{barre:.1f}" height="{max(y(dessous) - y(dessus), 1):.1f}" '
                f'rx="4" class="{serie.classe}"><title>{escape(serie.nom)} {annee} : {escape(texte)}</title></rect>'
            )
            sous = serie.sous_etiquettes[rang] if serie.sous_etiquettes else ""
            y_texte = y(dessus) - 6 - (HAUTEUR_LIGNE if sous else 0) if valeur >= 0 else y(dessous) + 14
            ligne2 = f'<tspan x="{x + barre / 2:.1f}" dy="{HAUTEUR_LIGNE}" class="sous">{escape(sous)}</tspan>'
            contenu.append(
                f'<text x="{x + barre / 2:.1f}" y="{y_texte:.1f}" class="valeur-barre" text-anchor="middle">'
                f"{escape(texte)}{ligne2 if sous else ''}</text>"
            )
        contenu.append(
            f'<text x="{centre:.1f}" y="{hauteur - 6}" class="graduation" text-anchor="middle">{annee}</text>'
        )
    return (
        f'<figure class="graphique"><figcaption>{escape(titre)}</figcaption>{_legende(series)}'
        f'<svg viewBox="0 0 {largeur} {hauteur}" role="img" aria-label="{escape(titre)}">{"".join(contenu)}</svg>'
        "</figure>"
    )
