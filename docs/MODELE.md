# Modèle de calcul

Toutes les grandeurs sont en euros. Les formules ci-dessous sont celles du code (`metabank/bilan.py`),
qui cite le paragraphe concerné.

## 0. Fiche CSV d'un contrat : ce que metabank lit

Chaque PDF de contrat (relevé annuel Suravenir, situation Suravenir, situation Cardif) est lu par son lecteur, et ce
qu'il dit est écrit dans une fiche « metabank-<année>.csv », à côté des PDF, une par compte et par année (année de la
date du document). L'application ne lit que ces fiches ; un PDF ne donne plus que l'identité du contrat.
- Format Excel français : séparateur « ; », virgule décimale, dates JJ/MM/AAAA, UTF-8 avec BOM. Colonnes : type, date,
  rubrique, libelle, isin, quantite, prix, prix_de_revient, montant, source (nom du PDF).
- Lignes : contrat (assureur, produit, numero, type_contrat), synthese (valeur, valeur_au_1er_janvier,
  versements_annee, cumul_versements, cumul_rachats, performance_annoncee, primes_non_remboursees,
  taux_frais_fonds_euros, mouvements.*, frais.*), support (fonds détenu), frais_support (taux du tableau des frais
  d'un fonds), operation (historique : jour, nature imprimée, fonds nommé, montant), anomalie (remarque du lecteur).
- Une fiche existante n'est jamais réécrite : une correction faite à la main y reste. Un PDF que la fiche ne cite pas
  encore y est ajouté à la fin. « Relire les PDF » (onglet Relevés) réécrit toutes les fiches depuis les PDF.
- La synthèse fait foi (document légal) ; versé de l'année en cours (§ 2.4) et coupons (§ 13.1) sont refaits depuis
  les lignes operation de la fiche, corrections comprises.

## 1. Année d'un contrat, à partir d'un relevé annuel

Notations pour l'année *n* :
- V₀ : valeur au 31/12/n-1 (« Pour rappel, la valeur … était de »), ou valeur de fin du relevé précédent,
  ou 0 pour l'année d'ouverture ;
- V₁ : valeur au 31/12/n ;
- A : apports = versements nets crédités + frais sur versements (ce qui est sorti de la poche de l'épargnant) ;
- R : rachats ;
- F : total des frais de l'année annoncé par l'assureur (frais sur opérations + frais de gestion des unités de
  compte + frais de gestion du fonds en euros).

### 1.1 Gain
G = V₁ − V₀ − A + R

Le gain est **net de tous les frais** : ils ont déjà été prélevés sur la valeur ou sur les versements.
Les arbitrages, distributions réinvesties et la revalorisation du fonds en euros sont internes au contrat :
ils sont déjà dans V₁ et ne s'ajoutent pas.

### 1.2 Rendement de l'année (Dietz modifié, flux supposés en milieu d'année)
r = G / (V₀ + (A − R) / 2)

Les relevés annuels ne datent pas les versements : on les suppose en moyenne au milieu de l'année. L'erreur est
faible quand les versements sont petits devant V₀, plus forte l'année d'un gros versement.
L'année d'ouverture (V₀ = 0), le rendement est le **rendement réel sur la durée de placement** :
r = G / (A − R), affiché avec cette durée en mois si la date d'ouverture est saisie (`data/corrections.json`).
Il n'est pas ramené à une année entière : 98 € gagnés sur 2 994 € en 5 mois font 3,3 %, pas 7,8 %.

### 1.3 Rendement avant frais
r_avant = (G + F) / (V₀ + (A − R) / 2)

L'écart r_avant − r est ce que les frais ont coûté en rendement.

### 1.4 Frais rapportés à l'encours
f = F / ((V₀ + V₁) / 2)

Comparable aux « frais annuels » annoncés par les assureurs et aux frais d'un ETF.

## 2. Depuis l'origine

### 2.1 Avec des relevés annuels contigus depuis l'ouverture
- Apports cumulés = Σ A ; frais cumulés = Σ F ;
- Gain cumulé = V_dernier − Σ A + Σ R.

Si le premier relevé n'est pas celui de l'ouverture (V₀ > 0), le cumul commence à ce relevé :
gain = V_dernier − V₀(premier) − Σ A + Σ R, et une anomalie le signale.

### 2.2 Avec un relevé de situation seul (Cardif)
Gain = valeur de rachat − total brut versé depuis l'origine + total racheté, tel que donné par l'assureur.
Ni frais ni rendement annuel : il faut les relevés annuels.

### 2.3 Relevés annuels suivis d'une situation plus récente (Suravenir, « Situation de votre contrat au … »)
La situation est un document légal : ses chiffres de synthèse font foi. Valeur, versé et rachats : ceux lus sur la
situation (valeur, cumul des versements bruts, cumul des rachats bruts) ; gagné = « Performance (+/- value fiscale)
en € » imprimée, ou valeur − versé + rachats si elle ne l'est pas (comme 2.2) ; les années restent celles des relevés
annuels plus l'année en cours (§ 2.4) ; frais = Σ F des mêmes années.
Contrôle du gagné : gagné refait = Σ gains des années (mêmes conditions que le contrôle du versé ci-dessous) ;
écart = gagné du document − gagné refait.
Contrôle du versé : quand les relevés annuels partent de l'ouverture (V₀ = 0) et que la situation donne l'année en
cours, versé refait = Σ A des relevés annuels + versé de l'année en cours. Écart = versé lu − versé refait ; plus de
1 € : affiché sous le versé et signalé. Cas connu : un transfert entrant d'un autre PER compte dans le cumul de
l'assureur pour les versements faits sur le contrat d'origine, et dans les mouvements pour la somme reçue ; la
somme des gains annuels diffère alors du gain cumulé de l'écart. Autres contrôles : gain calculé face à la
« Performance (+/- value fiscale) en € » de l'assureur, et somme des fonds face au total ; écart de plus de 1 €
signalé. Les frais des fonds (§ 4) restent ceux du dernier relevé annuel qui les donne.

### 2.4 Année en cours, d'après la situation (« 2026 au 23/11 »)
La situation Suravenir imprime l'historique des opérations depuis l'ouverture (date, nature, montant). Pour l'année de
la situation :
- versé = somme des opérations « VERSEMENT… », « SOUSCRIPTION », « ADHESION » datées de l'année ; rachats = somme des
  « RACHAT… » ; frais = « FRAIS ANNEE n » (frais annoncés par l'assureur pour l'année) ; les arbitrages et les
  distributions restent dans le contrat et ne sont pas des flux ;
- gain = valeur de la situation − valeur au 31/12 précédent − versé + rachats ;
- rendement de la période (non annualisé) = gain / (valeur au 31/12 + (versé − rachats) / 2).
Corrigé le 2026-11-23 : la première version prenait « cumul des versements − primes non remboursées au 31/12 » pour
l'assurance vie ; ce montant fiscal n'est pas le cumul des versements (un versement de l'année précédente y comptait à tort).
Pour la rentabilité annualisée (§ 6.2), les versements de la période sont placés à son milieu et la valeur finale à
la date de la situation.

## 3. Contrôles (anomalies signalées, jamais corrigées en silence)
- Somme des supports = valeur du contrat, à un centime par ligne près.
- Composantes des frais = total annoncé ; frais sur opérations = frais de la synthèse des mouvements.
- PER : versements de l'année au tableau « évolution du plan » = versements bruts de la synthèse des mouvements.
- Valeur de début d'un relevé = valeur de fin du relevé précédent ; pas d'année manquante.
- Toute ligne de support ou de mouvement non reconnue.

## 4. Frais support par support (dernier relevé annuel, `metabank frais`)

Le tableau Suravenir « Frais sur les supports d'investissement » donne, pour l'année écoulée et par support,
en points de pourcentage :
- A : performance brute du support ;
- B : frais de gestion du support, prélevés par la société de gestion dans la valeur de part
  (**absents du total des frais du relevé**), dont une part rétrocédée à l'assureur et au distributeur ;
- C : frais de gestion du contrat, prélevés par l'assureur (ceux du relevé) ;
- A − B − C : performance finale pour l'épargnant.

Une ligne n'est retenue que si A − B = nette, nette − C = finale et B + C = total, à 0,02 point près.
Le fonds en euros a B = 0 et C = taux de frais annuels de gestion du fonds.

### 4.1 Coût annuel au rythme actuel
Pour chaque support de valeur V au 31/12 : coût = V × (B + C) / 100. B = frais de gestion du fonds,
C = frais du contrat, lus au tableau « frais sur les supports » du relevé ; les rétrocessions y sont imprimées « dont »
sous B : elles font partie de B (part reversée à l'assureur et au distributeur) et ne s'y ajoutent pas. Somme sur le contrat ;
taux moyen = coût total / encours × 100. C'est une estimation : l'encours bouge pendant l'année.
Elle diffère du total du relevé, qui ne contient pas B mais contient les frais sur versements et arbitrages.

### 4.2 Simulation de supports moins chers
Frais de support cible b (0,20 point par défaut, ordre de grandeur d'un ETF) :
économie annuelle = Σ V × max(B − b, 0) / 100. Les frais du contrat C ne changent pas.

### 4.3 Projection
Sans nouveau versement, sur H années, à rendement brut r (avant tous frais) et taux de frais moyen t :
V_H = V × (1 + (r − t) / 100)^H. L'écart affiché compare t actuel et t après simulation.
r = 5 % et H = 15 ans par défaut : hypothèses, pas des prévisions.

### 4.4 Simulation de l'application web (onglet « Simulation des frais »)
Deux projections de 4.3 côte à côte, avec le taux de frais actuel t₁ et un taux visé t₂ choisis à la main, année
par année de 0 à H. Écart = V_H(t₂) − V_H(t₁), en euros et en % de V_H(t₁).
Frais payés sur la durée = Σ (k = 0 … H − 1) V_k(t) × t / 100 : le taux appliqué à la valeur en début d'année.
Par défaut, t₁ = taux moyen du contrat (4.1) et t₂ = taux après simulation des supports à 0,20 point (4.2).

## 5. Frais depuis l'ouverture (`metabank tableau`, section « Frais payés depuis l'ouverture »)

### 5.1 Taux des fonds
Frais de gestion B de chaque fonds (en points) pris dans le tableau « frais sur les supports » le plus récent qui le
cite. Un fonds vendu avant ce tableau reçoit le taux moyen, pondéré par la valeur, des fonds au taux connu de l'année ;
le nombre de fonds ainsi estimés est affiché. Une année sans aucun fonds au taux connu prend le taux moyen pondéré du
dernier relevé.

### 5.2 Frais d'une année
Frais du relevé (exacts) + Σ sur les fonds de ((V au 31/12 précédent + V au 31/12 de l'année) / 2) × B / 100.
L'année d'ouverture, V au 31/12 précédent vaut 0 (versements supposés en milieu d'année).
Un fonds acheté et revendu dans la même année n'apparaît à aucun 31/12 : ses frais ne sont pas comptés (sous-estimation).

## 6. Synthèse par foyer, personne et contrat (`metabank tableau`)

### 6.1 Année d'un ensemble de contrats
Sommes, sur les contrats à relevés annuels, de V₀, versements, gain et frais. Rendement réel de l'année :
r = G / (V₀ + F_ouverture + F_courant / 2), où F_ouverture sont les versements des contrats ouverts dans l'année
(comptés en entier, § 1.2) et F_courant ceux des autres, supposés en milieu d'année.
Si |F_courant| > 25 % de V₀, la date inconnue des versements pèse : l'année est marquée « ≈ » et la fourchette est
donnée, de G / (V₀ + F_ouverture + F_courant) (tout versé en janvier) à G / (V₀ + F_ouverture) (tout en décembre).
Le gain G, lui, est exact. Les relevés de situation n'entrent que dans la valeur, le versé et le gain.

### 6.5 Fiche de chaque contrat (onglet Placements)
Pour chaque contrat : les chiffres de synthèse de son document le plus récent, tels que la fiche CSV les donne
(§ 0) — valeur, cumul des versements, cumul des rachats, performance annoncée ; un chiffre que le document n'imprime
pas est calculé et dit comme tel (gagné = valeur − versé + rachats, versé = somme des relevés annuels). Contrôle,
quand les relevés annuels partent de l'ouverture : versé et gagné refaits année par année (§ 2.3) ; seul un écart de
plus de 1 € est affiché. Puis les années : valeur au 31/12 (ou à la date de la situation), versé, frais, gagné (§ 1).

### 6.2 Rentabilité annualisée depuis l'ouverture
Taux de rendement interne r tel que Σ flux / (1 + r)^t = 0, t en années depuis le premier flux :
versements nets de rachats au 1er juillet de chaque année, ou à la date d'ouverture l'année d'ouverture (négatifs), valeur au premier 31/12 connu si le contrat
est antérieur aux relevés (négative), valeur au dernier 31/12 (positive). Résolu par dichotomie entre −99 % et
+1 000 %. Elle est nette de tous les frais.
Elle porte sur le même versé que le gain affiché : quand le versé lu sur le document diffère du versé refait par les
mouvements (§ 2.3), l'écart est un flux négatif de plus, placé à l'ouverture du contrat (1er janvier de la première
année si la date d'ouverture n'est pas saisie) ; le taux est alors un minimum (comme § 6.3).

### 6.4 Progression des placements, fin d'année par fin d'année
Sur les contrats à relevés annuels de l'ensemble (les contrats à situation seule n'ont pas d'historique et n'y
sont pas), pour chaque année n : valeur V_n = Σ valeurs au 31/12 (ou à la date de la situation pour l'année en
cours), un contrat sans chiffres l'année n gardant sa dernière valeur connue ; variation de l'année = V_n − V_(n−1)
(Σ valeurs de début de la première année pour la première) ; versé net cumulé = Σ valeurs de début de la première
année de chaque contrat (0 à l'ouverture) + Σ (versé − rachats) jusqu'à n ; gagné cumulé = V_n − versé net
cumulé. Une dernière colonne « aujourd'hui, tous contrats » reprend les tuiles (valeur, versé lu, gagné), contrats à
situation seule compris : leur valeur y est indiquée à part. La variation se décompose en versé net de l'année + gagné de l'année. Ce sont les mouvements des années :
si le versé lu sur le document en diffère (§ 2.3), l'écart reste affiché sous le versé.

### 6.3 Contrats à relevé de situation seul (PERP Cardif)
Avec une date d'ouverture saisie, ils entrent dans la rentabilité annualisée : tout le versé depuis l'origine est
supposé placé à l'ouverture (seule date connue), valeur de rachat à la date du relevé. Si des versements ont eu lieu
plus tard, la rentabilité réelle est plus élevée : c'est un minimum.

## 7. Comptes bancaires (onglet « Comptes »)

Source : export des opérations BNP (CSV). La première ligne donne le solde S à la date D ; chaque ligne suivante,
une opération (jour, libellé, montant m, positif pour une entrée).

### 7.1 Fusion de plusieurs exports
Une opération est identifiée par (jour, libellé, montant). Présente n fois dans un export, elle compte n fois ;
présente dans deux exports, elle n'est pas doublée (on garde le plus grand n). S et D viennent de l'export le plus
récent. Contrôle : pour chaque autre export (S', D'), S − Σ m (D' < jour ≤ D) doit valoir S'.

### 7.1 bis Même opération reçue par deux sources (export CSV et connexion directe)
Mesuré le 2026-11-23 sur 90 jours et quatre comptes : mêmes nombres d'opérations des deux côtés ; 85 % à date
comptable égale, toutes les autres au même montant à 1 à 5 jours près, aucune sans jumelle.
Règle : une opération d'une source n'est pas ajoutée quand le compte a déjà, venue d'une autre source, une opération
de même montant dont la date est à 5 jours au plus, et pas encore appariée ; la plus proche en date est retenue (puis
la plus ancienne en base). L'appariement est gardé en base (table jumelles) : chaque opération ne sert qu'une fois, et
une nouvelle synchronisation qui rend la même opération la reconnaît à son identifiant. Entre deux exports de la même
source, seule compte l'identifiant (7.1). Les opérations « en attente » de la banque ne sont pas importées.

### 7.2 Classement
Chaque opération reçoit une catégorie par règles sur « type sous-type libellé » (règles personnelles de
data/categories.json d'abord, puis celles du code), et une nature :
- revenu : salaires (émetteur d'au moins 4 virements reçus ≥ 1 000 € sur 4 mois différents), remboursements
  santé, autres entrées ;
- interne : virements entre ses propres comptes ;
- épargne : versements vers des placements (assurance vie, PER, livrets, PEA) ;
- dépense : tout le reste. Un montant positif dans une catégorie de dépense (achat remboursé) diminue la dépense.

### 7.3 Soldes
Solde en fin de journée j : S − Σ m (jour > j). Solde moyen : moyenne de ces soldes sur chaque jour de la période,
du premier jour de l'export à D.

### 7.4 Budget
Sur la période (N mois = jours / 30,44) : R = Σ revenus, Dp = Σ dépenses (en positif), E = Σ épargne placée.
Par mois : montant / N. Parts : Dp / R, E / R. Taux d'épargne : (R − Dp) / R. Frais bancaires par an :
Σ frais / N × 12.

### 7.5 Argent qui dort
Coussin = 2 mois de dépenses moyennes (Dp / N × 2). Argent qui dort = max(solde moyen − coussin, 0), sur un
compte courant seulement. Manque à gagner par an = argent qui dort × taux du Livret A (1,7 % depuis le
1er août 2026). Repère, pas une prévision : le taux change le 1er février et le 1er août.

### 7.6 Livrets
Intérêts de l'année Y = Σ des entrées dont le libellé contient « INTERET » ou « REMUNERATION », datées de Y ou
du 1er au 15 janvier de Y + 1 (la banque les crédite début janvier : BNP, « REMUNERATION NETTE » au 01/01).
Taux obtenu = intérêts / solde moyen de Y (7.3), sur les jours de Y couverts par l'export ; si aucun ne l'est,
solde supposé constant, égal à celui de la veille du versement (exact sans mouvement dans l'année).
Taux réglementé moyen de Y = moyenne des taux du Livret A (identique pour le LDDS) en vigueur le 1er de chaque
mois. Intérêts attendus de l'année en cours ≈ solde actuel × taux réglementé moyen de l'année.
Plafond des versements : 22 950 € (Livret A), 12 000 € (LDDS) ; les intérêts peuvent le dépasser.

### 7.7 Budget du foyer
Avec plusieurs comptes courants (personnels, commun, locatif), un compte fictif les additionne : opérations mises
bout à bout, solde = Σ soldes. Les virements entre ces comptes sont « interne » (7.2) et s'annulent : seuls
restent les revenus et dépenses du foyer avec l'extérieur.

### 7.8 Synthèse de l'épargne disponible (tableau de bord)
Pour le foyer et chaque personne : solde = Σ soldes des livrets, part du patrimoine (§ 8). Intérêts de la dernière
année versée = Σ intérêts de cette année ; taux obtenu = intérêts / Σ soldes moyens de l'année (7.6), comparé au
taux réglementé moyen. Intérêts attendus de l'année en cours = Σ estimations (7.6). Plafonds : rempli =
Σ min(solde, plafond) / Σ plafonds ; versements encore possibles = Σ plafonds − Σ min(solde, plafond).

### 7.9 Crédits immobiliers
Source : export BNP du prêt. Solde négatif = capital restant dû C ; une ligne « AMORTISSEMENT PRET » par mois =
part de capital remboursée A. À mensualité constante, A croît chaque mois du taux mensuel i :
i = médiane des A(k+1) / A(k) − 1 ; taux annuel ≈ 12 × i. Prochaine mensualité P = A(dernier) × (1 + i) + C × i,
dont intérêts C × i. Mois restants n = ln(P / (P − C × i)) / ln(1 + i), arrondi au-dessus ; fin estimée = date de
l'export + n mois ; intérêts restant à payer ≈ n × P − C. Hors assurance et sans remboursement anticipé.
Contrôle : P est comparée à la dernière « ECHEANCE PRET » portant le numéro du prêt sur les comptes courants.
Les crédits rangés dans un dossier « credits » (hors personne) sont rattachés au compte joint.

### 7.10 Capital restant dû projeté au mois en cours
Entre deux exports, le capital suit le tableau d'amortissement. Jour d'échéance = jour du mois de la dernière ligne
« AMORTISSEMENT PRET ». k = nombre d'échéances passées entre la date de l'export (exclue) et aujourd'hui (inclus).
Capital projeté C(k) = C × (1 + i)^k − P × ((1 + i)^k − 1) / i, avec C, i et P de 7.9 (P hors assurance), et
jamais sous zéro. Mois restants = n − k ; intérêts restant à payer ≈ (n − k) × P − C(k). Sans taux ni mensualité
estimés, ou sans échéance passée, le capital reste celui de l'export. La date de projection est affichée ; un nouvel
export remplace la projection par le chiffre de la banque.

### 7.11 Tableau d'amortissement, remboursement anticipé ou placement, assurance emprunteur
Point de départ : le crédit au mois en cours (7.10), capital C, taux mensuel i, mensualité P hors assurance (7.9).
- **Tableau d'amortissement** : chaque mois k, intérêts = C(k−1) × i, capital remboursé = P − intérêts (le dernier mois,
  le capital restant), C(k) = C(k−1) − capital remboursé. Regroupé par année civile.
- **Remboursement anticipé** d'un montant R aujourd'hui, mensualité gardée : le tableau repart de C − R ; intérêts
  économisés = intérêts restants avant − après ; durée raccourcie de n − n' mois. Indemnités (IRA) : au plus le
  plafond légal, min(6 mois d'intérêts sur R au taux du prêt, 3 % de C avant remboursement) (code de la
  consommation, art. R313-25) ; le contrat peut prévoir moins, ou rien.
- **Rembourser ou placer** : comparaison du patrimoine à la date de fin actuelle du prêt (mois n), avec un rendement
  annuel net r supposé (taux mensuel r_m = (1 + r)^(1/12) − 1) :
  rembourser = Σ des mensualités P libérées des mois n' + 1 à n, chacune placée jusqu'au mois n, moins les IRA placées
  depuis aujourd'hui ; placer = R × (1 + r_m)^n. Écart = rembourser − placer. Hypothèse, pas une prévision ;
  fiscalité du placement non comptée (r est net).
- **Assurance emprunteur** : coût mensuel estimé = mensualité prélevée sur le compte courant − P ; coût restant
  ≈ ce coût × n. Inconnu sans échéance prélevée retrouvée.

### 7.12 Bien locatif : rendement et trésorerie
Le bien locatif est le bien saisi dans Corrections dont le nom contient « locatif » ; son crédit est celui de même
clé ; ses flux sont ceux des comptes de type « locatif ». Sur la période couverte par les exports du compte (m mois,
7.4), ramenée à l'année (× 12 / m) :
- loyers L = entrées de nature « revenu » (les virements depuis ses propres comptes n'en sont pas) ;
- échéances E = sorties de la catégorie « Crédits » (mensualités prélevées, assurance comprise) ;
- charges H = autres sorties de nature « dépense » (taxe foncière, copropriété, travaux, assurance du bien…).
Avec V la valeur du bien saisie et I les intérêts des 12 prochaines échéances du crédit (7.11) :
- rendement brut = L / V ; rendement net de charges = (L − H) / V ; après intérêts d'emprunt = (L − H − I) / V ;
- trésorerie mensuelle = (L − H − E) / 12 : ce que le bien rapporte ou coûte chaque mois, prêt compris.
Avant impôts et prélèvements sociaux ; sans valeur saisie, seuls les montants et la trésorerie sont affichés.

### 7.13 Budget : abonnements, objectifs, d'une année sur l'autre
Sur les dépenses classées (7.2) d'un compte courant, regroupées par marchand (libellé sans date, carte ni chiffres) :
- **abonnement ou prélèvement régulier** : un marchand débité au moins 3 mois distincts sur les 12 derniers mois
  couverts, au plus deux fois par mois en moyenne, montants stables (le plus haut ≤ 1,2 × le plus bas). Montant
  habituel = médiane ; coût sur 12 mois = somme des débits de la fenêtre ;
- **objectif par catégorie** (saisi, en euros par mois) : dépassement si la dépense du dernier mois complet de la
  catégorie dépasse l'objectif ; la moyenne des 3 derniers mois complets est donnée à côté ;
- **d'une année sur l'autre** : par catégorie, dépenses des 12 derniers mois complets face aux 12 mois complets
  précédents, écart en euros ; sans 24 mois complets couverts, la colonne précédente reste vide.

## 8. Patrimoine complet (tableau de bord)

Pour le foyer et pour chaque personne : actifs = Σ valeurs des placements (assurance vie, PER, PERP, au dernier
relevé) + Σ soldes des livrets (épargne disponible) + Σ soldes des comptes courants (au dernier export) + Σ valeurs
estimées des biens immobiliers (saisies dans Corrections). Crédits = Σ capitaux restant dus (7.9).
Patrimoine net = actifs − crédits ; sans valeur de bien saisie, il n'est pas affiché (il serait trompeur).
Part d'une famille, d'un compte ou des crédits = son montant / actifs. Les dates de valeur diffèrent d'un compte à l'autre :
chacune est affichée.

### 8.1 Historique mensuel du patrimoine (13 mois)
Points : la fin de chacun des 12 mois précédents, et aujourd'hui pour le mois en cours. Pour chaque point m, chaque
montant est reconstitué à partir des données déjà en base, sans instantané :
- compte courant, livret ou crédit : solde(m) = S − Σ des opérations datées de ]m, d], S étant le solde du dernier
  export à la date d. Si m ≥ d : S, et pour un crédit le capital projeté au jour m (7.10). Si m précède la veille de la
  première opération connue, le solde est inconnu ;
- assurance vie, PER, PERP : valeur du dernier relevé daté au plus tard de m (les relevés sont annuels : la courbe des
  placements avance par paliers) ; sans relevé à cette date, la valeur est inconnue ;
- bien immobilier : valeur saisie dans Corrections, la même à chaque point (pas d'historique).
Actifs, crédits et net comme au § 8, sur le même ensemble de comptes et contrats à chaque point, pour qu'un compte
qui apparaît ne passe pas pour un gain ni un crédit encore inconnu pour une dette éteinte : avant sa première valeur
connue, un compte ou contrat est compté à cette première valeur (reportée en arrière) et nommé sous le graphique.
Un compte sans aucune valeur connue à la date du dernier point est laissé hors de la courbe.

## 9. Fraîcheur des comptes (onglet « Synoptique »)

Date de la dernière donnée d'un compte = la plus récente des dates portées par ses données : jour d'un solde, jour
d'une opération, date d'arrêté d'un relevé. Ce n'est pas la date d'import : un vieux relevé déposé aujourd'hui reste
vieux.
Âge = aujourd'hui − date de la dernière donnée, en jours. Fréquence attendue f = celle saisie dans Configuration,
sinon celle du type de compte (30 jours pour un compte courant, 90 pour un crédit, 365 pour un livret ou un contrat).
- **à jour** : âge ≤ f ;
- **en retard** : f < âge ≤ 2 f ;
- **très en retard** : âge > 2 f ;
- **jamais** : aucune donnée.
Sans fréquence connue, le compte est « à jour » dès qu'il a une donnée. Le journal compte, sur les 30 derniers jours,
les imports réussis et ceux en erreur ou refusés qui visaient ce compte.

## 10. Performance comparée aux repères publics (première version)

Pour chaque année d'une vue (foyer, personne, contrat), le rendement de l'année (§ 6.1, gagné rapporté aux sommes
placées, frais déduits) est affiché face aux repères publics de la même année, sans autre calcul que l'écart en
points (rendement − repère). Repères, dans metabank/reperes.py avec leur source :
- **fonds en euros** : taux de revalorisation moyen des contrats individuels (ACPR, Analyses et synthèses
  « Revalorisation des contrats d'assurance-vie »), net de frais sur encours, avant prélèvements sociaux ;
- **unités de compte** : performance globale des supports en UC (France Assureurs), brute des frais des contrats et
  nette des frais des fonds : un contrat la bat d'autant moins que ses frais de gestion sont élevés ;
- **Livret A** : moyenne des taux en vigueur le 1er de chaque mois (§ 7.6) ;
- **inflation** : hausse moyenne annuelle de l'indice des prix à la consommation (Insee) ;
- **MSCI World** : rendement annuel en euros, dividendes nets réinvestis (fiche MSCI World Index (EUR)), sans aucun
  frais.
Une année sans repère publié ou vérifié reste vide. Les repères se mettent à jour une fois par an, à la publication.
La comparaison pondérée par la répartition de chaque contrat viendra à l'étape 5.

## 11. Fiscalité et échéances

Faits datés pour chaque contrat ; aucune recommandation. Date d'ouverture : celle saisie dans Corrections (sinon
l'échéance est « à saisir »).
- **Assurance vie, 8 ans** : date d'ouverture + 8 ans. Ensuite, les gains compris dans un rachat bénéficient d'un
  abattement annuel d'impôt sur le revenu de 4 600 € (9 200 € pour un couple soumis à imposition commune, paramètre de
  Configuration), pour l'ensemble des contrats du foyer (CGI, art. 125-0 A). Part de gain d'un rachat = gain / valeur
  du contrat ; rachat couvert par l'abattement ≈ abattement × valeur / gain (si le gain est positif). Les prélèvements
  sociaux restent dus.
- **PER, transfert** : frais de transfert au plus 1 % de l'épargne avant 5 ans, nuls ensuite (loi Pacte) ; date de
  gratuité = ouverture + 5 ans. PERP et autres anciens contrats : règles de transfert propres, non chiffrées ici.
- **PER, versements déductibles** : rappel du 31 décembre de l'année en cours.
Échéances listées par date ; une échéance passée de moins d'un an reste affichée comme « atteinte ».

## 12. Projection retraite (onglet « Simulation »)

Hypothèses saisies, jamais une prévision. Contrats retenus : les PER et PERP du titulaire, et ses assurances vie si
la case est cochée ; K0 = somme de leurs valeurs au dernier relevé. n = mois d'aujourd'hui au 1er janvier de l'année
de départ ; versement mensuel V ; pour chaque rendement annuel net r des trois scénarios, r_m = (1 + r)^(1/12) − 1 :
- capital au départ K = K0 × (1 + r_m)^n + V × ((1 + r_m)^n − 1) / r_m (V × n si r_m = 0) ;
- en euros d'aujourd'hui, avec une inflation annuelle π : K_réel = K / (1 + π)^(n / 12) ;
- retrait mensuel possible pendant D années, le reste du capital continuant de rapporter r (sortie en capital
  fractionnée, pas une rente viagère) : W = K_réel × r_m / (1 − (1 + r_m)^(−12 D)) (K_réel / (12 D) si r_m = 0).
Fiscalité de la sortie non comptée.

## 13. Allocation (onglet « Allocation »)

Valeur d'un support = sa valeur au dernier relevé de son contrat. Classe d'un support : celle choisie par le titulaire
(onglet Allocation), sinon déduite de mots de son libellé (FCPR → capital-investissement, OBLIG, BOND, CREDIT →
obligations, EQUITY, ACTIONS → actions…), sinon « à classer ». Le classement par mots est une aide, pas une analyse
du document d'information du fonds.
- **Répartition** : par classe, part du patrimoine financier = supports des contrats + livrets + comptes courants (hors
  biens immobiliers et crédits).
- **Concentration** : alerte pour tout support qui pèse plus de 20 % du patrimoine financier ; les supports « à
  classer » sont listés.
- **Cible** (parts saisies, somme 100 %) : écart = part actuelle − cible, en points. Rééquilibrage par les seuls
  versements, sans rien vendre : T' = max des V_c / cible_c sur les classes de cible non nulle ; à verser dans la
  classe c = cible_c × T' − V_c (jamais négatif) ; total à verser = T' − T. Alerte de dérive quand une classe
  s'écarte de sa cible de plus de 5 points. Les livrets et comptes courants ne sont pas
  des classes de la cible : la cible porte sur les supports des contrats.

### 13.1 Plus-value face au prix de revient, coupons reçus

La situation Suravenir imprime, pour chaque fonds, le nombre de parts n, la valeur liquidative VL et le prix de
revient P (prix moyen d'achat d'une part détenue, calculé par l'assureur ; un arbitrage entrant le refait, un
arbitrage sortant ne le change pas). Le relevé annuel ne le donne pas : rien n'est alors affiché.
- **Plus-value latente** = (VL − P) × n, en euros ; en part du prix payé : VL / P − 1.
- **Coupons reçus** = somme des lignes « DISTRIBUTION » de l'historique des opérations de la situation qui nomment ce
  fonds, depuis l'origine. Versés sur un autre support du contrat, ils ne sont pas dans la valeur du fonds.
- **Net** = plus-value latente + coupons reçus : ce que le fonds a rapporté ou coûté depuis son achat, à ce jour.
- **Coupon attendu non venu** : pour un fonds qui a versé au moins 3 coupons, rythme habituel R = médiane des jours
  entre deux coupons consécutifs ; alerte quand la date de la situation dépasse le dernier coupon de plus de 1,5 × R.
  C'est un constat : un coupon peut dépendre d'une condition (produit structuré), que seul le document
  d'information du fonds dit.

## 14. Simulateur d'arbitrage (onglet « Allocation »)

Arbitrer un montant V d'un fonds de frais totaux t₁ (frais du fonds et du contrat, en % par an, 4.1) vers un fonds
de frais t₂, avec des frais d'arbitrage a (% du montant, selon le contrat), au même rendement brut supposé r pour
les deux, afin de n'isoler que l'effet des frais (projection de 4.3) :
- garder : V_H = V × (1 + (r − t₁) / 100)^H ;
- arbitrer : V'_H = V × (1 − a / 100) × (1 + (r − t₂) / 100)^H ;
- écart à H ans = V'_H − V_H ; coût immédiat = V × a / 100 ; point mort = première année H où V'_H ≥ V_H (aucun si
  t₂ ≥ t₁ et a > 0).
Coût fiscal : un arbitrage à l'intérieur d'une assurance vie ou d'un PER n'est pas imposable ; rien n'est donc
compté. Les frais d'un fonds viennent de son tableau « frais sur les supports » au dernier relevé ; inconnus (fonds en
euros, relevé sans tableau), ils se saisissent. Le rendement est une hypothèse ; un fonds moins cher n'est pas pour
autant un meilleur fonds.
