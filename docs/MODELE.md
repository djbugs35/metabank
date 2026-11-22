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
**Non calculé l'année d'ouverture** (V₀ = 0) : la durée de placement est inconnue.

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
