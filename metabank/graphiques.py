"""Histogrammes SVG par année, écrits sans bibliothèque (la page doit s'ouvrir hors connexion)."""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from html import escape

ZERO = Decimal(0)
LARGEUR, HAUTEUR = 300, 200
HAUT, BAS = 24, 24
LARGEUR_BARRE_MAX = 46
ECART_EMPILEMENT = 2


@dataclass(frozen=True)
class Serie:
    """Une série de valeurs, une par année ; None = pas de valeur cette année-là."""

    classe: str
    nom: str
    valeurs: list[Decimal | None]


def histogramme(
    titre: str,
    annees: list[int],
    series: list[Serie],
    formater: Callable[[Decimal], str],
    marques: list[bool] | None = None,
) -> str:
    """Rendre un histogramme par année ; plusieurs séries sont empilées, le total est écrit au-dessus.

    Args:
        marques: une par année ; vrai ajoute « * » à l'étiquette (valeur estimée, expliquée sous le graphique).
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
        contenu += _barres(series, rang, (centre, largeur_barre), y, f"{annee}", formater)
        total = totaux[rang]
        etoile = "*" if marques and marques[rang] else ""
        texte = "—" if total is None else formater(total) + etoile
        y_texte = y(max(total or ZERO, ZERO)) - 6 if (total or ZERO) >= 0 else y(total) + 14
        contenu.append(f'<text x="{centre:.1f}" y="{y_texte:.1f}" class="valeur-barre" text-anchor="middle">'
                       f"{escape(texte)}</text>")  # fmt: skip
        contenu.append(
            f'<text x="{centre:.1f}" y="{HAUTEUR - 6}" class="graduation" text-anchor="middle">{annee}</text>'
        )
    legende = _legende(series) if len(series) > 1 else ""
    return (f'<figure class="graphique"><figcaption>{escape(titre)}</figcaption>{legende}'
            f'<svg viewBox="0 0 {LARGEUR} {HAUTEUR}" role="img" aria-label="{escape(titre)}">{"".join(contenu)}</svg>'
            "</figure>")  # fmt: skip


def _barres(series: list[Serie], rang: int, position: tuple[float, float], y, annee: str, formater) -> list[str]:
    """Rendre les segments empilés d'une année, du bas vers le haut, séparés de 2 px."""
    centre, largeur = position
    segments, cumul = [], ZERO
    for serie in series:
        valeur = serie.valeurs[rang]
        if valeur is None or valeur == 0:
            continue
        haut, bas = (cumul + valeur, cumul) if valeur > 0 else (cumul, cumul + valeur)
        hauteur = max(y(bas) - y(haut) - (ECART_EMPILEMENT if cumul else 0), 1)
        segments.append(
            f'<rect x="{centre - largeur / 2:.1f}" y="{y(haut):.1f}" width="{largeur:.1f}" height="{hauteur:.1f}" '
            f'rx="3" class="{serie.classe}"><title>{escape(serie.nom)} {annee} : {escape(formater(valeur))}</title></rect>'
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
