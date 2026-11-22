// Onglet « Comptes » : compte courant, Livret A, LDD. Les chiffres viennent de l'API (banque/analyse.py, testé).
import { barresGroupees, barresHorizontales, courbes, echapper } from "./graphiques.js";
import { euros, eurosSignes, pct } from "./rendu.js";

const $ = (id) => document.getElementById(id);
const NOMS_MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
const libelleMois = (cle) => `${NOMS_MOIS[Number(cle.slice(5)) - 1]} ${cle.slice(2, 4)}`;
const dateFr = (iso) => new Date(iso).toLocaleDateString("fr-FR");
let choisi = null;

const tuile = ([etiquette, valeur, part, note]) =>
  `<div class="tuile"><div class="etiquette">${echapper(etiquette)}</div><div class="valeur">${echapper(valeur)}</div>
   <div class="pct">${echapper(part)}</div><div class="note">${echapper(note)}</div></div>`;

export function afficherComptes(etat) {
  const comptes = etat.banque ?? [];
  $("comptes-vide").classList.toggle("cache", comptes.length > 0);
  $("comptes-contenu").classList.toggle("cache", !comptes.length);
  if (!comptes.length) return;
  if (!comptes.some((c) => c.id === choisi)) choisi = comptes[0].id;
  const total = comptes.reduce((t, c) => t + c.solde, 0);
  $("comptes-total").textContent = `Liquidités : ${euros(total)} sur ${comptes.length} compte${comptes.length > 1 ? "s" : ""}`;
  $("choix-compte").replaceChildren(...comptes.map((c) => {
    const b = document.createElement("button");
    b.className = "puce";
    b.textContent = c.nom;
    b.setAttribute("aria-pressed", String(c.id === choisi));
    b.addEventListener("click", () => { choisi = c.id; afficherComptes(etat); });
    return b;
  }));
  const compte = comptes.find((c) => c.id === choisi);
  $("compte-periode").textContent = `Du ${dateFr(compte.debut)} au ${dateFr(compte.date_solde)} (${compte.nombre_mois.toFixed(0)} mois), d'après les exports.`;
  if (compte.type === "courant") afficherCourant(compte); else afficherLivret(compte);
  $("compte-anomalies").innerHTML = compte.anomalies.map((a) => `<p class="alerte">${echapper(a)}</p>`).join("");
}

function afficherCourant(c) {
  $("compte-tuiles").innerHTML = [
    ["Solde", euros(c.solde), pct(c.part_liquidites), `des liquidités ; solde moyen ${euros(c.solde_moyen)}`],
    ["Revenus par mois", euros(c.revenus_mois), "100,0 %", "salaires, remboursements et autres entrées"],
    ["Dépenses par mois", euros(c.depenses_mois), pct(c.part_depenses), "des revenus (hors virements entre vos comptes)"],
    ["Épargne placée par mois", euros(c.epargne_mois), pct(c.part_epargne), "des revenus (assurance vie, PER, livrets…)"],
    ["Frais bancaires par an", euros(c.frais_an), pct(c.part_frais), "des revenus"],
    ["Argent qui dort", euros(c.argent_qui_dort), pct(c.part_qui_dort),
      `du solde moyen, au-delà de 2 mois de dépenses (${euros(c.coussin)}) ; ${euros(c.manque_a_gagner)} par an au taux du Livret A (${pct(c.taux_livret_a)})`],
  ].map(tuile).join("");
  afficherSolde(c);
  const mois = c.mois;
  barresGroupees($("compte-flux"), {
    titre: "Revenus et dépenses, mois par mois",
    annees: mois.map((m) => libelleMois(m.mois)),
    series: [
      { classe: "serie-3", nom: "Revenus", valeurs: mois.map((m) => m.revenus) },
      { classe: "serie-2", nom: "Dépenses", valeurs: mois.map((m) => m.depenses) },
    ],
    formater: euros,
    etiquettes: false,
    survol: (rang) => {
      const m = rang === null ? null : mois[rang];
      $("compte-infobulle").textContent = m
        ? `${libelleMois(m.mois)}${m.complet ? "" : " (mois partiel)"} : revenus ${euros(m.revenus)} · dépenses ${euros(m.depenses)} (${pct(m.revenus ? m.depenses / m.revenus : null)}) · épargne placée ${euros(m.epargne)} · vers vos autres comptes ${eurosSignes(-m.interne)}`
        : "";
    },
  });
  barresHorizontales($("compte-categories"), {
    titre: "Dépenses par catégorie, sur la période",
    lignes: c.categories.filter((k) => k.montant > 0).map((k) => ({ nom: k.nom, valeur: k.montant, sous: pct(k.part) })),
    formater: euros,
  });
  $("compte-frais").innerHTML = `<thead><tr><th>Frais bancaires</th><th class="n">Montant sur la période</th></tr></thead><tbody>${c.frais_detail
    .map((f) => `<tr><td>${echapper(f.libelle)}</td><td class="n">${euros(f.montant)}</td></tr>`).join("") || "<tr><td colspan='2'>Aucun.</td></tr>"}</tbody>`;
  $("compte-non-classees").innerHTML = `<thead><tr><th>Libellé</th><th class="n">Nombre</th><th class="n">Montant</th></tr></thead><tbody>${c.non_classees
    .map((o) => `<tr><td>${echapper(o.libelle)}</td><td class="n">${o.nombre}</td><td class="n">${euros(o.montant)}</td></tr>`).join("") || "<tr><td colspan='3'>Tout est classé.</td></tr>"}</tbody>`;
  $("bloc-courant").classList.remove("cache");
  $("bloc-livret").classList.add("cache");
}

function afficherLivret(c) {
  const dernier = c.interets.at(-1);
  $("compte-tuiles").innerHTML = [
    ["Solde", euros(c.solde), pct(c.part_liquidites), `des liquidités ; solde moyen ${euros(c.solde_moyen)}`],
    [`Intérêts ${dernier?.annee ?? ""}`, euros(dernier?.interets), pct(dernier?.taux), "du solde moyen de l'année (taux réellement obtenu)"],
    ["Taux du Livret A", pct(c.taux_livret_a), "", `depuis le ${dateFr(c.taux_livret_a_depuis)}, net d'impôt`],
  ].map(tuile).join("");
  afficherSolde(c);
  $("livret-interets").innerHTML = `<thead><tr><th>Année</th><th class="n">Intérêts</th><th class="n">Solde moyen</th><th class="n">Taux obtenu</th></tr></thead><tbody>${c.interets
    .map((i) => `<tr><td>${i.annee}</td><td class="n">${euros(i.interets)}</td><td class="n">${euros(i.solde_moyen)}</td><td class="n">${pct(i.taux)}</td></tr>`).join("")}</tbody>`;
  $("bloc-courant").classList.add("cache");
  $("bloc-livret").classList.remove("cache");
}

function afficherSolde(c) {
  courbes($("compte-solde"), {
    titre: "Solde en fin de mois",
    abscisses: c.mois.map((m) => m.mois),
    legendeX: libelleMois,
    series: [{ classe: "serie-1", nom: "Solde", valeurs: c.mois.map((m) => m.solde_fin) }],
    formater: euros,
    survol: (rang) => {
      $("compte-solde-infobulle").textContent = rang === null ? "" : `Fin ${libelleMois(c.mois[rang].mois)} : ${euros(c.mois[rang].solde_fin)}`;
    },
  });
}
