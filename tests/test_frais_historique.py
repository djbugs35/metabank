from datetime import date
from decimal import Decimal

from metabank.frais_historique import historiques_frais
from metabank.releves import ReleveRange
from metabank.releves.frais_supports import FraisSupport
from metabank.releves.modele import Frais, Mouvements, Releve, Support


def _frais(isin: str, taux: str) -> FraisSupport:
    d = Decimal(taux)
    return FraisSupport(isin, d, d / 2, Decimal(1), Decimal(0), d + 1, Decimal(5), Decimal(3), Decimal(3))


def _releve(annee: int, supports: dict[str, int], frais_releve: int, taux: dict[str, str]) -> Releve:
    return Releve(
        assureur="Test",
        produit="Contrat",
        numero="1",
        type_contrat="assurance_vie",
        date_arrete=date(annee, 12, 31),
        valeur=Decimal(sum(supports.values())),
        supports=tuple(Support(isin, Decimal(v), isin) for isin, v in supports.items()),
        mouvements=Mouvements(),
        frais=Frais(total=Decimal(frais_releve)),
        frais_supports=tuple(_frais(i, t) for i, t in taux.items()),
    )


def test_frais_des_fonds_sur_l_encours_moyen_de_chaque_annee():
    """2023 : 10 000 € en fin d'année, moyenne 5 000 € à 2 % = 100 €. 2024 : moyenne 12 000 € à 2 % = 240 €."""
    releves = [
        ReleveRange("A", _releve(2023, {"FR0000000001": 10000}, 50, {})),
        ReleveRange("A", _releve(2024, {"FR0000000001": 14000}, 120, {"FR0000000001": "2.00"})),
    ]
    historique = historiques_frais(releves)[0]
    assert [a.frais_fonds for a in historique.annees] == [Decimal(100), Decimal(240)]
    assert historique.cumul_releve == Decimal(170)
    assert historique.cumul == Decimal(510)


def test_fonds_vendu_avant_le_dernier_tableau_au_taux_moyen_du_contrat():
    """FR…2 n'est plus détenu en 2024 : son taux est inconnu, on lui applique la moyenne des fonds connus (1 %)."""
    releves = [
        ReleveRange("A", _releve(2023, {"FR0000000002": 4000}, 0, {})),
        ReleveRange("A", _releve(2024, {"FR0000000001": 4000}, 0, {"FR0000000001": "1.00"})),
    ]
    annee_2024 = historiques_frais(releves)[0].annees[1]
    assert annee_2024.supports_taux_estime == 1
    assert annee_2024.frais_fonds == Decimal(40)


def test_annee_sans_aucun_fonds_connu_au_taux_moyen_du_dernier_releve():
    """Cas réel (2023) : tous les fonds de l'ouverture ont été vendus depuis ; avant, leurs frais valaient zéro."""
    releves = [
        ReleveRange("A", _releve(2023, {"FR0000000002": 4000}, 0, {})),
        ReleveRange("A", _releve(2024, {"FR0000000001": 4000}, 0, {"FR0000000001": "1.50"})),
    ]
    assert historiques_frais(releves)[0].annees[0].frais_fonds == Decimal(30)
