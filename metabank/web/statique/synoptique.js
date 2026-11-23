// Onglet « Synoptique » : fraîcheur et journal de chaque compte (calculés en Python, MODELE § 9).
import { echapper } from "./graphiques.js";

const $ = (id) => document.getElementById(id);
const FRAICHEUR = {
  a_jour: ["à jour", "pastille-ok"], en_retard: ["en retard", "pastille-alerte"],
  tres_en_retard: ["très en retard", "pastille-ko"], jamais: ["jamais", "pastille-vide"],
};
const RESULTATS = { ok: "réussi", refus: "refusé", erreur: "en erreur" };
const dateFr = (iso) => (iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}` : "—");

function age(iso, aujourdhui) {
  if (!iso) return "";
  const jours = Math.round((Date.parse(aujourdhui) - Date.parse(iso)) / 86400000);
  return jours <= 0 ? "aujourd'hui" : `il y a ${jours} j`;
}

function detail(c) {
  const journal = c.journal.length
    ? `<table><thead><tr><th>Le</th><th>Connecteur</th><th>Résultat</th><th>Éléments</th><th>Fichier ou message</th></tr></thead><tbody>${c.journal
        .map((e) => `<tr><td>${dateFr(e.le)}</td><td>${echapper(e.connecteur)}</td><td class="${e.resultat === "ok" ? "ok" : "ko"}">${RESULTATS[e.resultat] ?? e.resultat}</td>
          <td class="nombre">${e.elements}</td><td>${echapper(e.message || e.fichier)}</td></tr>`).join("")}</tbody></table>`
    : `<p class="discret">Aucun import dans le journal.</p>`;
  return `<tr class="detail cache" data-detail="${echapper(c.cle)}"><td colspan="6">
    ${c.mode_emploi ? `<p><strong>Mettre à jour :</strong> ${echapper(c.mode_emploi)}</p>` : ""}${journal}</td></tr>`;
}

export async function afficherSynoptique() {
  const reponse = await fetch("/api/synoptique");
  const s = await reponse.json();
  if (!reponse.ok) throw new Error(s.erreur || `erreur ${reponse.status}`);
  const lignes = s.comptes.map((c) => {
    const [texte, classe] = FRAICHEUR[c.fraicheur];
    const acces = `${echapper(c.principal || "aucun")}${c.secours ? ` → ${echapper(c.secours)}` : ""}`;
    return `<tr class="cliquable" data-compte="${echapper(c.cle)}"><td>${echapper(c.nom)}</td><td>${acces}</td><td>${echapper(c.reseau)}</td>
      <td><span class="pastille ${classe}" title="${texte}"></span> ${dateFr(c.derniere_donnee)} <span class="discret">${age(c.derniere_donnee, s.aujourd_hui)} · ${texte}</span></td>
      <td>${echapper(c.alimente)}</td><td class="nombre">${c.reussis_30_jours} ✓ ${c.echecs_30_jours ? `<span class="ko">${c.echecs_30_jours} ✗</span>` : ""}</td></tr>${detail(c)}`;
  });
  $("synoptique-comptes").innerHTML = s.comptes.length
    ? `<thead><tr><th>Compte</th><th>Accès principal → secours</th><th>Réseau</th><th>Dernière donnée</th><th>Alimente</th><th>30 jours</th></tr></thead>
       <tbody>${lignes.join("")}</tbody>`
    : `<tbody><tr><td class="discret">Aucun compte : déposez un relevé ou un export dans l'onglet Relevés.</td></tr></tbody>`;
  $("synoptique-comptes").querySelectorAll("[data-compte]").forEach((ligne) => ligne.addEventListener("click", () =>
    $("synoptique-comptes").querySelector(`[data-detail="${CSS.escape(ligne.dataset.compte)}"]`).classList.toggle("cache")));
  $("synoptique-sorties").innerHTML = `<thead><tr><th>Sortie</th><th>Réseau</th><th>Vers</th><th>Ce qui part</th><th>État</th></tr></thead><tbody>${s.sorties
    .map((o) => `<tr><td>${echapper(o.nom)}</td><td>${echapper(o.reseau)}</td><td>${echapper(o.destinataire)}</td><td>${echapper(o.contenu)}</td><td>${echapper(o.etat)}</td></tr>`)
    .join("")}</tbody>`;
}

export function preparerSynoptique(recharger) {
  $("synoptique-synchroniser").addEventListener("click", async () => {
    $("synoptique-attente").textContent = "Mise à jour…";
    $("synoptique-messages").innerHTML = "";
    const reponse = await fetch("/api/synchroniser", {
      method: "POST", headers: { "Content-Type": "application/json", "X-Metabank": "1" }, body: JSON.stringify({ forcer: true }),
    });
    const r = await reponse.json();
    $("synoptique-attente").textContent = reponse.ok ? (r.messages.length ? "" : "Aucun accord enregistré.") : r.erreur;
    if (!reponse.ok) return;
    const classes = { ok: "ok", erreur: "ko", info: "discret" };
    $("synoptique-messages").innerHTML = r.messages.map((m) => `<li class="${classes[m.ton] ?? ""}">${echapper(m.texte)}</li>`).join("");
    await recharger();
    await afficherSynoptique();
  });
}
