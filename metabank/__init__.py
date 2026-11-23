"""metabank : vision globale et analyse de mon patrimoine financier, en local."""

import tomllib
from pathlib import Path

# metabank n'est pas installé comme paquet (uv run depuis le dépôt) : la version se lit dans pyproject.toml.
try:
    __version__ = tomllib.loads((Path(__file__).parent.parent / "pyproject.toml").read_text())["project"]["version"]
except (OSError, KeyError, tomllib.TOMLDecodeError):
    __version__ = "inconnue"
