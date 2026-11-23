// Un graphique par bloc du tableau de bord ; tous les chiffres viennent de l'API (code Python testé).
import { barresGroupees, barresHorizontales, courbes } from "./graphiques.js";
import { creditsDeVue, euros, fondsDeVue, pct } from "./rendu.js";

const $ = (id) => document.getElementById(id);
const MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
const moisDe = (iso) => `${MOIS[Number(iso.slice(5, 7)) - 1]} ${iso.slice(2, 4)}`;

function montrer(id, visible) {
  $(id).closest(".carte, #bloc-reperes").classList.toggle("cache", !visible);
  return visible;
}

// Épargne disponible : somme des livrets en fin de mois (MODELE § 8.1).
function livrets(etat, vue) {
  const h = etat.historique?.[vue.id];
  const valeurs = h?.familles?.["Épargne disponible"];
  if (!montrer("graphique-livrets", Boolean(valeurs?.some((v) => v)))) return;
  courbes($("graphique-livrets"), {
    titre: "Livrets en fin de mois", abscisses: h.points.map((p) => p.jour), legendeX: moisDe, formater: euros,
    series: [{ classe: "serie-3", nom: "Épargne disponible", valeurs }],
    survol: (rang) => { $("infobulle-livrets").textContent = rang === null ? "" : `${moisDe(h.points[rang].jour)} : ${euros(valeurs[rang])}`; },
  });
}

// Crédits : capital restant dû aujourd'hui puis à chaque fin d'année, d'après le tableau d'amortissement (§ 7.11).
function credits(etat, vue) {
  const liste = vue.niveau === "contrat" ? [] : creditsDeVue(etat, vue).filter((c) => c.echeancier?.length);
  if (!montrer("graphique-credits", liste.length > 0)) return;
  const annees = [...new Set(liste.flatMap((c) => c.echeancier.map((a) => a.annee)))].sort();
  const series = liste.map((c, rang) => {
    const fin = Object.fromEntries(c.echeancier.map((a) => [a.annee, a.restant]));
    return { classe: `serie-${(rang % 4) + 1}`, nom: c.nom, valeurs: [c.capital_restant, ...annees.map((a) => fin[a] ?? 0)] };
  });
  const abscisses = ["aujourd'hui", ...annees.map(String)];
  courbes($("graphique-credits"), {
    titre: "Capital restant dû, fin d'année", abscisses, legendeX: (a) => a, formater: euros, series,
    survol: (rang) => {
      $("infobulle-credits").textContent = rang === null ? "" : `${abscisses[rang]} : ${series.map((s) => `${s.nom} ${euros(s.valeurs[rang])}`).join(" ; ")}`;
    },
  });
}

// Bien locatif : entrées et sorties du compte locatif, mois par mois (MODELE § 7.4).
function locatif(etat, vue) {
  const b = etat.locatif;
  const compte = (etat.banque ?? []).find((c) => c.type === "locatif");
  const visible = Boolean(b && compte?.mois?.length) && (vue.niveau === "foyer" || (vue.niveau === "personne" && b.titulaires.includes(vue.nom)));
  if (!montrer("graphique-locatif", visible)) return;
  const mois = compte.mois.slice(-13);
  barresGroupees($("graphique-locatif"), {
    titre: "Compte locatif : entrées et sorties par mois", annees: mois.map((m) => moisDe(`${m.mois}-01`)), formater: euros, etiquettes: false,
    series: [{ classe: "serie-3", nom: "Entrées", valeurs: mois.map((m) => m.revenus) },
             { classe: "serie-2", nom: "Sorties", valeurs: mois.map((m) => m.depenses) }],
    survol: (rang) => {
      $("infobulle-locatif").textContent = rang === null ? "" : `${moisDe(`${mois[rang].mois}-01`)} : entrées ${euros(mois[rang].revenus)}, sorties ${euros(mois[rang].depenses)}`;
    },
  });
}

// Placements : rendement de chaque année face aux repères publics (MODELE § 10).
function reperes(etat, vue) {
  const annees = vue.annees.filter((a) => etat.reperes?.[a.annee]);
  if (!montrer("graphique-reperes", annees.length > 0)) return;
  const champs = [["Votre rendement", null, "serie-1"], ["Fonds en euros", "fonds_euros", "serie-3"], ["Unités de compte", "unites_de_compte", "serie-4"],
    ["MSCI World", "msci_world", "serie-2"], ["Livret A", "livret_a", "serie-5"], ["Inflation", "inflation", "serie-6"]];
  const series = champs.map(([nom, cle, classe]) => ({
    nom, classe, valeurs: annees.map((a) => (cle === null ? a.gain_taux : etat.reperes[a.annee][cle]) ?? null),
  }));
  barresGroupees($("graphique-reperes"), {
    titre: "Rendement de l'année face aux repères publics", annees: annees.map((a) => a.annee), formater: (v) => pct(v, true), etiquettes: false, series,
    survol: (rang) => {
      $("infobulle-reperes").textContent = rang === null ? "" : `${annees[rang].annee} : ${series
        .map((s) => `${s.nom} ${s.valeurs[rang] === null ? "—" : pct(s.valeurs[rang], true)}`).join(" ; ")}`;
    },
  });
}

// Fonds : coût annuel de chacun (frais du fonds et du contrat, MODELE § 4.1), du plus coûteux au moins coûteux.
function fonds(etat, vue) {
  const liste = fondsDeVue(etat, vue).filter((f) => f.cout_annuel).slice(0, 12);
  if (!montrer("graphique-fonds", liste.length > 0)) return;
  barresHorizontales($("graphique-fonds"), {
    titre: "Coût annuel des fonds (frais du fonds et du contrat)", formater: euros,
    lignes: liste.map((f) => ({ nom: f.fonds.length > 28 ? `${f.fonds.slice(0, 27)}…` : f.fonds, valeur: f.cout_annuel, sous: `${pct(f.frais_totaux)} par an` })),
  });
}

export function afficherGraphiques(etat, vue) {
  for (const tracer of [livrets, credits, locatif, reperes, fonds]) tracer(etat, vue);
}

