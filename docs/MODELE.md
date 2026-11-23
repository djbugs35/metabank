# Modèle de calcul

Toutes les grandeurs sont en euros. Les formules ci-dessous sont celles du code (`metabank/bilan.py`),
qui cite le paragraphe concerné.

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
Pour chaque support de valeur V au 31/12 : coût = V × (B + C) / 100. Somme sur le contrat ;
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

### 6.2 Rentabilité annualisée depuis l'ouverture
Taux de rendement interne r tel que Σ flux / (1 + r)^t = 0, t en années depuis le premier flux :
versements nets de rachats au 1er juillet de chaque année, ou à la date d'ouverture l'année d'ouverture (négatifs), valeur au premier 31/12 connu si le contrat
est antérieur aux relevés (négative), valeur au dernier 31/12 (positive). Résolu par dichotomie entre −99 % et
+1 000 %. Elle est nette de tous les frais.

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

## 8. Patrimoine complet (tableau de bord)

Pour le foyer et pour chaque personne : actifs = Σ valeurs des placements (assurance vie, PER, PERP, au dernier
relevé) + Σ soldes des livrets (épargne disponible) + Σ soldes des comptes courants (au dernier export) + Σ valeurs
estimées des biens immobiliers (saisies dans Corrections). Crédits = Σ capitaux restant dus (7.9).
Patrimoine net = actifs − crédits ; sans valeur de bien saisie, il n'est pas affiché (il serait trompeur).
Part d'une famille, d'un compte ou des crédits = son montant / actifs. Les dates de valeur diffèrent d'un compte à l'autre :
chacune est affichée.

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
