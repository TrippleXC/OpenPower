import arcade
from src.client.services.imgui_service import ImGuiService

class GameView(arcade.View):
    """
    The main gameplay mode.
    
    Refactoring Note:
        Even though this is a placeholder, it must use the same standard architecture 
        (ImGuiService) as the EditorView to ensure consistent window behavior 
        and input handling.
    """
    
    def __init__(self):
        super().__init__()
        # Initialize the standard UI service
        self.imgui = ImGuiService(self.window)
        
    def on_show_view(self):
        self.window.background_color = arcade.color.BLACK
        print("[GameView] Switched to Game Mode.")

    def on_resize(self, width: int, height: int):
        """Crucial: Update UI viewport on resize."""
        self.imgui.resize(width, height)

    def on_draw(self):
        self.clear()
        
        # 1. Start UI Frame
        self.imgui.new_frame(1.0 / 60.0)
        
        # 2. Draw Game Content (Placeholder)
        arcade.draw_text("GAMEPLAY MODE (Placeholder)", 
                         self.window.width / 2, self.window.height / 2,
                         arcade.color.WHITE, 30, anchor_x="center")
        
        # 3. Draw UI
        # (You could have a 'GameLayout' class here similar to EditorLayout)
        
        # 4. Render UI
        self.imgui.render()
        
    # --- Input Routing ---
    # Ensure UI gets input first, just like in EditorView
    
    def on_mouse_press(self, x, y, button, modifiers):
        if self.imgui.on_mouse_press(x, y, button, modifiers): return
        # Game logic here...

    def on_mouse_release(self, x, y, button, modifiers):
        if self.imgui.on_mouse_release(x, y, button, modifiers): return

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        if self.imgui.on_mouse_drag(x, y, dx, dy, buttons, modifiers): return

    def on_mouse_motion(self, x, y, dx, dy):
        self.imgui.on_mouse_motion(x, y, dx, dy)