# utils/global_task_tracker.py
import threading

ACTIVE_TASK_COUNT = 0
_lock = threading.Lock()


def increment_task_count():
    """Incrémente le compteur global de tâches actives de manière thread-safe."""
    global ACTIVE_TASK_COUNT
    with _lock:
        ACTIVE_TASK_COUNT += 1


def decrement_task_count():
    """Décrémente le compteur global de tâches actives de manière thread-safe."""
    global ACTIVE_TASK_COUNT
    with _lock:
        if ACTIVE_TASK_COUNT > 0:
            ACTIVE_TASK_COUNT -= 1


def is_busy():
    """Vérifie s'il y a des tâches actives."""
    global ACTIVE_TASK_COUNT
    with _lock:
        return ACTIVE_TASK_COUNT > 0