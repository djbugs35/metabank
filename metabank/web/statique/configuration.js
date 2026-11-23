// Onglet « Configuration » : registre des comptes, connecteurs, paramètres. Validation côté Python (configuration.py).
import { echapper } from "./graphiques.js";

const $ = (id) => document.getElementById(id);
const FAMILLES = { fichier: "fichier déposé", direct: "connexion directe", calcul: "calcul", reference: "données publiques" };
let configuration = null;

async function appeler(chemin, options = {}) {
  const reponse = await fetch(chemin, options);
  const donnees = await reponse.json();
  if (!reponse.ok) throw new Error(donnees.erreur || `erreur ${reponse.status}`);
  return donnees;
}

export async function afficherConfiguration() {
  configuration = await appeler("/api/configuration");
  afficherComptes();
  afficherConnecteurs();
  $("config-assistant").checked = configuration.parametres.assistant_actif;
  $("config-depot").value = configuration.dossiers.depot;
  $("config-dossier").textContent = `Données : ${configuration.dossier_donnees} ; dépôt surveillé : ${configuration.dossier_depot}`;
}

function choix(nom, valeur, possibles, vide) {
  const libelles = Object.fromEntries(configuration.connecteurs.map((c) => [c.nom, c.libelle]));
  const options = [["", vide], ...possibles.map((p) => [p, libelles[p] ?? p])];
  return `<select data-champ="${nom}">${options
    .map(([v, t]) => `<option value="${echapper(v)}" ${v === valeur ? "selected" : ""}>${echapper(t)}</option>`).join("")}</select>`;
}

function afficherComptes() {
  const lignes = configuration.comptes.map((c) => `<tr data-compte="${echapper(c.cle)}">
    <td>${echapper(c.libelle_type)}<br><span class="discret">${echapper(c.etablissement)} ${echapper(c.numero_masque)}</span></td>
    <td><input data-champ="titulaire" maxlength="40" placeholder="${echapper(c.titulaire)}" value="${echapper(c.titulaire_saisi)}"></td>
    <td>${choix("principal", c.principal, c.connecteurs_possibles, "aucun")}</td>
    <td>${choix("secours", c.secours, c.connecteurs_possibles, "aucun")}</td>
    <td><input type="number" data-champ="frequence_jours" min="1" max="400" step="1" value="${c.frequence_jours ?? ""}"></td>
    <td class="discret">${c.derniere_donnee ? echapper(c.derniere_donnee.slice(0, 10)) : "jamais"}</td></tr>`);
  $("config-comptes").innerHTML = configuration.comptes.length
    ? `<thead><tr><th>Compte</th><th>Titulaire</th><th>Accès principal</th><th>Secours</th><th>Fréquence (jours)</th>
        <th>Dernière donnée</th></tr></thead><tbody>${lignes.join("")}</tbody>`
    : `<tbody><tr><td class="discret">Aucun compte : déposez un relevé ou un export dans l'onglet Relevés.</td></tr></tbody>`;
}

function afficherConnecteurs() {
  $("config-connecteurs").innerHTML = configuration.connecteurs.map((c) => {
    const reglages = c.reglages.map((r) => r.secret
      ? `<label class="champ">${echapper(r.libelle)} <span class="discret">(secret : ${r.renseigne ? "renseigné" : "à ranger dans le coffre de la machine"})</span></label>`
      : `<label class="champ">${echapper(r.libelle)} <input data-reglage="${echapper(r.nom)}" maxlength="200" value="${echapper(r.valeur)}"></label>`).join("");
    return `<div class="carte"><strong>${echapper(c.libelle)}</strong>
      <span class="${c.actif ? "ok" : "ko"}">${c.actif ? "actif" : "inactif : réglages à renseigner"}</span>
      <p class="discret">${echapper(FAMILLES[c.famille] ?? c.famille)} · réseau ${echapper(c.reseau)} ·
        ${echapper(c.etablissements.join(", "))} · comptes : ${echapper(c.types_comptes.join(", "))}</p>
      ${reglages ? `<div class="champs">${reglages}</div>` : `<p class="note">Aucun réglage.</p>`}</div>`;
  }).join("");
}

function saisie() {
  const comptes = {};
  document.querySelectorAll("[data-compte]").forEach((ligne) => {
    const champ = (nom) => ligne.querySelector(`[data-champ="${nom}"]`).value.trim();
    const frequence = champ("frequence_jours");
    comptes[ligne.dataset.compte] = {
      titulaire: champ("titulaire"), principal: champ("principal"), secours: champ("secours"),
      frequence_jours: frequence === "" ? null : Number(frequence),
    };
  });
  const reglages = Object.fromEntries([...document.querySelectorAll("[data-reglage]")].map((i) => [i.dataset.reglage, i.value]));
  return { comptes, reglages, parametres: { assistant_actif: $("config-assistant").checked }, dossiers: { depot: $("config-depot").value.trim() } };
}

export function preparerConfiguration(apresEnregistrement) {
  $("enregistrer-configuration").addEventListener("click", async () => {
    const message = $("etat-configuration");
    try {
      configuration = await appeler("/api/configuration", {
        method: "POST", headers: { "Content-Type": "application/json", "X-Metabank": "1" }, body: JSON.stringify(saisie()),
      });
      afficherComptes();
      afficherConnecteurs();
      message.className = "ok";
      message.textContent = "Enregistré ; chiffres recalculés.";
      await apresEnregistrement();
    } catch (erreur) {
      message.className = "ko";
      message.textContent = `Non enregistré : ${erreur.message}`;
    }
  });
}
