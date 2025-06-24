# utils/global_events.py
import queue

# File d'attente pour communiquer les changements de statut du backend vers l'UI
# Les messages seront des tuples, ex: ("Base de données occupée...", True)
status_update_queue = queue.Queue()