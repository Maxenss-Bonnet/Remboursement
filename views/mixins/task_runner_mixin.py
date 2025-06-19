# views/mixins/task_runner_mixin.py
import threading
import queue
from utils.ui_utils import LoadingOverlay
from utils import global_task_tracker


class TaskRunnerMixin:
    def __init__(self, parent_for_overlay):
        self.loading_overlay = LoadingOverlay(parent_for_overlay)
        self._loading_task_count = 0
        self._overlay_show_job = None

    def run_task(self, task_function, on_complete, loading_message="Chargement...", show_overlay=True):
        global_task_tracker.increment_task_count()
        self._loading_task_count += 1

        if show_overlay and self._loading_task_count == 1:
            self.loading_overlay.set_message(loading_message)
            self._overlay_show_job = self.after(300, self.loading_overlay.show)

        task_queue = queue.Queue()

        def worker():
            try:
                result = task_function()
                task_queue.put(('success', result))
            except Exception as e:
                task_queue.put(('error', e))

        def check_queue():
            try:
                status, result = task_queue.get_nowait()
                global_task_tracker.decrement_task_count()
                self._loading_task_count -= 1

                if self._loading_task_count == 0:
                    if self._overlay_show_job:
                        self.after_cancel(self._overlay_show_job)
                        self._overlay_show_job = None
                    self.loading_overlay.hide()

                if status == 'error':
                    print(f"Erreur dans le thread: {result}")
                    if on_complete:
                        on_complete(None, result)
                else:
                    if on_complete:
                        on_complete(result, None)

            except queue.Empty:
                self.after(100, check_queue)

        threading.Thread(target=worker, daemon=True).start()
        self.after(100, check_queue)