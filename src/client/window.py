import arcade
from src.client.views.editor_view import EditorView

# Window configuration
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
SCREEN_TITLE = "OpenPower Engine"

class MainWindow(arcade.Window):
    """
    The main application window that manages different views (Editor, Game, Menu).
    """
    def __init__(self):
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE, resizable=True)
        
    def setup(self):
        """Initializes the window and sets the starting view."""
        # Defaulting to EditorView for now. CLI arguments can be added here later 
        # to allow selecting different modes on startup.
        start_view = EditorView()
        self.show_view(start_view)

    def on_resize(self, width, height):
        """Passes the resize event to the active view."""
        super().on_resize(width, height)
        # Explicitly passing resize to the super class, which in Arcade 
        # normally handles view resizing automatically for the current view.
