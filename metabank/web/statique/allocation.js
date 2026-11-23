// Onglet « Allocation » : répartition, concentration, cible, rééquilibrage (calculés en Python, MODELE § 13).
import { courbes, echapper } from "./graphiques.js";
import { euros, eurosSignes, pct } from "./rendu.js";

const $ = (id) => document.getElementById(id);
let allocation = null;

async function appeler(chemin, corps) {
  const options = corps === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json", "X-Metabank": "1" }, body: JSON.stringify(corps),
  };
  const reponse = await fetch(chemin, options);
  const donnees = await reponse.json();
  if (!reponse.ok) throw new Error(donnees.erreur || `erreur ${reponse.status}`);
  return donnees;
}

function remplirArbitrage(a) {
  const fonds = a.positions.map((p, rang) => ({ ...p, rang }));
  $("arb-source").innerHTML = fonds.map((p) => `<option value="${p.rang}">${echapper(p.libelle)} · ${echapper(p.contrat)} (${euros(p.valeur)})</option>`).join("");
  choisirSource();
}

function choisirSource() {
  const source = allocation.positions[Number($("arb-source").value)];
  if (!source) return;
  $("arb-montant").value = Math.round(source.valeur);
  $("arb-frais-source").value = source.frais_totaux ?? "";
  const memeContrat = allocation.positions.map((p, rang) => ({ ...p, rang }))
    .filter((p) => p.contrat === source.contrat && p.titulaire === source.titulaire && p.libelle !== source.libelle);
  $("arb-cible").innerHTML = [...memeContrat.map((p) => `<option value="${p.rang}">${echapper(p.libelle)}</option>`),
    `<option value="">Autre fonds (frais à saisir)</option>`].join("");
  choisirCible();
}

function choisirCible() {
  const cible = $("arb-cible").value === "" ? null : allocation.positions[Number($("arb-cible").value)];
  $("arb-frais-cible").value = cible?.frais_totaux ?? "";
}

async function simulerArbitrage() {
  for (const [id, quoi] of [["arb-frais-source", "du fonds vendu"], ["arb-frais-cible", "du fonds visé"]]) {
    if ($(id).value === "") {
      $("arb-resultat").innerHTML = `<p class="ko">Saisissez les frais ${quoi} : le relevé ne les donne pas (fonds en euros, ou relevé sans tableau des frais).</p>`;
      return;
    }
  }
  const saisie = Object.fromEntries(["montant", "frais_source", "frais_cible", "frais_arbitrage", "rendement", "horizon"]
    .map((cle) => [cle, $(`arb-${cle.replace("_", "-")}`).value]));
  try {
    const r = await appeler("/api/arbitrage", saisie);
    const mieux = r.ecart >= 0 ? "de plus en arbitrant" : "de moins en arbitrant";
    $("arb-resultat").innerHTML = `<p><strong>${euros(Math.abs(r.ecart))} ${mieux}</strong> au bout de ${saisie.horizon} ans ;
      coût immédiat ${euros(r.cout_immediat)} ; ${r.point_mort === null ? "pas de point mort sur la durée" : `point mort au bout de ${r.point_mort} an${r.point_mort > 1 ? "s" : ""}`}.</p>`;
    courbes($("arb-graphique"), {
      titre: "Valeur du montant arbitré", abscisses: r.garder.map((_, annee) => annee), legendeX: (annee) => `${annee} ans`,
      series: [{ classe: "serie-1", nom: "Garder", valeurs: r.garder }, { classe: "serie-3", nom: "Arbitrer", valeurs: r.arbitrer }],
      formater: euros, survol: () => {},
    });
  } catch (erreur) {
    $("arb-resultat").innerHTML = `<p class="ko">${echapper(erreur.message)}</p>`;
  }
}

const centimes = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const date = (iso) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`;

function montrer(a) {
  allocation = a;
  remplirArbitrage(a);
  $("alloc-titulaire").innerHTML = [`<option value="">Foyer</option>`, ...a.titulaires.map((t) => `<option>${echapper(t)}</option>`)].join("");
  $("alloc-titulaire").value = a.titulaire;
  const aClasser = a.positions.filter((p) => p.classe === "À classer");
  $("alloc-alertes").innerHTML = [
    ...a.concentrations.map((c) => `<p class="alerte">${echapper(c.libelle)} (${echapper(c.contrat)}) pèse ${pct(c.part)} du patrimoine financier.</p>`),
    ...Object.entries(a.derives).map(([c, e]) => `<p class="alerte">${echapper(c)} s'écarte de sa cible de ${pct(e, true)}.</p>`),
    ...a.positions.filter((p) => p.coupon_attendu_le).map((p) => `<p class="alerte">${echapper(p.libelle)} (${echapper(p.titulaire)} · ${echapper(p.contrat)}) :
      aucun coupon depuis le ${date(p.dernier_coupon)}, le suivant était attendu vers le ${date(p.coupon_attendu_le)}. Le versement
      d'un coupon peut dépendre d'une condition : voir le document d'information du fonds.</p>`),
    aClasser.length ? `<p class="alerte">${aClasser.length} fonds à classer : choisissez leur classe plus bas.</p>` : "",
  ].join("") || `<p class="discret">Aucun fonds ne dépasse 20 % du patrimoine financier.</p>`;
  $("alloc-repartition").innerHTML = `<thead><tr><th>Classe</th><th class="n">Montant</th><th class="n">Part</th><th class="n">Part des fonds</th>
    <th class="n">Cible (%)</th><th class="n">Écart</th><th class="n">À verser</th></tr></thead><tbody>${a.repartition
    .map((r) => {
      const classe = a.classes.includes(r.nom) && r.nom !== "À classer";
      const ecart = r.cible === null || r.cible === undefined || r.part_supports === null ? "—" : pct(r.part_supports - r.cible / 100, true);
      return `<tr><td>${echapper(r.nom)}</td><td class="n">${euros(r.montant)}</td><td class="n">${pct(r.part)}</td>
        <td class="n">${r.part_supports === null ? "—" : pct(r.part_supports)}</td>
        <td class="n">${classe ? `<input type="number" min="0" max="100" step="5" data-cible="${echapper(r.nom)}" value="${r.cible ?? ""}">` : ""}</td>
        <td class="n">${ecart}</td><td class="n">${a.a_verser[r.nom] ? euros(a.a_verser[r.nom]) : "—"}</td></tr>`;
    }).join("")}</tbody>`;
  $("alloc-versements").textContent = a.total_a_verser ? `Versements pour atteindre la cible sans rien vendre : ${euros(a.total_a_verser)} au total.` : "";
  const options = (choisie) => a.classes.map((c) => `<option ${c === choisie ? "selected" : ""}>${echapper(c)}</option>`).join("");
  $("alloc-positions").innerHTML = `<thead><tr><th>Fonds</th><th>Contrat</th><th class="n">Valeur</th>
    <th class="n">Prix de revient d'une part</th><th class="n">+/- latente</th><th class="n">Coupons reçus</th><th class="n">Net</th>
    <th>Classe</th></tr></thead><tbody>${a.positions
    .map((p) => `<tr><td>${echapper(p.libelle)}</td><td>${echapper(p.titulaire)} · ${echapper(p.contrat)}</td><td class="n">${euros(p.valeur)}</td>
      <td class="n">${p.prix_de_revient === null ? "—" : `${centimes.format(p.prix_de_revient)} €`}</td>
      <td class="n">${p.plus_value === null ? "—" : `${eurosSignes(p.plus_value)} (${pct(p.plus_value_taux, true)})`}</td>
      <td class="n">${p.coupons ? euros(p.coupons) : "—"}</td><td class="n">${eurosSignes(p.net)}</td>
      <td><select data-classe="${echapper(p.cle)}" data-choisie="${p.choisie}">${options(p.classe)}</select>${p.choisie ? "" : ' <span class="note">déduite</span>'}</td></tr>`)
    .join("")}</tbody>`;
}

export async function afficherAllocation(titulaire = $("alloc-titulaire").value || "") {
  montrer(await appeler(`/api/allocation?titulaire=${encodeURIComponent(titulaire)}`));
}

export function preparerAllocation() {
  $("arb-source").addEventListener("change", choisirSource);
  $("arb-cible").addEventListener("change", choisirCible);
  $("arb-simuler").addEventListener("click", simulerArbitrage);
  $("alloc-titulaire").addEventListener("change", () => afficherAllocation($("alloc-titulaire").value));
  $("enregistrer-allocation").addEventListener("click", async () => {
    const classes = {};
    document.querySelectorAll("[data-classe]").forEach((s) => {
      const deduite = allocation.positions.find((p) => p.cle === s.dataset.classe);
      if (s.dataset.choisie === "true" || s.value !== deduite?.classe) classes[s.dataset.classe] = s.value;
    });
    const cible = {};
    document.querySelectorAll("[data-cible]").forEach((i) => { if (i.value !== "") cible[i.dataset.cible] = Number(i.value); });
    const message = $("etat-allocation");
    try {
      montrer(await appeler("/api/allocation", { classes, cible, titulaire: $("alloc-titulaire").value }));
      message.className = "ok";
      message.textContent = "Enregistré.";
    } catch (erreur) {
      message.className = "ko";
      message.textContent = `Non enregistré : ${erreur.message}`;
    }
  });
}
