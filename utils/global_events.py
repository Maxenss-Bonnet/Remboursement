import queue

# File d'attente pour communiquer les changements de statut du backend vers l'UI
# Les messages seront des tuples, ex: ("Base de données occupée...", True)
status_update_queue = queue.Queue()

# File d'attente pour communiquer l'état de la connexion réseau
# Les messages seront des booléens : True pour connecté, False pour déconnecté
network_status_queue = queue.Queue()