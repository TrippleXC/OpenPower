import arcade
import orjson
from src.client.services.imgui_service import ImGuiService
from src.client.ui.composer import UIComposer
from src.client.ui.theme import GAMETHEME
from src.shared.config import GameConfig
from src.server.session import GameSession
from src.server.io.save_writer import SaveWriter
from src.server.io.data_load_manager import DataLoader
from src.client.views.game_view import GameView
from src.client.views.loading_view import LoadingView
from src.client.tasks.startup_task import StartupTask # Reuse or make generic

class LoadGameView(arcade.View):
    def __init__(self, config: GameConfig):
        super().__init__()
        self.config = config
        self.imgui = ImGuiService(self.window)
        self.ui = UIComposer(GAMETHEME)
        
        # Initialize Save Helpers
        self.writer = SaveWriter(config) # Used for listing saves
        self.loader = DataLoader(config)
        
        self.save_list = self.writer.get_available_saves()
        self.selected_save_name = None

    def on_show_view(self):
        self.window.background_color = GAMETHEME.col_black

    def on_draw(self):
        self.clear()
        self.imgui.new_frame()
        self.ui.setup_frame()
        
        screen_w, screen_h = self.window.get_size()
        
        if self.ui.begin_centered_panel("Load Game", screen_w, screen_h, w=500, h=600):
            self.ui.draw_title("LOAD GAME")
            
            from imgui_bundle import imgui
            
            # SAVE LIST
            imgui.begin_child("SaveList", (0, 400), True)
            if not self.save_list:
                imgui.text_disabled("No saves found.")
            else:
                for save in self.save_list:
                    name = save['name']
                    date = save['timestamp'][:16].replace("T", " ")
                    label = f"{name}  |  {date}"
                    
                    if imgui.selectable(label, self.selected_save_name == name)[0]:
                        self.selected_save_name = name
            imgui.end_child()
            
            imgui.dummy((0, 20))
            
            # BUTTONS
            if imgui.button("BACK", (100, 40)):
                from src.client.views.main_menu_view import MainMenuView
                # Note: We pass None for session as we are going back to menu
                self.window.show_view(MainMenuView(None, self.config)) # type: ignore TODO: fix type error
                
            imgui.same_line()
            avail_w = imgui.get_content_region_avail().x
            imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + avail_w - 150)
            
            if self.selected_save_name:
                if imgui.button("LOAD", (150, 40)):
                    self._load_selected_save()
            else:
                imgui.begin_disabled()
                imgui.button("LOAD", (150, 40))
                imgui.end_disabled()

            self.ui.end_panel()
        
        self.imgui.render()

    def _load_selected_save(self):
        # Trigger Loading Sequence
        print(f"Loading {self.selected_save_name}...")
        
        # 1. Create a Custom Task to load the save
        class SaveLoadTask:
            def __init__(self, config, save_name, loader):
                self.config = config
                self.save_name = save_name
                self.loader = loader
                self.progress = 0.0
                self.status_text = "Loading Save..."

            def run(self):
                # We need to recreate the GameSession with the loaded state
                # 1. Load State
                self.status_text = "Reading State from Disk..."
                self.progress = 0.3
                loaded_state = self.loader.load_save(self.save_name)
                
                # 2. Spin up Session (Similar to StartupTask)
                self.status_text = "Initializing Engine..."
                self.progress = 0.6
                
                # We reuse GameSession.create_local but inject the loaded state
                # Note: This requires a slight refactor of GameSession.create_local 
                # or we manually assemble it here. For MVP, let's manually assemble.
                
                from src.server.session import GameSession
                from src.server.io.data_export_manager import DataExporter
                from src.engine.simulator import Engine
                from src.engine.mod_manager import ModManager
                from src.core.map_data import RegionMapData
                
                # Dependencies
                exporter = DataExporter(self.config)
                engine = Engine()
                mod_mgr = ModManager(self.config)
                
                # Load Systems
                mods = mod_mgr.resolve_load_order()
                systems = mod_mgr.load_systems()
                engine.register_systems(systems)
                
                # Map Data
                map_path = self.config.get_asset_path("map/regions.png")
                map_data = RegionMapData(str(map_path))
                
                session = GameSession(
                    self.config, self.loader, exporter, engine, map_data, loaded_state
                )
                
                self.progress = 1.0
                return session

        task = SaveLoadTask(self.config, self.selected_save_name, self.loader)
        
        def on_success(session):
            # Assuming 'player_tag' is stored in globals or we default to a country
            player_tag = session.state.globals.get("player_tag", "USA") 
            return GameView(session, self.config, player_tag)

        self.window.show_view(LoadingView(task, on_success))

    # --- Input Passthrough ---
    def on_resize(self, w, h): self.imgui.resize(w, h)
    def on_mouse_press(self, x, y, b, m): self.imgui.on_mouse_press(x, y, b, m)
    def on_mouse_release(self, x, y, b, m): self.imgui.on_mouse_release(x, y, b, m)
    def on_mouse_drag(self, x, y, dx, dy, b, m): self.imgui.on_mouse_drag(x, y, dx, dy, b, m)
    def on_mouse_motion(self, x, y, dx, dy): self.imgui.on_mouse_motion(x, y, dx, dy)