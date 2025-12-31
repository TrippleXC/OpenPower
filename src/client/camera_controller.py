import arcade

class CameraController:
    """
    Manages camera zoom and pan logic.
    Ported logic from the Godot project's 'editor_camera.gd'.
    """
    def __init__(self, start_pos: arcade.math.Vector2):
        # Movement sensitivity constants.
        self.ZOOM_SPEED = 0.05
        self.MIN_ZOOM = 0.1
        self.MAX_ZOOM = 5.0

        self.position = start_pos
        self.zoom = 1.0

    def scroll(self, scroll_y: int):
        """Processes mouse wheel events for zooming."""
        if scroll_y > 0:
            self.zoom *= (1.0 + self.ZOOM_SPEED)
        elif scroll_y < 0:
            self.zoom *= (1.0 - self.ZOOM_SPEED)
        
        # Clamp
        self.zoom = max(self.MIN_ZOOM, min(self.zoom, self.MAX_ZOOM))

    def drag(self, dx: int, dy: int):
        """Processes mouse drag events for panning."""
        scale_factor = 1.0 / self.zoom
        self.position.x -= dx * scale_factor
        self.position.y -= dy * scale_factor

    def update_arcade_camera(self, camera: arcade.Camera, window_width: int, window_height: int):
        """Applies the calculated zoom and position to the arcade.Camera object."""
        viewport_w = window_width / self.zoom
        viewport_h = window_height / self.zoom
        
        # Calculate the bottom-left corner of the viewport to center it on self.position.
        left = self.position.x - (viewport_w / 2)
        bottom = self.position.y - (viewport_h / 2)
        
        camera.set_projection(
            left=left,
            right=left + viewport_w,
            bottom=bottom,
            top=bottom + viewport_h
        )

    def screen_to_world(self, screen_x: float, screen_y: float, window_width: int, window_height: int) -> tuple[float, float]:
        """Converts screen-space mouse coordinates to absolute world-space coordinates."""
        viewport_w = window_width / self.zoom
        viewport_h = window_height / self.zoom
        
        cam_left = self.position.x - (viewport_w / 2)
        cam_bottom = self.position.y - (viewport_h / 2)
        
        world_x = cam_left + (screen_x / self.zoom)
        world_y = cam_bottom + (screen_y / self.zoom)
        
        return world_x, world_y
