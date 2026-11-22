// Graphiques SVG sans bibliothèque : barres groupées par année et courbes, avec lecture au survol.

export const echapper = (texte) =>
  String(texte ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const legende = (series) =>
  `<div class="legende">${series
    .map((s) => `<span><i class="pastille ${s.classe}"></i>${echapper(s.nom)}</span>`)
    .join("")}</div>`;

// Barres côte à côte par année ; chaque barre porte sa valeur et, dessous, une seconde étiquette (le %).
// series : [{classe, nom, valeurs: [nombre|null], sous: [texte]}] ; survol(rang) appelé au survol d'une année.
export function barresGroupees(figure, { titre, annees, series, formater, survol }) {
  const L = 640, H = 260, HAUT = 44, BAS = 26, ECART = 2, LIGNE = 13;
  const valeurs = series.flatMap((s) => s.valeurs.filter((v) => v !== null));
  const bas = Math.min(0, ...valeurs), haut = Math.max(0, ...valeurs);
  const etendue = haut - bas || 1;
  const y = (v) => HAUT + ((haut - v) / etendue) * (H - HAUT - BAS);
  const pas = L / Math.max(annees.length, 1);
  const barre = Math.min(64, (pas * 0.7) / series.length);
  const parties = [`<line x1="0" y1="${y(0)}" x2="${L}" y2="${y(0)}" class="axe"/>`];
  annees.forEach((annee, rang) => {
    const centre = pas * (rang + 0.5);
    const gauche = centre - (barre * series.length) / 2 - (ECART * (series.length - 1)) / 2;
    series.forEach((s, numero) => {
      const v = s.valeurs[rang];
      if (v === null || v === undefined) return;
      const x = gauche + numero * (barre + ECART);
      const dessus = Math.max(v, 0), dessous = Math.min(v, 0);
      const sous = s.sous?.[rang] ?? "";
      parties.push(`<rect x="${x}" y="${y(dessus)}" width="${barre}" height="${Math.max(y(dessous) - y(dessus), 1)}" rx="4" class="${s.classe}"/>`);
      const yTexte = v >= 0 ? y(dessus) - 6 - (sous ? LIGNE : 0) : y(dessous) + 14;
      const ligne2 = sous ? `<tspan x="${x + barre / 2}" dy="${LIGNE}" class="sous">${echapper(sous)}</tspan>` : "";
      parties.push(`<text x="${x + barre / 2}" y="${yTexte}" class="valeur-barre" text-anchor="middle">${echapper(formater(v))}${ligne2}</text>`);
    });
    parties.push(`<text x="${centre}" y="${H - 6}" class="graduation" text-anchor="middle">${annee}</text>`);
    parties.push(`<rect x="${pas * rang}" y="0" width="${pas}" height="${H}" class="cible" data-rang="${rang}"/>`);
  });
  figure.innerHTML = `<figcaption>${echapper(titre)}</figcaption>${legende(series)}
    <svg viewBox="0 0 ${L} ${H}" role="img" aria-label="${echapper(titre)}">${parties.join("")}</svg>`;
  if (survol) {
    figure.querySelectorAll("rect.cible").forEach((r) => {
      r.addEventListener("mouseenter", () => survol(Number(r.dataset.rang)));
      r.addEventListener("mouseleave", () => survol(null));
    });
  }
}

// Courbes sur un axe x commun (0..n) ; survol(rang) au déplacement de la souris ; un repère suit le curseur.
export function courbes(figure, { titre, abscisses, series, formater, legendeX, survol }) {
  const L = 640, H = 280, G = 64, D = 12, HAUT = 12, BAS = 28;
  const valeurs = series.flatMap((s) => s.valeurs);
  const bas = Math.min(...valeurs) * 0.95, haut = Math.max(...valeurs) * 1.02;
  const etendue = haut - bas || 1;
  const x = (rang) => G + (rang / Math.max(abscisses.length - 1, 1)) * (L - G - D);
  const y = (v) => HAUT + ((haut - v) / etendue) * (H - HAUT - BAS);
  const parties = [];
  for (let i = 0; i <= 4; i++) {
    const v = bas + (etendue * i) / 4;
    parties.push(`<line x1="${G}" y1="${y(v)}" x2="${L - D}" y2="${y(v)}" class="grille"/>`);
    parties.push(`<text x="${G - 6}" y="${y(v) + 4}" class="graduation" text-anchor="end">${echapper(formater(v))}</text>`);
  }
  const etape = Math.ceil(abscisses.length / 8);
  const dernier = abscisses.length - 1;
  abscisses.forEach((a, rang) => {
    // Le dernier libellé remplace le précédent s'il en est trop proche (« 14 ans » et « 15 ans » se chevauchaient).
    const garde = rang === dernier || (rang % etape === 0 && dernier - rang >= Math.max(etape / 2, 1) * 1.5);
    if (garde) {
      parties.push(`<text x="${x(rang)}" y="${H - 8}" class="graduation" text-anchor="middle">${echapper(legendeX(a))}</text>`);
    }
  });
  series.forEach((s) => {
    const d = s.valeurs.map((v, rang) => `${rang ? "L" : "M"}${x(rang).toFixed(1)},${y(v).toFixed(1)}`).join("");
    parties.push(`<path d="${d}" class="courbe ${s.classe}"/>`);
  });
  parties.push(`<line class="curseur cache" y1="${HAUT}" y2="${H - BAS}"/>`);
  series.forEach((s) => parties.push(`<circle r="5" class="repere cache ${s.classe}"/>`));
  parties.push(`<rect x="${G}" y="0" width="${L - G - D}" height="${H}" class="cible"/>`);
  figure.innerHTML = `<figcaption>${echapper(titre)}</figcaption>${legende(series)}
    <svg viewBox="0 0 ${L} ${H}" role="img" aria-label="${echapper(titre)}">${parties.join("")}</svg>`;
  const svg = figure.querySelector("svg");
  const curseur = svg.querySelector(".curseur");
  const reperes = [...svg.querySelectorAll("circle.repere")];
  const cible = svg.querySelector("rect.cible");
  cible.addEventListener("mousemove", (evenement) => {
    const boite = svg.getBoundingClientRect();
    const px = ((evenement.clientX - boite.left) / boite.width) * L;
    const rang = Math.round(((px - G) / (L - G - D)) * (abscisses.length - 1));
    const borne = Math.min(Math.max(rang, 0), abscisses.length - 1);
    curseur.setAttribute("x1", x(borne));
    curseur.setAttribute("x2", x(borne));
    curseur.classList.remove("cache");
    reperes.forEach((c, i) => {
      c.setAttribute("cx", x(borne));
      c.setAttribute("cy", y(series[i].valeurs[borne]));
      c.classList.remove("cache");
    });
    survol?.(borne);
  });
  cible.addEventListener("mouseleave", () => {
    curseur.classList.add("cache");
    reperes.forEach((c) => c.classList.add("cache"));
    survol?.(null);
  });
}
