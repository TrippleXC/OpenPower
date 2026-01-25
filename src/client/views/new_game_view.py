import arcade
import polars as pl
from typing import TYPE_CHECKING, Optional

# Base Class (Provides self.nav and ImGui handling)
from src.client.views.base_view import BaseImGuiView

from src.client.services.network_client_service import NetworkClient
from src.client.ui.composer import UIComposer
from src.client.ui.theme import GAMETHEME
from src.shared.config import GameConfig
from src.client.utils.coords_util import calculate_centroid
from src.client.tasks.new_game_task import NewGameTask, NewGameContext

if TYPE_CHECKING:
    from src.server.session import GameSession

class NewGameView(BaseImGuiView):
    """
    Screen to select a country and start the campaign.
    """
    def __init__(self, session: "GameSession", config: GameConfig):
        super().__init__()
        self.session = session 
        self.config = config
        
        # Use NetworkClient for reading data
        self.net = NetworkClient(session)
        
        # UI Composer (ImGuiService is handled by BaseImGuiView)
        self.ui = UIComposer(GAMETHEME)
        
        self.selected_country_id: Optional[str] = None
        self.playable_countries = self._fetch_playable_countries()

    def _fetch_playable_countries(self) -> pl.DataFrame:
        try:
            state = self.net.get_state()
            df = state.get_table("countries")
            return df.filter(pl.col("is_playable") == True).sort("id")
        except KeyError:
            print("[NewGameView] 'countries' table not found in state.")
            return pl.DataFrame()

    def on_show_view(self):
        self.window.background_color = arcade.color.BLACK_OLIVE

    def on_draw(self):
        self.clear()
        
        self.imgui.new_frame()
        self.ui.setup_frame()
        self._render_ui()
        self.imgui.render()

    def _render_ui(self):
        screen_w, screen_h = self.window.get_size()
        
        if self.ui.begin_centered_panel("New Game", screen_w, screen_h, w=600, h=500):
            self.ui.draw_title("SELECT NATION")
            
            from imgui_bundle import imgui
            
            # --- Country List (Left Side) ---
            imgui.begin_child("CountryList", (250, 350), True)
            if not self.playable_countries.is_empty():
                for row in self.playable_countries.iter_rows(named=True):
                    c_id = row['id']
                    label = f"{c_id}"
                    is_selected = (self.selected_country_id == c_id)
                    if imgui.selectable(label, is_selected)[0]:
                        self.selected_country_id = c_id
            else:
                imgui.text_disabled("No countries loaded.")
            imgui.end_child()
            
            imgui.same_line()
            
            # --- Details Panel (Right Side) ---
            imgui.begin_group()
            imgui.dummy((300, 0))
            if self.selected_country_id:
                imgui.text_colored(GAMETHEME.col_active_accent, f"Selected: {self.selected_country_id}")
                imgui.separator()
                imgui.text_wrapped("Description placeholder.")
            else:
                imgui.text_disabled("Select a nation from the list.")
            imgui.end_group()
            
            imgui.dummy((0, 20))
            imgui.separator()
            imgui.dummy((0, 10))
            
            # --- Bottom Buttons ---
            
            # BACK BUTTON: Use Router
            if imgui.button("BACK", (100, 40)):
                self.nav.show_main_menu(self.session, self.config)
                
            imgui.same_line()
            avail_w = imgui.get_content_region_avail().x
            imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + avail_w - 150)
            
            # START BUTTON
            if self.selected_country_id:
                if imgui.button("START CAMPAIGN", (150, 40)):
                    self._start_game()
            else:
                imgui.begin_disabled()
                imgui.button("START CAMPAIGN", (150, 40))
                imgui.end_disabled()

            self.ui.end_panel()

    def _start_game(self):
        """
        Initiates the sequence to start the campaign:
        1. Checks validity.
        2. Creates a background task to calculate positions.
        3. Transitions to the generic Loading Screen.
        """
        if not self.selected_country_id:
            return

        # Import locally to avoid circular dependencies during file initialization
        from src.client.tasks.new_game_task import NewGameTask, NewGameContext

        # 1. Define the callback
        # This function will run on the Main Thread once the Loading Task is 100% complete.
        def on_task_complete(ctx: NewGameContext):
            # Use the data calculated in the background (ctx.start_pos) to initialize the view
            self.nav.show_game_view(
                session=ctx.session,
                config=self.config,
                player_tag=ctx.player_tag,
                initial_pos=ctx.start_pos
            )
            # Returning None tells the LoadingView: "I have handled the screen switch, you don't need to do anything else."
            return None

        # 2. Create the background task
        # This object holds the logic for calculating the centroid and initializing the session
        task = NewGameTask(self.session, self.config, self.selected_country_id)

        # 3. Hand off control to the Navigation Service
        # The user will immediately see the Loading Screen while 'task.run()' executes in a thread.
        self.nav.show_loading(task, on_success=on_task_complete)