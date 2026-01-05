import arcade
from pyglet.math import Vec2

class CameraController:
    """
    Manages camera state (Position, Zoom) and logic for the Editor.
    
    Refactoring Note:
        This class encapsulates all vector math related to view manipulation.
        The View should simply tell this controller *what* the user did (drag, scroll),
        and this controller handles the *how* (applying zoom scales, clamping values).
    """

    def __init__(self, start_pos: tuple[float, float]):
        self.ZOOM_SPEED = 0.1
        self.MIN_ZOOM = 0.1
        self.MAX_ZOOM = 5.0

        # Store position as a Vec2 for easy vector arithmetic
        self.position = Vec2(start_pos[0], start_pos[1])
        self.zoom = 1.0

    def pan(self, dx: float, dy: float):
        """
        Moves the camera based on screen-space drag deltas.
        
        Why this is here:
            The View receives mouse drag events in Screen Pixels. 
            However, the camera moves in World Units. The relationship between 
            the two depends on the current Zoom level. This logic belongs here, 
            not in the View.
        """
        # Calculate how much world space is covered by one screen pixel
        scale_factor = 1.0 / self.zoom
        
        # Invert direction: Dragging mouse RIGHT moves camera LEFT (to show content on the left)
        # We subtract the movement vector.
        movement = Vec2(dx, dy) * scale_factor
        self.position -= movement

    def zoom_scroll(self, scroll_y: int):
        """
        Adjusts zoom level based on mouse wheel input.
        """
        # Determine direction
        direction = 1.0 if scroll_y > 0 else -1.0
        
        # Apply zoom
        self.zoom += direction * self.ZOOM_SPEED
        
        # Clamp values to prevent the map from flipping or becoming microscopic
        self.zoom = max(self.MIN_ZOOM, min(self.zoom, self.MAX_ZOOM))

    def jump_to(self, x: float, y: float):
        """Instantly teleports the camera to a world coordinate."""
        self.position = Vec2(x, y)

    def update_arcade_camera(self, camera: arcade.Camera2D):
        """
        Syncs the internal logic state with the rendering engine's Camera object.
        
        This separates 'Logic State' (this class) from 'Render State' (Arcade).
        """
        camera.position = self.position
        camera.zoom = self.zoom

    def screen_to_world(self, screen_x: float, screen_y: float, window_width: int, window_height: int) -> tuple[float, float]:
        """
        Utility to convert screen coordinates to world coordinates manually.
        Useful if we don't have access to the arcade.Camera2D.unproject() method 
        in a specific context, though unproject() is preferred where possible.
        """
        viewport_w = window_width / self.zoom
        viewport_h = window_height / self.zoom
        
        cam_left = self.position.x - (viewport_w / 2)
        cam_bottom = self.position.y - (viewport_h / 2)
        
        world_x = cam_left + (screen_x / self.zoom)
        world_y = cam_bottom + (screen_y / self.zoom)
        
        return world_x, world_y