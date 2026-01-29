import arcade
import polars as pl
from pathlib import Path
from typing import Dict, Optional, Any
from imgui_bundle import imgui, icons_fontawesome_6

from src.client.ui.composer import UIComposer
from src.client.ui.theme import GAMETHEME
from src.client.services.network_client_service import NetworkClient
from src.shared.actions import ActionSetGameSpeed, ActionSetPaused

class CentralBar:
    def __init__(self):
        self.show_speed_controls = True
        self.news_ticker_text = "Welcome to OpenPower. Global news will appear here..."
        
        # Internal Cache for flags
        self._flag_cache: Dict[str, arcade.Texture] = {}
        self.active_player_tag = "" 

    def render(self, composer: UIComposer, state, net: NetworkClient, player_tag: str) -> str:
        self.active_player_tag = player_tag
        
        viewport = imgui.get_main_viewport()
        screen_w = viewport.size.x
        screen_h = viewport.size.y
        
        bar_w = 800
        bar_h = 85
        
        imgui.set_next_window_pos(( (screen_w - bar_w)/2, screen_h - bar_h - 10 ))
        imgui.set_next_window_size((bar_w, bar_h))

        flags = (imgui.WindowFlags_.no_decoration | 
                 imgui.WindowFlags_.no_move | 
                 imgui.WindowFlags_.no_scroll_with_mouse |
                 imgui.WindowFlags_.no_background)

        # SAFE WINDOW BLOCK
        if imgui.begin("CentralBar", True, flags):
            try:
                draw_list = imgui.get_window_draw_list()
                p = imgui.get_cursor_screen_pos()
                
                # Draw Backgrounds
                draw_list.add_rect_filled(p, (p.x + bar_w, p.y + 60), imgui.get_color_u32(GAMETHEME.col_panel_bg))
                draw_list.add_rect_filled((p.x, p.y + 60), (p.x + bar_w, p.y + bar_h), imgui.get_color_u32(GAMETHEME.col_overlay_bg))
                draw_list.add_rect(p, (p.x + bar_w, p.y + bar_h), imgui.get_color_u32(GAMETHEME.border), 4.0)

                # --- Section 1: Flag & Country (LEFT) ---
                imgui.set_cursor_pos((10, 10))
                imgui.begin_group()
                
                flag_tex = self._get_flag_texture(player_tag)
                
                if flag_tex:
                    tex_id = self._get_texture_id(flag_tex)
                    # type: ignore - We intentionally pass int ID instead of Texture obj to satisfy ImGui C++
                    composer.draw_image(tex_id, 80, 50) # type: ignore
                else:
                    composer.dummy((80, 50))
                
                imgui.same_line()
                
                imgui.begin_group()
                if imgui.button(f" {player_tag} ", (150, 24)):
                    imgui.open_popup("CountrySelectorPopup")
                
                imgui.push_style_var(imgui.StyleVar_.item_spacing, (2, 0))
                self._draw_status_button("ALLIED", GAMETHEME.col_positive)
                imgui.same_line()
                self._draw_status_button("RELATIONS", GAMETHEME.col_button_idle)
                imgui.same_line()
                self._draw_status_button("INFO", GAMETHEME.col_button_idle)
                imgui.pop_style_var()
                
                imgui.end_group()
                imgui.end_group()

                # --- Section 2: Quick Actions (CENTER) ---
                imgui.set_cursor_pos((350, 12)) 
                
                btn_sz = (45, 45)
                
                # Removed set_window_font_scale as it is not supported in this binding.
                # Standard icons will be used.
                if imgui.button(f"{icons_fontawesome_6.ICON_FA_DESKTOP}", btn_sz): pass
                imgui.same_line()
                if imgui.button(f"{icons_fontawesome_6.ICON_FA_CHART_LINE}", btn_sz): pass
                imgui.same_line()
                if imgui.button(f"{icons_fontawesome_6.ICON_FA_MESSAGE}", btn_sz): pass

                # --- Section 3: Time Control (RIGHT) ---
                imgui.set_cursor_pos((bar_w - 260, 12))
                self._render_time_section(state, net)

                # --- Section 4: News Ticker ---
                imgui.set_cursor_pos((10, 64)) 
                imgui.text_colored(GAMETHEME.col_text_bright, f">> {self.news_ticker_text}")
                
                imgui.same_line()
                imgui.set_cursor_pos_x(bar_w - 50)
                if imgui.button(f"{icons_fontawesome_6.ICON_FA_NEWSPAPER}", (40, 18)): pass

                # --- Popups ---
                self._render_country_selector_popup(state)

            except Exception as e:
                print(f"[CentralBar] Error: {e}")
            finally:
                imgui.end()
        else:
            imgui.end()
            
        return self.active_player_tag

    def _render_time_section(self, state, net):
        imgui.begin_group()
        try:
            if imgui.button("TIME", (50, 45)):
                self.show_speed_controls = not self.show_speed_controls
            
            imgui.same_line()
            
            # Decoration Box
            draw_list = imgui.get_window_draw_list()
            p = imgui.get_cursor_screen_pos()
            box_w, box_h = 160, 45
            draw_list.add_rect_filled(p, (p.x + box_w, p.y + box_h), imgui.get_color_u32((0, 0, 0, 1)))
            draw_list.add_rect(p, (p.x + box_w, p.y + box_h), imgui.get_color_u32(GAMETHEME.border))

            imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + 8)
            imgui.set_cursor_pos_y(imgui.get_cursor_pos_y() + 7)

            if self.show_speed_controls:
                # Retrieve current state safely
                current_speed = getattr(state.time, "speed", 1)
                is_paused = getattr(state.time, "paused", False)
                
                btn_s = (30, 30)

                # --- PAUSE BUTTON ---
                if is_paused: imgui.push_style_color(imgui.Col_.button, GAMETHEME.col_positive)
                if imgui.button(icons_fontawesome_6.ICON_FA_PAUSE, btn_s): 
                    net.send_action(ActionSetPaused("local", True))
                if is_paused: imgui.pop_style_color()
                
                imgui.same_line()

                # --- SPEED 1 ---
                active_t1 = (current_speed == 1 and not is_paused)
                if active_t1: imgui.push_style_color(imgui.Col_.button, GAMETHEME.col_positive)
                if imgui.button("1", btn_s): self._set_speed(net, 1)
                if active_t1: imgui.pop_style_color()

                imgui.same_line()
                
                # --- SPEED 2 ---
                active_t2 = (current_speed == 2 and not is_paused)
                if active_t2: imgui.push_style_color(imgui.Col_.button, GAMETHEME.col_positive)
                if imgui.button("2", btn_s): self._set_speed(net, 2)
                if active_t2: imgui.pop_style_color()

                imgui.same_line()

                # --- SPEED 3 ---
                active_t3 = (current_speed == 3 and not is_paused)
                if active_t3: imgui.push_style_color(imgui.Col_.button, GAMETHEME.col_positive)
                if imgui.button("3", btn_s): self._set_speed(net, 3)
                if active_t3: imgui.pop_style_color()

            else:
                # Date Display
                t = state.time
                parts = t.date_str.split(" ")
                date_part = parts[0] if len(parts) > 0 else "N/A"
                time_part = parts[1] if len(parts) > 1 else ""
                
                imgui.set_cursor_pos_y(imgui.get_cursor_pos_y() + 5)
                imgui.text_colored(GAMETHEME.col_positive, date_part)
                imgui.same_line()
                imgui.text_colored(GAMETHEME.col_text_bright, time_part)

        except Exception as e:
            print(f"[TimeSection] Error: {e}")
        finally:
            imgui.end_group()

    def _render_country_selector_popup(self, state):
        if imgui.begin_popup("CountrySelectorPopup"):
            try:
                imgui.text_disabled("Switch Viewpoint")
                imgui.separator()
                if "countries" in state.tables:
                    df = state.tables["countries"]
                    for row in df.head(50).iter_rows(named=True):
                        tag = row['id']
                        name = row.get('name', tag)
                        
                        if imgui.selectable(f"{tag} - {name}", False)[0]:
                            self.active_player_tag = tag
            finally:
                imgui.end_popup()

    def _set_speed(self, net, speed):
        net.send_action(ActionSetPaused("local", False))
        net.send_action(ActionSetGameSpeed("local", speed))

    def _draw_status_button(self, label, color_bg):
        imgui.push_style_color(imgui.Col_.button, color_bg)
        imgui.button(label, (50, 20))
        imgui.pop_style_color()

    def _get_flag_texture(self, tag: str) -> Optional[arcade.Texture]:
        if tag in self._flag_cache:
            return self._flag_cache[tag]

        try:
            base_path = Path(f"modules/base/assets/flags/{tag}.png")
            if not base_path.exists():
                base_path = Path("modules/base/assets/flags/XXX.png")
            
            if not base_path.exists():
                return None 
                
            texture = arcade.load_texture(str(base_path))
            self._flag_cache[tag] = texture
            return texture
        except Exception as e:
            print(f"[CentralBar] Flag Load Error: {e}")
            return None

    def _get_texture_id(self, texture: arcade.Texture) -> int:
        """
        Safely extracts the OpenGL ID from an Arcade Texture.
        Uses getattr to handle different Arcade versions (2.6 vs 3.0) 
        and silence static analysis errors.
        """
        # Arcade 3.0+ uses a 'glo' object
        glo = getattr(texture, "glo", None)
        if glo:
            return int(glo.glo_id)

        # Legacy Arcade 2.6 uses direct 'gl_id'
        return int(getattr(texture, "gl_id", 0))