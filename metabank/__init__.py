"""metabank : vision globale et analyse de mon patrimoine financier, en local."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("metabank")
except PackageNotFoundError:
    __version__ = "inconnue"
