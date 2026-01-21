import arcade
import threading
from typing import Callable, Any
from src.client.services.imgui_service import ImGuiService
from src.client.ui.composer import UIComposer
from src.client.ui.theme import GAMETHEME
from src.client.interfaces.loading import LoadingTask

class LoadingView(arcade.View):
    def __init__(self, 
                 task: LoadingTask, 
                 on_success: Callable[[Any], arcade.View],
                 on_failure: Callable[[Exception], None] | None = None):
        
        super().__init__()
        self.task = task
        self.on_success = on_success
        self.on_failure = on_failure
        
        self.imgui = ImGuiService(self.window)
        self.ui = UIComposer(GAMETHEME)
        
        # Threading Logic
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.is_finished = False
        self.result = None
        self.error = None

        # --- NEW: Sentinel to allow one render frame before switching ---
        self._finalizing_frame_rendered = False 

    def on_show_view(self):
        self.window.background_color = GAMETHEME.col_black
        self.thread.start()

    def _worker(self):
        try:
            self.result = self.task.run()
        except Exception as e:
            self.error = e
        finally:
            self.is_finished = True

    def on_update(self, delta_time: float):
        # If thread is done...
        if self.is_finished:
            if self.error:
                # Handle error immediately
                if self.on_failure: self.on_failure(self.error)
                else: raise self.error
            else:
                # --- THE FIX: DELAY SWITCHING BY 1 FRAME ---
                if not self._finalizing_frame_rendered:
                    # Update text to show we are now in the blocking phase
                    self.task.status_text = "Finalizing Graphics..."
                    self.task.progress = 1.0
                    self._finalizing_frame_rendered = True
                    return # RETURN HERE! Let on_draw() run one last time!

                # NOW we do the heavy main-thread switching
                next_view = self.on_success(self.result)
                
                if next_view:
                    self.window.show_view(next_view)

    # ... (rest of class: on_resize, on_draw remain the same) ...
    def on_resize(self, width: int, height: int):
        self.imgui.resize(width, height)

    def on_draw(self):
        self.clear()
        self.imgui.new_frame()
        self.ui.setup_frame()

        screen_w, screen_h = self.window.get_size()
        
        if self.ui.begin_centered_panel("Loader", screen_w, screen_h, w=400, h=150):
            self.ui.draw_title("PROCESSING")
            self.ui.draw_progress_bar(self.task.progress, self.task.status_text)
            
            if self.error:
                from imgui_bundle import imgui
                imgui.text_colored(GAMETHEME.col_error, "OPERATION FAILED")

            self.ui.end_panel()

        self.imgui.render()