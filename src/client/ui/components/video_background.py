import arcade
import pyglet
from pathlib import Path

class VideoBackground:
    def __init__(self, video_path: Path, window: arcade.Window):
        self.window = window
        self.video_path = str(video_path)
        
        # 1. Initialize Pyglet Media Player
        self.player = pyglet.media.Player()
        
        # 2. Load Source
        try:
            self.source = pyglet.media.load(self.video_path)
        except FileNotFoundError:
            print(f"Error: Video file not found at {self.video_path}")
            self.source = None
            return
            
        # 3. Setup Looping via Event Handler
        # We explicitly register the class method to handle the 'on_eos' event
        self.player.push_handlers(on_eos=self._on_eos)
        
        self.player.queue(self.source)
        self.player.play()
        
        # 4. Layout State
        self.draw_x = 0
        self.draw_y = 0
        self.draw_w = window.width
        self.draw_h = window.height

    def _on_eos(self):
        """
        Callback triggered by Pyglet when the video ends.
        We rewind to the beginning to loop it.
        """
        self.player.seek(0)
        self.player.play()

    def resize(self):
        """Recalculate video scale to cover the screen (aspect fill)."""
        if not self.source or not self.source.video_format:
            return

        vw = self.source.video_format.width
        vh = self.source.video_format.height
        sw, sh = self.window.get_size()

        # Calculate Aspect Ratio
        video_ratio = vw / vh
        screen_ratio = sw / sh

        if screen_ratio > video_ratio:
            # Screen is wider than video -> Fit to Width
            self.draw_w = sw
            self.draw_h = sw / video_ratio
        else:
            # Screen is taller than video -> Fit to Height
            self.draw_w = sh * video_ratio
            self.draw_h = sh

        # Center it
        self.draw_x = (sw - self.draw_w) / 2
        self.draw_y = (sh - self.draw_h) / 2

    def draw(self):
        """
        Draws the current video frame directly to the screen.
        """
        if not self.source: 
            return

        # Get the underlying Pyglet texture for the current frame
        tex = self.player.get_texture() # type: ignore
        
        if tex:
            # We use direct blit for maximum performance with video frames
            tex.blit(
                self.draw_x, 
                self.draw_y, 
                width=self.draw_w, 
                height=self.draw_h
            )

    def pause(self):
        self.player.pause()

    def resume(self):
        self.player.play()