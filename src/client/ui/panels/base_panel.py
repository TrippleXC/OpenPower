from abc import ABC, abstractmethod
from typing import Optional
from src.client.ui.composer import UIComposer

class BasePanel(ABC):
    """
    Abstract base class for all UI panels.
    Handles the ImGui window lifecycle (Begin/End) automatically.
    """
    def __init__(self, title: str, x: int, y: int, w: int, h: int):
        self.title = title
        self.default_x = x
        self.default_y = y
        self.default_w = w
        self.default_h = h

    def render(self, composer: UIComposer, state, **kwargs) -> bool:
        """
        Public template method.
        Returns: False if the user clicked the 'X' button (requesting close).
        """
        # 1. Start the window
        expanded, opened = composer.begin_panel(
            self.title, 
            self.default_x, 
            self.default_y, 
            self.default_w, 
            self.default_h, 
            is_visible=True
        )

        # 2. Render content if not collapsed
        if expanded:
            try:
                self._render_content(composer, state, **kwargs)
            except Exception as e:
                # Fallback error display to prevent crashing the whole UI
                from imgui_bundle import imgui
                imgui.text_colored((1, 0, 0, 1), f"Panel Error: {e}")
                print(f"[{self.title}] Error: {e}")

        # 3. End the window
        composer.end_panel()
        
        return opened # type: ignore

    @abstractmethod
    def _render_content(self, composer: UIComposer, state, **kwargs):
        """
        Subclasses must implement the actual UI drawing here.
        """
        pass