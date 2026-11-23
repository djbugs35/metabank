// Graphiques SVG sans bibliothèque : barres groupées par année et courbes, avec lecture au survol.

export const echapper = (texte) =>
  String(texte ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const legende = (series) =>
  `<div class="legende">${series
    .map((s) => `<span><i class="pastille ${s.classe}"></i>${echapper(s.nom)}</span>`)
    .join("")}</div>`;

// Barres côte à côte par année ; chaque barre porte sa valeur et, dessous, une seconde étiquette (le %).
// series : [{classe, nom, valeurs: [nombre|null], sous: [texte]}] ; survol(rang) appelé au survol d'une année.
export function barresGroupees(figure, { titre, annees, series, formater, survol, etiquettes = true }) {
  const L = 640, H = 260, HAUT = etiquettes ? 44 : 12, BAS = 26, ECART = 2, LIGNE = 13;
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
      if (!etiquettes) return;
      const yTexte = v >= 0 ? y(dessus) - 6 - (sous ? LIGNE : 0) : y(dessous) + 14;
      const ligne2 = sous ? `<tspan x="${x + barre / 2}" dy="${LIGNE}" class="sous">${echapper(sous)}</tspan>` : "";
      parties.push(`<text x="${x + barre / 2}" y="${yTexte}" class="valeur-barre" text-anchor="middle">${echapper(formater(v))}${ligne2}</text>`);
    });
    const pasEtiquette = Math.ceil(annees.length / 12);
    if (rang % pasEtiquette === 0) {
      parties.push(`<text x="${centre}" y="${H - 6}" class="graduation" text-anchor="middle">${echapper(annee)}</text>`);
    }
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
// Pas « rond » de l'axe (1, 2, 2,5 ou 5 × 10^n) pour environ quatre intervalles entre min et max.
function pasRond(etendue) {
  const brut = etendue / 4 || 1;
  const puissance = 10 ** Math.floor(Math.log10(brut));
  return puissance * ([1, 2, 2.5, 5, 10].find((m) => m * puissance >= brut) ?? 10);
}

// Libellé court d'une graduation, pour tenir dans la marge : « 1,25 M€ », « 850 k€ », « 300 € ».
export function eurosCourts(v) {
  const abs = Math.abs(v);
  const nombre = (n, decimales) => n.toLocaleString("fr-FR", { maximumFractionDigits: decimales });
  if (abs >= 1e6) return `${nombre(v / 1e6, 2)} M€`;
  if (abs >= 1e4) return `${nombre(v / 1e3, 0)} k€`;
  return `${nombre(v, 0)} €`;
}

export function courbes(figure, { titre, abscisses, series, formater, legendeX, survol, formaterAxe = null }) {
  const L = 640, H = 280, G = 64, D = 12, HAUT = 12, BAS = 28;
  const valeurs = series.flatMap((s) => s.valeurs);
  const pas = pasRond(Math.max(...valeurs) - Math.min(...valeurs));
  const bas = Math.floor(Math.min(...valeurs) / pas) * pas, haut = Math.ceil(Math.max(...valeurs) / pas) * pas || pas;
  const etendue = haut - bas || 1;
  const graduation = formaterAxe ?? ((v) => (Math.abs(v) >= 1e4 ? eurosCourts(v) : formater(v)));
  const x = (rang) => G + (rang / Math.max(abscisses.length - 1, 1)) * (L - G - D);
  const y = (v) => HAUT + ((haut - v) / etendue) * (H - HAUT - BAS);
  const parties = [];
  for (let v = bas; v <= haut + pas / 2; v += pas) {
    parties.push(`<line x1="${G}" y1="${y(v)}" x2="${L - D}" y2="${y(v)}" class="grille"/>`);
    parties.push(`<text x="${G - 6}" y="${y(v) + 4}" class="graduation" text-anchor="end">${echapper(graduation(v))}</text>`);
  }
  const etape = Math.ceil(abscisses.length / 8);
  const dernier = abscisses.length - 1;
  abscisses.forEach((a, rang) => {
    // Le dernier libellé remplace le précédent s'il en est trop proche (« 14 ans » et « 15 ans » se chevauchaient).
    const garde = rang === dernier || (rang % etape === 0 && dernier - rang >= Math.max(etape / 2, 1) * 1.5);
    if (garde) {
      const ancre = rang === dernier ? "end" : rang === 0 ? "start" : "middle";
      parties.push(`<text x="${x(rang)}" y="${H - 8}" class="graduation" text-anchor="${ancre}">${echapper(legendeX(a))}</text>`);
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

// Barres empilées par colonne : chaque part part du haut de la précédente, vers le bas si elle est négative (classe
// « classeNegative » alors) ; au-dessus, le total et une seconde étiquette. parts : [{classe, classeNegative, nom,
// valeurs}] ; totaux et sous : un par colonne ; survol(rang) au survol d'une colonne. Avec « diverge », les parts
// positives montent depuis zéro et les négatives descendent depuis zéro (hausses et baisses de chaque contrat).
export function barresEmpilees(figure, { titre, abscisses, parts, totaux, sous, formater, survol, diverge = false }) {
  const L = 640, H = 300, G = 64, D = 12, HAUT = 40, BAS = 26, LIGNE = 13;
  const piles = abscisses.map((_, rang) => {
    let base = 0, dessus = 0, dessous = 0;
    return parts.map((p) => {
      const v = p.valeurs[rang] ?? 0;
      if (diverge) {
        const depart = v >= 0 ? dessus : dessous;
        if (v >= 0) dessus += v; else dessous += v;
        return { v, bas: Math.min(depart, depart + v), haut: Math.max(depart, depart + v) };
      }
      const depart = base;
      base += v;
      return { v, bas: Math.min(depart, base), haut: Math.max(depart, base) };
    });
  });
  const bornes = piles.flatMap((pile) => pile.flatMap((s) => [s.bas, s.haut]));
  const pas = pasRond(Math.max(0, ...bornes, ...totaux) - Math.min(0, ...bornes));
  const bas = Math.floor(Math.min(0, ...bornes) / pas) * pas, haut = Math.ceil(Math.max(0, ...bornes, ...totaux) / pas) * pas || pas;
  const y = (v) => HAUT + ((haut - v) / (haut - bas || 1)) * (H - HAUT - BAS);
  const colonne = (L - G - D) / Math.max(abscisses.length, 1);
  const largeur = Math.min(72, colonne * 0.6);
  const parties = [];
  for (let v = bas; v <= haut + pas / 2; v += pas) {
    parties.push(`<line x1="${G}" y1="${y(v)}" x2="${L - D}" y2="${y(v)}" class="${v === 0 ? "axe" : "grille"}"/>`);
    parties.push(`<text x="${G - 6}" y="${y(v) + 4}" class="graduation" text-anchor="end">${echapper(eurosCourts(v))}</text>`);
  }
  piles.forEach((pile, rang) => {
    const centre = G + colonne * (rang + 0.5), x = centre - largeur / 2;
    pile.forEach((s, numero) => {
      const classe = s.v < 0 ? parts[numero].classeNegative ?? parts[numero].classe : parts[numero].classe;
      if (s.haut > s.bas) parties.push(`<rect x="${x}" y="${y(s.haut)}" width="${largeur}" height="${Math.max(y(s.bas) - y(s.haut), 1)}" class="${classe}"/>`);
    });
    const sommet = y(Math.max(0, ...pile.map((s) => s.haut), totaux[rang])) - 6 - LIGNE;
    parties.push(`<text x="${centre}" y="${sommet}" class="valeur-barre" text-anchor="middle">${echapper(formater(totaux[rang]))}`
      + `<tspan x="${centre}" dy="${LIGNE}" class="sous">${echapper(sous[rang] ?? "")}</tspan></text>`);
    parties.push(`<text x="${centre}" y="${H - 6}" class="graduation" text-anchor="middle">${echapper(abscisses[rang])}</text>`);
    parties.push(`<rect x="${G + colonne * rang}" y="0" width="${colonne}" height="${H}" class="cible" data-rang="${rang}"/>`);
  });
  const legendes = parts.flatMap((p) => [p, ...(p.classeNegative && p.valeurs.some((v) => v < 0) ? [{ classe: p.classeNegative, nom: p.nomNegatif }] : [])]);
  figure.innerHTML = `<figcaption>${echapper(titre)}</figcaption>${legende(legendes)}
    <svg viewBox="0 0 ${L} ${H}" role="img" aria-label="${echapper(titre)}">${parties.join("")}</svg>`;
  figure.querySelectorAll("rect.cible").forEach((r) => {
    r.addEventListener("mouseenter", () => survol?.(Number(r.dataset.rang)));
    r.addEventListener("mouseleave", () => survol?.(null));
  });
}

// Barres horizontales triées : une ligne par catégorie, montant et part écrits à droite de la barre.
export function barresHorizontales(figure, { titre, lignes, formater }) {
  const L = 640, LIGNE = 26, G = 190, D = 150;
  const H = LIGNE * lignes.length + 8;
  const max = Math.max(...lignes.map((l) => l.valeur), 1);
  const parties = lignes.map((l, rang) => {
    const y = 4 + rang * LIGNE;
    const largeur = Math.max(((L - G - D) * l.valeur) / max, 1);
    return `<text x="${G - 8}" y="${y + 16}" class="graduation" text-anchor="end">${echapper(l.nom)}</text>
      <rect x="${G}" y="${y + 4}" width="${largeur}" height="${LIGNE - 8}" rx="4" class="serie-1"/>
      <text x="${G + largeur + 6}" y="${y + 16}" class="valeur-barre">${echapper(formater(l.valeur))}<tspan class="sous" dx="6">${echapper(l.sous ?? "")}</tspan></text>`;
  });
  figure.innerHTML = `<figcaption>${echapper(titre)}</figcaption>
    <svg viewBox="0 0 ${L} ${H}" role="img" aria-label="${echapper(titre)}">${parties.join("")}</svg>`;
}
