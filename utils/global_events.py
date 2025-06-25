import queue

# File d'attente pour les mises à jour de la barre de statut principale
# (message, is_persistent)
status_update_queue = queue.Queue()

# File d'attente pour l'état de la connexion réseau (True pour connecté, False pour déconnecté)
network_status_queue = queue.Queue()

# File d'attente pour mettre à jour le texte du widget de chargement (Loader)
# (message)
loader_status_queue = queue.Queue()