"""Lire la provenance d'une archive : « <titulaire>/<type> - <établissement> - <compte>[/<année>] »."""


def morceaux_provenance(provenance: str) -> tuple[str, list[str]]:
    """Rendre le titulaire et les morceaux du dossier de compte (« AV - Suravenir - Vie Plus 1234 » en trois)."""
    parties = provenance.split("/")
    dossier = parties[1] if len(parties) > 1 else ""
    return parties[0], [m.strip() for m in dossier.split(" - ")]
