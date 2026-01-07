from dataclasses import dataclass
from imgui_bundle import imgui

@dataclass
class UITheme:
    """
    Defines the visual properties of the UI.
    Swapping this object changes the entire feel of the game (SP2 vs Editor vs Fantasy).
    """
    # Colors (RGBA tuple 0.0 - 1.0)
    text_main: tuple = (0.0, 1.0, 1.0, 1.0)        # SP2 Cyan
    text_dim: tuple = (0.0, 0.7, 0.7, 1.0)
    
    window_bg: tuple = (0.05, 0.05, 0.1, 0.85)     # Dark Blue Semi-transparent
    border: tuple = (0.0, 1.0, 1.0, 0.5)           # Thin Cyan Border
    
    button_normal: tuple = (0.0, 0.2, 0.3, 0.6)
    button_hover: tuple = (0.0, 0.4, 0.6, 0.8)
    button_active: tuple = (0.0, 0.6, 0.8, 1.0)

    # Geometry
    rounding: float = 0.0  # SP2 is very sharp/angular
    padding: tuple = (15.0, 10.0)
    
    def apply_global_styles(self):
        """Pushes style vars that should apply to the whole UI context."""
        # Note: In a full engine, you might manage the stack more carefully.
        style = imgui.get_style()
        style.window_rounding = self.rounding
        style.frame_rounding = self.rounding
        style.popup_rounding = self.rounding
        style.scrollbar_rounding = self.rounding
        
        # Adjust generic colors
        style.set_color_(imgui.Col_.text, self.text_main)
        style.set_color_(imgui.Col_.window_bg, self.window_bg)
        style.set_color_(imgui.Col_.border, self.border)
        style.set_color_(imgui.Col_.button, self.button_normal)
        style.set_color_(imgui.Col_.button_hovered, self.button_hover)
        style.set_color_(imgui.Col_.button_active, self.button_active)

# Pre-defined SP2 Style Instance
SP2_THEME = UITheme()