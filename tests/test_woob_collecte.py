import pytest
from woob.exceptions import AppValidation, NeedInteractiveFor2FA

from metabank.connecteurs.woob_collecte import ErreurCollecte, _executer


class _Reglage:
    def __init__(self):
        self.valeur = None

    def set(self, valeur):
        self.valeur = valeur


class _BackendFactice:
    name = "bnp"

    def __init__(self):
        self.config = {"resume": _Reglage(), "request_information": _Reglage()}


def _action_qui_echoue_puis_reussit(exception):
    appels = []

    def action():
        appels.append(1)
        if len(appels) == 1:
            raise exception
        return ["compte"]

    return action


def test_validation_sur_telephone_relancee_en_interactif():
    backend = _BackendFactice()
    action = _action_qui_echoue_puis_reussit(AppValidation("Validez sur votre application"))
    assert _executer(backend, action, interactif=True) == ["compte"]
    assert backend.config["resume"].valeur is True


def test_validation_sur_telephone_refusee_hors_interactif():
    action = _action_qui_echoue_puis_reussit(AppValidation("Validez sur votre application"))
    with pytest.raises(ErreurCollecte, match="--interactif"):
        _executer(_BackendFactice(), action, interactif=False)


def test_double_authentification_demandee_signale_l_option():
    action = _action_qui_echoue_puis_reussit(NeedInteractiveFor2FA())
    with pytest.raises(ErreurCollecte, match="--interactif"):
        _executer(_BackendFactice(), action, interactif=False)


def test_relances_bornees():
    def action():
        raise AppValidation("encore")

    with pytest.raises(ErreurCollecte, match="relances"):
        _executer(_BackendFactice(), action, interactif=True)
