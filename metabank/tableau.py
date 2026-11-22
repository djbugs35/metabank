"""Tableau de bord du patrimoine : une page HTML autonome, générée en local (aucune ressource en ligne).

Graphiques en SVG écrits ici même : pas de bibliothèque à télécharger, la page s'ouvre hors connexion.
Palette : catégorielle de référence (skill dataviz), une version claire et une sombre.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from html import escape

from metabank.bilan import BilanContrat
from metabank.frais import AnalyseFrais
from metabank.rapport import LIBELLES_TYPES, euros
from metabank.rapport_frais import points

ZERO = Decimal(0)
LARGEUR = 640
HAUTEUR_BARRE = 14
ECART_BARRES = 2
HAUTEUR_GROUPE = 2 * HAUTEUR_BARRE + ECART_BARRES + 16
MARGE_LIBELLES = 230


@dataclass(frozen=True)
class Tableau:
    """Contenu du tableau de bord, prêt à mettre en page."""

    bilans: list[BilanContrat]
    analyses: list[AnalyseFrais]
    genere_le: date

    def analyse_de(self, bilan: BilanContrat) -> AnalyseFrais | None:
        """Rendre l'analyse des frais du même contrat, ou None (contrat sans détail des supports)."""
        return next(
            (a for a in self.analyses if a.titulaire == bilan.titulaire and a.produit.lower() == bilan.produit.lower()),
            None,
        )


def generer_html(tableau: Tableau) -> str:
    """Rendre la page HTML complète du tableau de bord."""
    sections = [
        _tuiles(tableau),
        _section("Valeur et versements par contrat", _barres_valeur(tableau.bilans)),
        _section("Évolution des contrats suivis depuis l'ouverture", _evolution(tableau.bilans)),
        _section("Frais annuels par contrat, au rythme actuel", _barres_frais(tableau)),
        _section("Les supports, du plus coûteux au moins coûteux", _table_supports(tableau.analyses)),
        _section("Points d'attention", _points_attention(tableau)),
    ]
    return GABARIT.format(date=f"{tableau.genere_le:%d/%m/%Y}", corps="\n".join(sections))


def _section(titre: str, contenu: str) -> str:
    return f"<section><h2>{escape(titre)}</h2>{contenu}</section>"


def _tuiles(tableau: Tableau) -> str:
    valeur = sum((b.valeur for b in tableau.bilans), ZERO)
    verse = sum((b.apports_cumules or ZERO for b in tableau.bilans), ZERO)
    frais = sum((a.cout_total for a in tableau.analyses), ZERO)
    caches = sum((a.frais_dans_supports for a in tableau.analyses), ZERO)
    retro = sum((a.retrocessions for a in tableau.analyses), ZERO)
    tuiles = [
        ("Patrimoine suivi", euros(valeur), f"{len(tableau.bilans)} contrats"),
        ("Versé", euros(verse), f"gain {euros(valeur - verse)}"),
        ("Frais par an, tout compris", euros(frais), "contrats au détail connu"),
        ("dont frais cachés dans les fonds", euros(caches), f"dont {euros(retro)} reversés au distributeur"),
    ]
    contenu = "".join(
        f'<div class="tuile"><div class="etiquette">{escape(e)}</div><div class="valeur">{escape(v)}</div>'
        f'<div class="note">{escape(n)}</div></div>'
        for e, v, n in tuiles
    )
    return f'<section class="tuiles">{contenu}</section>'


def _nom(bilan: BilanContrat) -> str:
    return f"{bilan.titulaire} · {LIBELLES_TYPES.get(bilan.type_contrat, bilan.type_contrat)} {bilan.assureur}"


def _barres_valeur(bilans: list[BilanContrat]) -> str:
    """Rendre deux barres par contrat : versé (série 1) et valeur actuelle (série 2)."""
    maximum = max((max(b.valeur, b.apports_cumules or ZERO) for b in bilans), default=Decimal(1))
    groupes = []
    for rang, bilan in enumerate(sorted(bilans, key=lambda b: b.valeur, reverse=True)):
        y = rang * HAUTEUR_GROUPE
        groupes.append(_libelle(MARGE_LIBELLES - 8, y + HAUTEUR_BARRE + 4, _nom(bilan)))
        for decalage, (classe, montant, texte) in enumerate(
            (("serie-1", bilan.apports_cumules or ZERO, "versé"), ("serie-2", bilan.valeur, "valeur"))
        ):
            yb = y + decalage * (HAUTEUR_BARRE + ECART_BARRES)
            groupes.append(
                _barre(MARGE_LIBELLES, yb, montant, maximum, classe, f"{_nom(bilan)} — {texte} {euros(montant)}")
            )
        groupes.append(_valeur_fin(MARGE_LIBELLES, y + HAUTEUR_BARRE + ECART_BARRES, bilan.valeur, maximum))
    legende = _legende([("serie-1", "Versé"), ("serie-2", "Valeur actuelle")])
    return legende + _svg(len(bilans) * HAUTEUR_GROUPE, "".join(groupes), "Valeur et versements par contrat")


def _barres_frais(tableau: Tableau) -> str:
    """Rendre une barre empilée par contrat : frais du contrat (visibles) puis frais des fonds (cachés)."""
    lignes = [(b, a) for b in tableau.bilans if (a := tableau.analyse_de(b))]
    if not lignes:
        return "<p>Aucun relevé ne détaille encore les frais des supports.</p>"
    maximum = max(a.cout_total for _, a in lignes)
    groupes = []
    for rang, (bilan, a) in enumerate(sorted(lignes, key=lambda l: l[1].cout_total, reverse=True)):
        y = rang * (HAUTEUR_BARRE + 18)
        groupes.append(_libelle(MARGE_LIBELLES - 8, y + HAUTEUR_BARRE - 2, _nom(bilan)))
        largeur_visible = _largeur(a.frais_contrat_estimes, maximum)
        groupes.append(
            _rect(MARGE_LIBELLES, y, largeur_visible, "serie-1", f"Frais du contrat {euros(a.frais_contrat_estimes)}")
        )
        groupes.append(_rect(MARGE_LIBELLES + largeur_visible + ECART_BARRES, y, _largeur(a.frais_dans_supports, maximum),
                             "serie-2", f"Frais des fonds {euros(a.frais_dans_supports)}"))  # fmt: skip
        fin = MARGE_LIBELLES + _largeur(a.cout_total, maximum) + ECART_BARRES + 6
        groupes.append(f'<text x="{fin}" y="{y + HAUTEUR_BARRE - 2}" class="valeur-barre">'
                       f"{euros(a.cout_total)} · {points(a.taux_moyen)}</text>")  # fmt: skip
    legende = _legende([("serie-1", "Frais du contrat (sur le relevé)"), ("serie-2", "Frais des fonds (cachés)")])
    return legende + _svg(len(lignes) * (HAUTEUR_BARRE + 18), "".join(groupes), "Frais annuels par contrat")


def _evolution(bilans: list[BilanContrat]) -> str:
    """Rendre la valeur totale et le versé cumulé au 31/12, pour les contrats à relevés annuels."""
    annees = sorted({a.annee for b in bilans for a in b.annees})
    if len(annees) < 2:
        return "<p>Pas encore assez d'années pour tracer une évolution.</p>"
    valeur, verse = [], []
    for annee in annees:
        valeur.append(sum((a.valeur_fin for b in bilans for a in b.annees if a.annee == annee), ZERO))
        verse.append(sum((a.apports for b in bilans for a in b.annees if a.annee <= annee), ZERO))
    hauteur, gauche, bas = 180, 70, 24
    maximum = max(valeur + verse) * Decimal("1.1")
    pas = (LARGEUR - gauche - 40) / (len(annees) - 1)

    def point(rang: int, montant: Decimal) -> tuple[float, float]:
        return gauche + rang * pas, float(hauteur - bas - (montant / maximum) * (hauteur - bas - 10))

    contenu = [f'<line x1="{gauche}" y1="{hauteur - bas}" x2="{LARGEUR - 20}" y2="{hauteur - bas}" class="axe"/>']
    for rang, annee in enumerate(annees):
        x, _ = point(rang, ZERO)
        contenu.append(f'<text x="{x}" y="{hauteur - 6}" class="graduation" text-anchor="middle">31/12/{annee}</text>')
    # Valeur au-dessus de son point, versé en dessous : les deux étiquettes finales ne se chevauchent pas.
    for classe, serie, nom, decalage in (("serie-1", verse, "Versé cumulé", 20), ("serie-2", valeur, "Valeur", -10)):
        coords = [point(rang, montant) for rang, montant in enumerate(serie)]
        contenu.append(f'<polyline class="ligne {classe}" points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in coords)}"/>')
        for (x, y), montant, annee in zip(coords, serie, annees, strict=True):
            contenu.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" class="point {classe}">'
                           f"<title>{nom} au 31/12/{annee} : {euros(montant)}</title></circle>")  # fmt: skip
        x, y = coords[-1]
        contenu.append(
            f'<text x="{x - 8}" y="{y + decalage}" class="valeur-barre" text-anchor="end">{euros(serie[-1])}</text>'
        )
    note = (
        "<p class='note'>Contrats à relevés annuels uniquement ; les relevés de situation n'ont pas d'historique.</p>"
    )
    legende = _legende([("serie-1", "Versé cumulé"), ("serie-2", "Valeur au 31/12")])
    return legende + _svg(hauteur, "".join(contenu), "Évolution de la valeur et des versements") + note


def _table_supports(analyses: list[AnalyseFrais]) -> str:
    lignes = [(a, l) for a in analyses for l in a.lignes]
    lignes.sort(key=lambda al: al[1].cout_annuel or ZERO, reverse=True)
    corps = "".join(
        f"<tr><td>{escape(l.libelle)}</td><td>{escape(a.titulaire)} · {escape(a.produit)}</td>"
        f'<td class="n">{euros(l.valeur)}</td><td class="n">{points(l.frais_support)}</td>'
        f'<td class="n">{points(l.retrocessions)}</td><td class="n">{points(l.frais_totaux)}</td>'
        f'<td class="n">{euros(l.cout_annuel)}</td><td class="n">{points(l.performance_finale)}</td></tr>'
        for a, l in lignes
    )
    entete = ("<tr><th>Support</th><th>Contrat</th><th>Valeur</th><th>Frais du fonds</th><th>dont rétro.</th>"
              "<th>Frais totaux</th><th>Coût/an</th><th>Perf. nette année</th></tr>")  # fmt: skip
    return f'<div class="defile"><table><thead>{entete}</thead><tbody>{corps}</tbody></table></div>'


def _points_attention(tableau: Tableau) -> str:
    points_ = [f"{b.titulaire} · {b.produit} : {a.split(' : ', 1)[-1]}" for b in tableau.bilans for a in b.anomalies]
    points_ += [
        f"{b.titulaire} · {b.produit} : relevé de situation seul, frais et historique inconnus"
        for b in tableau.bilans
        if not b.annees
    ]
    if not points_:
        return "<p>Aucun.</p>"
    return "<ul>" + "".join(f"<li>{escape(p)}</li>" for p in points_) + "</ul>"


def _largeur(montant: Decimal, maximum: Decimal) -> float:
    return float(montant / maximum) * (LARGEUR - MARGE_LIBELLES - 110) if maximum else 0.0


def _rect(x: float, y: float, largeur: float, classe: str, info: str) -> str:
    return (f'<rect x="{x:.1f}" y="{y}" width="{max(largeur, 1):.1f}" height="{HAUTEUR_BARRE}" rx="4" '
            f'class="{classe}"><title>{escape(info)}</title></rect>')  # fmt: skip


def _barre(x: float, y: float, montant: Decimal, maximum: Decimal, classe: str, info: str) -> str:
    return _rect(x, y, _largeur(montant, maximum), classe, info)


def _valeur_fin(x: float, y: float, montant: Decimal, maximum: Decimal) -> str:
    return f'<text x="{x + _largeur(montant, maximum) + 6:.1f}" y="{y + HAUTEUR_BARRE - 3}" class="valeur-barre">{euros(montant)}</text>'


def _libelle(x: float, y: float, texte: str) -> str:
    return f'<text x="{x}" y="{y}" class="libelle" text-anchor="end">{escape(texte)}</text>'


def _legende(series: list[tuple[str, str]]) -> str:
    return '<div class="legende">' + "".join(
        f'<span><i class="pastille {classe}"></i>{escape(nom)}</span>' for classe, nom in series
    ) + "</div>"  # fmt: skip


def _svg(hauteur: int, contenu: str, titre: str) -> str:
    return (f'<svg viewBox="0 0 {LARGEUR} {hauteur + 4}" role="img" aria-label="{escape(titre)}">'
            f"{contenu}</svg>")  # fmt: skip


GABARIT = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Patrimoine du foyer</title>
<style>
:root {{ color-scheme: light; --fond:#f6f5f2; --surface:#fcfcfb; --texte:#0b0b0b; --texte-2:#52514e; --trait:#dcdad3;
  --serie-1:#2a78d6; --serie-2:#eb6834; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ color-scheme: dark; --fond:#121211;
  --surface:#1a1a19; --texte:#f0efec; --texte-2:#c3c2b7; --trait:#3a3936; --serie-1:#3987e5; --serie-2:#d95926; }} }}
:root[data-theme="dark"] {{ color-scheme: dark; --fond:#121211; --surface:#1a1a19; --texte:#f0efec; --texte-2:#c3c2b7;
  --trait:#3a3936; --serie-1:#3987e5; --serie-2:#d95926; }}
body {{ margin:0; background:var(--fond); color:var(--texte); font:15px/1.5 -apple-system, "Segoe UI", sans-serif; }}
main {{ max-width:980px; margin:0 auto; padding:24px 16px 48px; }}
h1 {{ font-size:26px; margin:0 0 4px; }} h2 {{ font-size:17px; margin:0 0 12px; }}
.sous-titre, .note {{ color:var(--texte-2); font-size:13px; }}
section {{ background:var(--surface); border:1px solid var(--trait); border-radius:12px; padding:18px; margin-top:16px; }}
.tuiles {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:12px; background:none;
  border:0; padding:0; }}
.tuile {{ background:var(--surface); border:1px solid var(--trait); border-radius:12px; padding:14px 16px; }}
.etiquette {{ color:var(--texte-2); font-size:13px; }} .valeur {{ font-size:26px; font-weight:650; }}
svg {{ width:100%; height:auto; display:block; }}
.serie-1 {{ fill:var(--serie-1); stroke:var(--serie-1); }} .serie-2 {{ fill:var(--serie-2); stroke:var(--serie-2); }}
rect.serie-1, rect.serie-2 {{ stroke:none; }}
.ligne {{ fill:none !important; stroke-width:2; }} .point {{ stroke:var(--surface) !important; stroke-width:2; }}
.axe {{ stroke:var(--trait); }} .graduation, .libelle {{ fill:var(--texte-2); font-size:12px; }}
.valeur-barre {{ fill:var(--texte); font-size:12px; }}
.legende {{ display:flex; gap:16px; flex-wrap:wrap; font-size:13px; color:var(--texte-2); margin-bottom:8px; }}
.pastille {{ display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:6px; }}
i.serie-1 {{ background:var(--serie-1); }} i.serie-2 {{ background:var(--serie-2); }}
.defile {{ overflow-x:auto; }} table {{ border-collapse:collapse; width:100%; font-size:13px; }}
th, td {{ padding:6px 8px; border-bottom:1px solid var(--trait); text-align:left; white-space:nowrap; }}
th {{ color:var(--texte-2); font-weight:600; }} td.n {{ text-align:right; font-variant-numeric:tabular-nums; }}
ul {{ margin:0; padding-left:20px; }} li {{ margin:4px 0; }}
</style></head>
<body><main>
<h1>Patrimoine du foyer</h1>
<div class="sous-titre">Généré le {date} par metabank, à partir des relevés de data/. Données locales, rien n'est envoyé.
Survoler un graphique pour le détail.</div>
{corps}
<p class="note">Rendements estimés (versements supposés en milieu d'année) ; frais annuels estimés sur la valeur au
31/12. Formules : docs/MODELE.md. Éléments d'aide à la décision, pas un conseil financier.</p>
</main></body></html>
"""
