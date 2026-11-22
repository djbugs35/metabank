// Mise en forme partagée par l'application et le rapport PDF : mêmes chiffres, mêmes libellés, même présentation.
import { echapper } from "./graphiques.js";

const nombre = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
export const euros = (v) => (v === null || v === undefined ? "—" : `${nombre.format(v)} €`);
export const eurosSignes = (v) => (v === null || v === undefined ? "—" : `${v >= 0 ? "+" : ""}${euros(v)}`);
export const pct = (t, signe = false) =>
  t === null || t === undefined ? "—" : `${signe && t >= 0 ? "+" : ""}${(t * 100).toFixed(1).replace(".", ",")} %`;

// Les quatre chiffres de la période d'une vue, chacun en euros et en pourcentage.
export function tuilesHtml(vue) {
  const fraisNote = vue.frais === null
    ? "inconnus (relevé de situation seul)"
    : `${vue.frais_sur_partie ? "du versé des contrats à relevés annuels" : "du versé, sur toute la période"} ; soit ${pct(vue.frais_par_an)} par an des sommes placées`;
  const tuiles = [
    ["Versé", euros(vue.verse), pct(vue.part_verse), "du versé du foyer"],
    ["Valeur aujourd'hui", euros(vue.valeur), pct(vue.part_valeur), "des placements du foyer"],
    ["Gagné, frais déduits", eurosSignes(vue.gain), pct(vue.gain_taux, true),
      `du versé, sur toute la période${vue.gain_par_an === null ? "" : ` ; soit ${pct(vue.gain_par_an, true)} par an`}`],
    ["Frais payés", euros(vue.frais), pct(vue.frais_taux), fraisNote],
  ];
  return tuiles
    .map(([e, v, p, n]) => `<div class="tuile"><div class="etiquette">${echapper(e)}</div><div class="valeur">${echapper(v)}</div>
      <div class="pct">${echapper(p)}</div><div class="note">${echapper(n)}</div></div>`)
    .join("");
}

// Séries du graphique « gagné et frais payés chaque année ».
export const seriesAnnees = (annees) => [
  { classe: "serie-3", nom: "Gagné (frais déduits)", valeurs: annees.map((a) => a.gain), sous: annees.map((a) => pct(a.gain_taux, true)) },
  { classe: "serie-2", nom: "Frais payés", valeurs: annees.map((a) => a.frais), sous: annees.map((a) => pct(a.frais_taux)) },
];

export function tableAnneesHtml(annees) {
  return `<thead><tr><th>Année</th><th class="n">Versé</th><th class="n">Gagné</th><th class="n">Gagné %</th>
    <th class="n">Frais</th><th class="n">Frais %</th><th class="n">Sommes placées</th></tr></thead><tbody>${annees
      .map((a) => `<tr><td>${a.annee}</td><td class="n">${euros(a.verse)}</td><td class="n">${eurosSignes(a.gain)}</td>
        <td class="n">${pct(a.gain_taux, true)}</td><td class="n">${euros(a.frais)}</td><td class="n">${pct(a.frais_taux)}</td>
        <td class="n">${euros(a.capital)}</td></tr>`)
      .join("")}</tbody>`;
}

// Fonds d'une vue : tous pour le foyer, ceux de la personne, ou ceux du contrat.
export const fondsDeVue = (etat, vue) =>
  etat.fonds.filter((f) =>
    vue.niveau === "foyer" ? true : vue.niveau === "personne" ? f.contrat.startsWith(`${vue.nom} · `) : f.contrat === vue.court,
  );

export function tableFondsHtml(fonds) {
  return `<thead><tr><th>Fonds</th><th>Contrat</th><th class="n">Valeur</th><th class="n">Frais du fonds</th>
    <th class="n">dont rétro.</th><th class="n">Frais totaux</th><th class="n">Coût / an</th><th class="n">Perf. nette</th></tr></thead><tbody>${fonds
      .map((f) => `<tr><td>${echapper(f.fonds)}</td><td>${echapper(f.contrat)}</td><td class="n">${euros(f.valeur)}</td>
        <td class="n">${pct(f.frais_fonds)}</td><td class="n">${pct(f.retrocessions)}</td><td class="n">${pct(f.frais_totaux)}</td>
        <td class="n">${euros(f.cout_annuel)}</td><td class="n">${pct(f.performance_nette, true)}</td></tr>`)
      .join("") || `<tr><td colspan="8">Aucun fonds détaillé (relevé de situation seul).</td></tr>`}</tbody>`;
}

export const noteSansHistorique = (vue) =>
  vue.sans_historique.length && vue.annees.length
    ? `Les années ne comprennent pas ${vue.sans_historique.join(", ")} : pas de relevé année par année.`
    : "";

export const MENTION =
  "Gagné : valeur aujourd'hui moins versé, tous frais déjà déduits. Pourcentages de l'année : par rapport aux sommes " +
  "placées dans l'année. Par an : moyenne annuelle depuis l'ouverture. Frais des fonds : estimés. Éléments d'aide à la " +
  "décision, pas un conseil financier.";

const CLASSES_FAMILLES = { "Placements": "serie-1", "Épargne disponible": "serie-3", "Comptes courants": "serie-2" };
const dateCourte = (iso) => new Date(iso).toLocaleDateString("fr-FR");

// Patrimoine d'une vue : total, une tuile par famille, barre de répartition, liste de tous les comptes.
export function patrimoineHtml(p, { sansNumero = false } = {}) {
  const nom = (texte) => (sansNumero ? texte.replace(/\s*\*+\d+/g, "") : texte);
  const tuiles = [["Patrimoine total", euros(p.total), "100,0 %", "placements, épargne disponible et comptes courants"],
    ...p.familles.map((f) => [f.famille, euros(f.montant), pct(f.part), f.explication])];
  let x = 0;
  const segments = p.familles.map((f) => {
    const largeur = (f.part ?? 0) * 640;
    const segment = `<rect x="${x + (x ? 1 : 0)}" y="0" width="${Math.max(largeur - (x ? 1 : 0), 1)}" height="22" rx="4" class="${CLASSES_FAMILLES[f.famille]}"/>`;
    x += largeur;
    return segment;
  }).join("");
  const legende = p.familles.map((f) => `<span><i class="pastille ${CLASSES_FAMILLES[f.famille]}"></i>${echapper(f.famille)} ${pct(f.part)}</span>`).join("");
  const lignes = p.lignes.map((l) => `<tr><td>${echapper(nom(l.nom))}</td><td>${echapper(l.famille)}</td>
    <td class="n">${euros(l.valeur)}</td><td class="n">${pct(l.part)}</td><td class="n">${dateCourte(l.date)}</td></tr>`).join("");
  return `<div class="tuiles">${tuiles.map(([e, v, q, n]) => `<div class="tuile"><div class="etiquette">${echapper(e)}</div>
      <div class="valeur">${echapper(v)}</div><div class="pct">${echapper(q)}</div><div class="note">${echapper(n)}</div></div>`).join("")}</div>
    <figure class="repartition"><div class="legende">${legende}</div>
      <svg viewBox="0 0 640 22" preserveAspectRatio="none" role="img" aria-label="Répartition du patrimoine">${segments}</svg></figure>
    <div class="defile"><table><thead><tr><th>Compte</th><th>Famille</th><th class="n">Valeur</th><th class="n">Part</th>
      <th class="n">Au</th></tr></thead><tbody>${lignes}</tbody></table></div>`;
}

// Livrets d'une vue : solde, intérêts de la dernière année versée, intérêts attendus, plafond.
export function livretsHtml(livrets, { sansNumero = false } = {}) {
  const nom = (texte) => (sansNumero ? texte.replace(/\s*\*+\d+/g, "") : texte);
  const lignes = livrets.map((l) => {
    const verse = l.interets.filter((i) => i.interets !== null).at(-1);
    const enCours = l.interets.find((i) => i.estimation !== null);
    return `<tr><td>${echapper(nom(l.nom))}</td><td class="n">${euros(l.solde)}</td>
      <td class="n">${verse ? `${euros(verse.interets)} (${verse.annee})` : "—"}</td><td class="n">${pct(verse?.taux)}</td>
      <td class="n">${pct(verse?.taux_reglemente)}</td>
      <td class="n">${enCours ? `≈ ${euros(enCours.estimation)} (${pct(enCours.taux_reglemente)})` : "—"}</td>
      <td class="n">${l.plafond === null ? "—" : `${pct(l.part_plafond)} de ${euros(l.plafond)}`}</td></tr>`;
  }).join("");
  return `<div class="defile"><table><thead><tr><th>Livret</th><th class="n">Solde</th><th class="n">Intérêts versés</th>
    <th class="n">Taux obtenu</th><th class="n">Taux réglementé moyen</th><th class="n">Attendus cette année</th>
    <th class="n">Plafond rempli</th></tr></thead><tbody>${lignes}</tbody></table></div>
    <p class="note">Intérêts versés début janvier pour l'année précédente. Taux obtenu : intérêts / solde moyen de
    l'année. Au-delà du plafond, plus de versement possible ; les intérêts continuent de s'ajouter.</p>`;
}

export const livretsDeVue = (etat, vue) =>
  (etat.banque ?? []).filter((c) => c.type !== "courant" && (vue.niveau === "foyer" || c.titulaire === vue.nom));

// Synthèse de l'épargne disponible d'une vue : quatre chiffres, chacun en euros et en pourcentage.
export function epargneHtml(e) {
  const tuiles = [
    ["Épargne disponible", euros(e.solde), pct(e.part_patrimoine), `du patrimoine ; ${e.nombre} livret${e.nombre > 1 ? "s" : ""}, disponibles à tout moment`],
    [`Intérêts ${e.annee_interets ?? ""}`, euros(e.interets), pct(e.taux_obtenu),
      `taux obtenu, pour un taux réglementé moyen de ${pct(e.taux_reglemente)}`],
    [`Intérêts ${e.annee_attendue ?? ""} attendus`, e.attendus === null ? "—" : `≈ ${euros(e.attendus)}`, pct(e.taux_attendu),
      `taux moyen de l'année ; versés début janvier, si les soldes ne bougent pas`],
    ["Plafonds", euros(e.plafond), pct(e.part_plafond),
      e.versements_possibles > 0 ? `remplis ; encore ${euros(e.versements_possibles)} de versements possibles` : "remplis : plus de versement possible"],
  ];
  return `<div class="tuiles">${tuiles.map(([t, v, q, n]) => `<div class="tuile"><div class="etiquette">${echapper(t)}</div>
    <div class="valeur">${echapper(v)}</div><div class="pct">${echapper(q)}</div><div class="note">${echapper(n)}</div></div>`).join("")}</div>`;
}
