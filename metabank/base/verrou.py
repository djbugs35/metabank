"""Un seul écrivain à la fois dans data/ : fiches CSV, archives et base.

Au lancement, la mise à jour des comptes en connexion directe (un fil à part) et la première page demandent les
données en même temps. Sans ce verrou, quand la version des lecteurs change, les deux reconstruisent la base et
écrivent les mêmes fiches par le même fichier temporaire : l'un des deux échoue (FileNotFoundError, mesuré au
lancement du 2026-11-25) et la page affiche « Failed to fetch ». Réentrant : un chargement qui archive puis ouvre
la base le reprend sans se bloquer lui-même.
"""

import threading

VERROU_DONNEES = threading.RLock()
