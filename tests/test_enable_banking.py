"""Client Enable Banking : jeton RS256, appels (transport simulé, aucun réseau), liaison, rapprochement avec le CSV."""

import base64
import json
import stat
import subprocess
from datetime import date
from decimal import Decimal
from urllib.parse import urlsplit

import pytest

from metabank.connecteurs._enable_banking import (
    Client,
    EnableBankingIndisponible,
    code_de_retour,
    jeton,
    lire_accord,
    masquer_iban,
)
from metabank.liaison_enable_banking import comparer, comparer_sources, montant_signe, relier

APPLICATION = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


@pytest.fixture
def cle(tmp_path):
    chemin = tmp_path / "cle.pem"
    subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(chemin)],
                   check=True, capture_output=True)  # fmt: skip
    return chemin


def _decoder(partie: str) -> bytes:
    return base64.urlsafe_b64decode(partie + "=" * (-len(partie) % 4))


def test_le_jeton_est_un_jwt_rs256_d_une_heure_signe_par_la_cle(cle, tmp_path):
    entete, charge, signature = jeton(APPLICATION, cle, maintenant=1_800_000_000).split(".")
    assert json.loads(_decoder(entete)) == {"typ": "JWT", "alg": "RS256", "kid": APPLICATION}
    assert json.loads(_decoder(charge)) == {"iss": "enablebanking.com", "aud": "api.enablebanking.com",
                                            "iat": 1_800_000_000, "exp": 1_800_003_600}  # fmt: skip
    publique, sig = tmp_path / "pub.pem", tmp_path / "sig"
    subprocess.run(["openssl", "pkey", "-in", str(cle), "-pubout", "-out", str(publique)], check=True)
    sig.write_bytes(_decoder(signature))
    verification = subprocess.run(["openssl", "dgst", "-sha256", "-verify", str(publique), "-signature", str(sig)],
                                  input=f"{entete}.{charge}".encode(), capture_output=True, check=False)  # fmt: skip
    assert verification.returncode == 0


def test_sans_cle_privee_le_jeton_dit_ou_la_ranger(tmp_path):
    with pytest.raises(EnableBankingIndisponible, match=r"rangez le \.pem"):
        jeton(APPLICATION, tmp_path / "absente.pem")


class Banque:
    """Faux serveur Enable Banking : rend des réponses écrites d'avance et garde la trace des appels."""

    def __init__(self, reponses: dict) -> None:
        self.reponses, self.appels = reponses, []

    def __call__(self, methode: str, adresse: str, entetes: dict, corps: bytes | None) -> dict:
        self.appels.append((methode, adresse, entetes, json.loads(corps) if corps else None))
        cle = f"{methode} {urlsplit(adresse).path}"
        reponse = self.reponses[cle]
        return reponse.pop(0) if isinstance(reponse, list) else reponse


def test_chaque_appel_porte_le_jeton_et_les_operations_suivent_les_pages(cle):
    banque = Banque({"GET /accounts/u1/transactions": [
        {"transactions": [{"id": 1}], "continuation_key": "k2"}, {"transactions": [{"id": 2}]}]})  # fmt: skip
    operations = Client(APPLICATION, cle, banque).operations("u1", date(2026, 1, 1))
    assert operations == [{"id": 1}, {"id": 2}]
    assert all(e["Authorization"].startswith("Bearer ") for _, _, e, _ in banque.appels)
    assert "continuation_key=k2" in banque.appels[1][1]


def test_le_code_de_retour_se_lit_dans_l_adresse_d_arrivee():
    assert code_de_retour("https://localhost:8770/enable-banking/retour?state=s&code=abc") == "abc"
    with pytest.raises(ValueError, match="refusé"):
        code_de_retour("https://localhost:8770/enable-banking/retour?error=access_denied")
    with pytest.raises(ValueError, match="sans code"):
        code_de_retour("https://localhost:8770/enable-banking/retour")


def test_le_numero_masque_reprend_les_quatre_derniers_chiffres_du_compte_comme_l_export_bnp():
    assert masquer_iban("FR76 3000 4000 3123 4567 8901 143") == "****9011"


def test_la_liaison_enregistre_session_et_comptes_masques_a_droits_restreints(cle, tmp_path):
    banque = Banque({
        "GET /aspsps": {"aspsps": [{"name": "BNP Paribas"}, {"name": "BNP Paribas Entreprises"}]},
        "POST /auth": {"url": "https://banque.example/accord"},
        "POST /sessions": {"session_id": "s1", "access": {"valid_until": "2027-05-20T00:00:00+00:00"},
                           "accounts": [{"uid": "u1", "account_id": {"iban": "FR7630004000312345678901143"},
                                         "name": "Compte de chèques", "currency": "EUR"}]},
    })  # fmt: skip
    chemin = tmp_path / "accord.json"

    def demander(_question: str) -> str:
        etat = banque.appels[-1][3]["state"]
        return f"https://localhost:8770/enable-banking/retour?state={etat}&code=abc"

    accord = relier(Client(APPLICATION, cle, banque), "BNP Paribas", demander, lambda _adresse: None, chemin=chemin,
                    retour="https://localhost/retour")  # fmt: skip
    assert (
        banque.appels[1][3]["redirect_url"] == "https://localhost/retour"
        and accord["retour"] == "https://localhost/retour"
    )
    assert accord["comptes"] == [{"uid": "u1", "masque": "****9011", "nom": "Compte de chèques", "devise": "EUR"}]
    assert banque.appels[-1][3] == {"code": "abc"} and "FR76" not in chemin.read_text()
    assert stat.S_IMODE(chemin.stat().st_mode) == 0o600 and lire_accord(chemin)["session"] == "s1"


def test_une_adresse_d_un_autre_accord_est_refusee(cle, tmp_path):
    banque = Banque({"GET /aspsps": {"aspsps": [{"name": "BNP Paribas"}]}, "POST /auth": {"url": "https://x"}})
    with pytest.raises(ValueError, match="recommencez"):
        relier(Client(APPLICATION, cle, banque), "BNP Paribas", lambda _q: "https://localhost?state=autre&code=c",
               lambda _a: None, chemin=tmp_path / "a.json")  # fmt: skip


def _dsp2(jour: str, montant: str, sens: str, statut: str = "BOOK") -> dict:
    return {"booking_date": jour, "value_date": jour, "transaction_amount": {"amount": montant, "currency": "EUR"},
            "credit_debit_indicator": sens, "status": statut}  # fmt: skip


def test_un_debit_dsp2_est_un_montant_negatif():
    assert montant_signe(_dsp2("2026-01-05", "200.00", "DBIT")) == Decimal("-200.00")


@pytest.mark.usefixtures("pdf_simules")
def test_le_rapprochement_compte_les_operations_communes_sans_rien_ecrire(donnees, cle):
    operations = [_dsp2("2026-03-05", "200.00", "DBIT"), _dsp2("2026-03-01", "3000.00", "CRDT"),
                  _dsp2("2026-03-30", "9.99", "DBIT", "PDNG")]  # fmt: skip
    banque = Banque({"GET /accounts/u1/transactions": {"transactions": operations}})
    accord = {"comptes": [{"uid": "u1", "masque": "****1234", "nom": "Courant", "devise": "EUR"}]}
    [ligne] = comparer(Client(APPLICATION, cle, banque), donnees, 400, accord)
    assert "apparies_booking_date 2" in ligne and "en_attente 1" in ligne
    assert not list((donnees / "archives").rglob("*.json"))


def test_le_rapprochement_suit_la_date_choisie():
    class Op:
        def __init__(self, jour, montant):
            self.jour, self.montant = jour, Decimal(montant)

    r = comparer_sources([_dsp2("2026-01-06", "10", "DBIT")], [Op(date(2026, 1, 6), "-10")],
                         date(2026, 1, 1), date(2026, 1, 31))  # fmt: skip
    assert (r["csv"], r["dsp2"], r["apparies_booking_date"]) == (1, 1, 1)
