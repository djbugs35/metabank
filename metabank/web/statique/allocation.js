// Onglet « Allocation » : répartition, concentration, cible, rééquilibrage (calculés en Python, MODELE § 13).
import { echapper } from "./graphiques.js";
import { euros, pct } from "./rendu.js";

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

function montrer(a) {
  allocation = a;
  $("alloc-titulaire").innerHTML = [`<option value="">Foyer</option>`, ...a.titulaires.map((t) => `<option>${echapper(t)}</option>`)].join("");
  $("alloc-titulaire").value = a.titulaire;
  const aClasser = a.positions.filter((p) => p.classe === "À classer");
  $("alloc-alertes").innerHTML = [
    ...a.concentrations.map((c) => `<p class="alerte">${echapper(c.libelle)} (${echapper(c.contrat)}) pèse ${pct(c.part)} du patrimoine financier.</p>`),
    ...Object.entries(a.derives).map(([c, e]) => `<p class="alerte">${echapper(c)} s'écarte de sa cible de ${pct(e, true)}.</p>`),
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
  $("alloc-positions").innerHTML = `<thead><tr><th>Fonds</th><th>Contrat</th><th class="n">Valeur</th><th>Classe</th></tr></thead><tbody>${a.positions
    .map((p) => `<tr><td>${echapper(p.libelle)}</td><td>${echapper(p.titulaire)} · ${echapper(p.contrat)}</td><td class="n">${euros(p.valeur)}</td>
      <td><select data-classe="${echapper(p.cle)}" data-choisie="${p.choisie}">${options(p.classe)}</select>${p.choisie ? "" : ' <span class="note">déduite</span>'}</td></tr>`)
    .join("")}</tbody>`;
}

export async function afficherAllocation(titulaire = $("alloc-titulaire").value || "") {
  montrer(await appeler(`/api/allocation?titulaire=${encodeURIComponent(titulaire)}`));
}

export function preparerAllocation() {
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
