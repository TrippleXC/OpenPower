import arcade
import sys
from src.client.services.imgui_service import ImGuiService
from src.client.ui.composer import UIComposer
from src.client.ui.theme import SP2_THEME
from src.shared.config import GameConfig
from src.server.session import GameSession

# Import views to switch to
from src.client.views.editor_view import EditorView
from src.client.views.game_view import GameView

class MainMenuView(arcade.View):
    """
    The entry point of the game visual stack.
    """

    def __init__(self, session: GameSession, config: GameConfig):
        super().__init__()
        self.session = session
        self.config = config
        
        # Services
        self.imgui = ImGuiService(self.window)
        self.ui = UIComposer(SP2_THEME)

    def on_show_view(self):
        print("[MainMenuView] Entered Main Menu")
        # Set placeholder black background
        self.window.background_color = arcade.color.BLACK

    def on_resize(self, width: int, height: int):
        self.imgui.resize(width, height)

    def on_draw(self):
        self.clear()
        
        # Start UI Frame
        self.imgui.new_frame(1.0 / 60.0)
        
        # Apply Theme
        self.ui.setup_frame()
        
        # Render the Menu Logic
        self._render_menu_window()
        
        # Draw to screen
        self.imgui.render()

    def _render_menu_window(self):
        """Defines the layout and logic of the main menu."""
        screen_w, screen_h = self.window.get_size()
        
        # Use Composer to draw the panel
        if self.ui.begin_centered_panel("Main Menu", screen_w, screen_h, width=350, height=450):
            
            self.ui.draw_title("OPEN POWER")
            
            # -- Menu Buttons --
            if self.ui.draw_menu_button("SINGLE PLAYER"):
                # Transition to GameView
                game_view = GameView()
                self.window.show_view(game_view)
            
            if self.ui.draw_menu_button("MAP EDITOR"):
                # Transition to EditorView
                editor = EditorView(self.session, self.config)
                self.window.show_view(editor)
            
            if self.ui.draw_menu_button("SETTINGS"):
                print("Settings clicked (Not Implemented)")
            
            # Spacer
            from imgui_bundle import imgui
            imgui.dummy((0, 50)) 
            
            if self.ui.draw_menu_button("EXIT TO DESKTOP"):
                arcade.exit()
                sys.exit()

            self.ui.end_panel()

    # --- Input Delegation ---
    
    def on_mouse_press(self, x, y, button, modifiers):
        self.imgui.on_mouse_press(x, y, button, modifiers)

    def on_mouse_release(self, x, y, button, modifiers):
        self.imgui.on_mouse_release(x, y, button, modifiers)

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        self.imgui.on_mouse_drag(x, y, dx, dy, buttons, modifiers)

    def on_mouse_motion(self, x, y, dx, dy):
        self.imgui.on_mouse_motion(x, y, dx, dy)