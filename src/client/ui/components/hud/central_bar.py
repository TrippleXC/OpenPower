import arcade
from typing import Optional
from imgui_bundle import imgui, icons_fontawesome_6

from src.client.ui.composer import UIComposer
from src.client.ui.theme import GAMETHEME
from src.client.services.network_client_service import NetworkClient
from src.client.renderers.flag_renderer import FlagRenderer
from src.shared.actions import ActionSetGameSpeed, ActionSetPaused

class CentralBar:
    """
    Main HUD element at the bottom of the screen.
    Features: Country Info, Time Controls, Quick Actions, and News Ticker.
    """
    def __init__(self):
        # --- View State ---
        self.show_speed_controls = True 
        self.news_ticker_text = "Global News: Simulation initialized and running."
        self.flag_renderer = FlagRenderer()
        self.active_player_tag = "" 

        # --- Layout Settings ---
        self.height = 100.0                # Master height control
        self.top_section_h_pct = 0.65      # Top 65% for controls, bottom 35% for news
        
        # Scaling factor for internal buttons (0.8 = buttons take 80% of top section height)
        self.content_scale_factor = 0.80   

    def render(self, composer: UIComposer, state, net: NetworkClient, player_tag: str) -> str:
        self.active_player_tag = player_tag
        
        viewport = imgui.get_main_viewport()
        screen_w = viewport.size.x
        screen_h = viewport.size.y
        
        # --- 1. Window Positioning ---
        # Width: Dynamic but clamped between 650px and 950px
        bar_width = max(650.0, min(screen_w * 0.40, 950.0))
        
        pos_x = (screen_w - bar_width) / 2
        pos_y = screen_h - self.height - 15  # 15px margin from bottom

        imgui.set_next_window_pos((pos_x, pos_y))
        imgui.set_next_window_size((bar_width, self.height))

        # Remove default padding for manual layout control
        imgui.push_style_var(imgui.StyleVar_.window_padding, (0, 0))

        flags = (imgui.WindowFlags_.no_decoration | 
                 imgui.WindowFlags_.no_move | 
                 imgui.WindowFlags_.no_scroll_with_mouse |
                 imgui.WindowFlags_.no_background)

        if imgui.begin("CentralBar", True, flags):
            try:
                draw_list = imgui.get_window_draw_list()
                p = imgui.get_cursor_screen_pos()
                
                w = imgui.get_window_width()
                h = imgui.get_window_height()
                
                top_h = h * self.top_section_h_pct
                ticker_h = h - top_h

                # --- 2. Background Drawing ---
                # Top Panel
                draw_list.add_rect_filled(
                    p, (p.x + w, p.y + top_h), 
                    imgui.get_color_u32(GAMETHEME.col_panel_bg),
                    GAMETHEME.rounding, imgui.ImDrawFlags_.round_corners_top
                )
                # Bottom Ticker Panel
                draw_list.add_rect_filled(
                    (p.x, p.y + top_h), (p.x + w, p.y + h), 
                    imgui.get_color_u32(GAMETHEME.col_overlay_bg),
                    GAMETHEME.rounding, imgui.ImDrawFlags_.round_corners_bottom
                )
                # Border
                draw_list.add_rect(
                    p, (p.x + w, p.y + h), 
                    imgui.get_color_u32(GAMETHEME.border),
                    GAMETHEME.rounding, 0, 1.5
                )

                # --- 3. Layout Calculations ---
                padding_x = 12.0
                
                # Height of internal buttons
                inner_item_h = top_h * self.content_scale_factor
                content_y = (top_h - inner_item_h) / 2

                # Section Widths (Reserved space)
                left_section_w = 170.0  
                right_section_w = 250.0 

                # --- A. LEFT: Country Info ---
                imgui.set_cursor_pos((padding_x, content_y))
                self._render_country_info(composer, inner_item_h)

                # --- B. RIGHT: Time Controls ---
                right_start_x = w - right_section_w - padding_x
                imgui.set_cursor_pos((right_start_x, content_y))
                self._render_time_controls(state, net, right_section_w, inner_item_h)

                # --- C. CENTER: Quick Actions ---
                # FIX: Dynamically calculate exact width of the center button group
                # to prevent overlapping with the Right section.
                btn_count = 3
                btn_spacing = 10.0
                # Exact width = (3 buttons) + (2 spaces)
                center_grp_w = (inner_item_h * btn_count) + (btn_spacing * (btn_count - 1))

                available_space_start = left_section_w + padding_x
                available_space_end = right_start_x
                
                # Center math: Start Point + (Gap Size - Group Size) / 2
                center_x = available_space_start + ((available_space_end - available_space_start) - center_grp_w) / 2
                
                imgui.set_cursor_pos((center_x, content_y))
                # Pass spacing explicitly to ensure render matches calculation
                self._render_quick_actions(inner_item_h, btn_spacing)

                # --- D. BOTTOM: News Ticker ---
                text_height = imgui.get_text_line_height()
                ticker_text_y = top_h + (ticker_h - text_height) / 2
                
                imgui.set_cursor_pos((padding_x, ticker_text_y))
                self._render_ticker()

                # --- Popups ---
                self._render_country_selector_popup(state)

            except Exception as e:
                print(f"[CentralBar] Render Error: {e}")
            finally:
                imgui.end()
        else:
            imgui.end()
            
        imgui.pop_style_var() 
        return self.active_player_tag

    # --- SUB-COMPONENTS ---

    def _render_time_controls(self, state, net, width, height):
        imgui.begin_group()
        
        # Toggle Button
        if imgui.button("TIME", (50, height)):
            self.show_speed_controls = not self.show_speed_controls
        
        imgui.same_line()
        
        # LCD Screen
        screen_w = width - 50 - imgui.get_style().item_spacing.x
        
        p = imgui.get_cursor_screen_pos()
        draw_list = imgui.get_window_draw_list()
        
        draw_list.add_rect_filled(p, (p.x + screen_w, p.y + height), imgui.get_color_u32(GAMETHEME.col_black))
        draw_list.add_rect(p, (p.x + screen_w, p.y + height), imgui.get_color_u32(GAMETHEME.border))

        imgui.begin_child("TimeScreen", (screen_w, height), False, imgui.WindowFlags_.no_background)
        
        # Center content inside LCD
        content_h = 26 
        imgui.set_cursor_pos((10, (height - content_h) / 2))

        if self.show_speed_controls:
            self._draw_speed_buttons(state, net)
        else:
            self._draw_date_display(state)
            
        imgui.end_child()
        imgui.end_group()

    def _draw_speed_buttons(self, state, net):
        current_speed = getattr(state.time, "speed", 1)
        is_paused = getattr(state.time, "paused", False)
        btn_s = (26, 26) 
        
        imgui.push_style_var(imgui.StyleVar_.item_spacing, (2, 0))
        imgui.push_style_var(imgui.StyleVar_.frame_padding, (0, 0))

        # Pause
        if is_paused: 
            imgui.push_style_color(imgui.Col_.button, GAMETHEME.col_warning)
            imgui.push_style_color(imgui.Col_.text, GAMETHEME.col_black)
            
        if imgui.button(icons_fontawesome_6.ICON_FA_PAUSE, btn_s):
            net.send_action(ActionSetPaused("local", not is_paused))
            
        if is_paused: imgui.pop_style_color(2)

        imgui.same_line()

        # Speeds 1-5
        for i in range(1, 6):
            is_active = (current_speed == i and not is_paused)
            if is_active: 
                imgui.push_style_color(imgui.Col_.button, GAMETHEME.col_positive)
                imgui.push_style_color(imgui.Col_.text, GAMETHEME.col_black)

            if imgui.button(str(i), btn_s):
                net.send_action(ActionSetPaused("local", False))
                net.send_action(ActionSetGameSpeed("local", i))
            
            if is_active: imgui.pop_style_color(2)
            if i < 5: imgui.same_line()

        imgui.pop_style_var(2)

    def _draw_date_display(self, state):
        t = state.time
        parts = t.date_str.split(" ")
        date_part = parts[0] if len(parts) > 0 else "N/A"
        time_part = parts[1] if len(parts) > 1 else ""
        
        imgui.text_colored(GAMETHEME.col_positive, date_part)
        imgui.same_line()
        imgui.text_colored(GAMETHEME.col_text_bright, time_part)

    def _render_country_info(self, composer: UIComposer, height):
        imgui.begin_group()
        
        # 1. Flag
        flag_h = height
        flag_w = flag_h * 1.5
        
        flag_tex = self.flag_renderer.get_texture(self.active_player_tag)
        if flag_tex:
            composer.draw_image(flag_tex, flag_w, flag_h)
        else:
            composer.dummy((flag_w, flag_h))

        imgui.same_line()

        # 2. Text/Button Stack
        imgui.begin_group()
        gap = 2.0
        row_h = (height - gap) / 2
        
        if imgui.button(f" {self.active_player_tag} ", (90, row_h)):
            imgui.open_popup("CountrySelectorPopup")
        
        imgui.push_style_var(imgui.StyleVar_.item_spacing, (4, 0))
        self._draw_status_label("ALLIED", GAMETHEME.col_positive, row_h, width=50)
        imgui.same_line()
        self._draw_status_label("INFO", GAMETHEME.col_info, row_h, width=36)
        imgui.pop_style_var()
        
        imgui.end_group()
        imgui.end_group()

    def _render_quick_actions(self, height, spacing):
        """
        Renders the center icons. 
        Uses 'spacing' arg to match the calculation in render().
        """
        btn_sz = (height, height)
        
        imgui.push_style_var(imgui.StyleVar_.item_spacing, (spacing, 0))
        
        if imgui.button(f"{icons_fontawesome_6.ICON_FA_DESKTOP}", btn_sz): pass
        if imgui.is_item_hovered(): imgui.set_tooltip("Overview")
        
        imgui.same_line()
        if imgui.button(f"{icons_fontawesome_6.ICON_FA_CHART_LINE}", btn_sz): pass
        if imgui.is_item_hovered(): imgui.set_tooltip("Statistics")
        
        imgui.same_line()
        if imgui.button(f"{icons_fontawesome_6.ICON_FA_MESSAGE}", btn_sz): pass
        if imgui.is_item_hovered(): imgui.set_tooltip("Diplomacy")
        
        imgui.pop_style_var()

    def _render_ticker(self):
        imgui.align_text_to_frame_padding()
        imgui.text_colored(GAMETHEME.col_text_disabled, icons_fontawesome_6.ICON_FA_NEWSPAPER)
        imgui.same_line()
        imgui.text_colored(GAMETHEME.col_text_bright, self.news_ticker_text)

    def _render_country_selector_popup(self, state):
        if imgui.begin_popup("CountrySelectorPopup"):
            imgui.text_disabled("Switch Viewpoint")
            imgui.separator()
            if "countries" in state.tables:
                df = state.tables["countries"]
                if imgui.begin_child("CountryList", (200, 300)):
                    for row in df.head(50).iter_rows(named=True):
                        tag = row['id']
                        name = row.get('name', tag)
                        if imgui.selectable(f"{tag} - {name}", False)[0]:
                            self.active_player_tag = tag
                            imgui.close_current_popup()
                    imgui.end_child()
            imgui.end_popup()

    def _draw_status_label(self, label, color, height, width=40):
        imgui.push_style_color(imgui.Col_.button, color)
        imgui.push_style_color(imgui.Col_.text, GAMETHEME.col_black)
        imgui.button(label, (width, height))
        imgui.pop_style_color(2)