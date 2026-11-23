"""Journal des imports et synchronisations : ce que chaque connecteur a fait, pour quel compte, avec quel résultat.

Les imports de fichiers y sont notés par base/integration.py, à la date de leur archive. Ce module ajoute ce qui
n'a pas d'archive (synchronisation refusée par la banque, service injoignable) et relit le journal.
Ces entrées-là ne se refont pas à la reconstruction : rien ne les garde hors de la base.
"""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

RESULTATS = ("ok", "refus", "erreur")


@dataclass(frozen=True)
class EntreeJournal:
    """Une ligne du journal.

    Attributes:
        le: UTC, ISO 8601.
        compte_cle: clés des comptes visés, séparées par « , » ; vide si inconnu.
        archive: chemin relatif à data/archives/, vide si l'import n'a rien archivé.
        elements: opérations ajoutées et soldes enregistrés.
    """

    le: str
    connecteur: str
    compte_cle: str
    resultat: str
    elements: int
    message: str
    archive: str


def noter_sans_archive(
    connexion: sqlite3.Connection, connecteur: str, compte_cle: str, resultat: str, message: str
) -> None:
    """Noter au journal, à l'heure présente, un import qui n'a rien laissé dans les archives.

    Raises:
        ValueError: résultat hors de RESULTATS.
    """
    if resultat not in RESULTATS:
        raise ValueError(f"résultat inconnu : {resultat}")
    le = datetime.now(tz=UTC).isoformat(timespec="microseconds")
    with connexion:
        connexion.execute(
            "INSERT INTO imports (le, connecteur, compte_cle, resultat, message) VALUES (?, ?, ?, ?, ?)",
            (le, connecteur, compte_cle, resultat, message),
        )


def lire_journal(connexion: sqlite3.Connection, depuis: str = "") -> list[EntreeJournal]:
    """Rendre les entrées du journal datées de depuis (ISO 8601) ou après, de la plus récente à la plus ancienne."""
    lignes = connexion.execute(
        "SELECT i.le, i.connecteur, i.compte_cle, i.resultat, i.elements, i.message, coalesce(a.chemin, '') "
        "FROM imports i LEFT JOIN archives a ON a.id = i.archive_id WHERE i.le >= ? ORDER BY i.le DESC, i.id DESC",
        (depuis,),
    )
    return [EntreeJournal(*ligne) for ligne in lignes]
