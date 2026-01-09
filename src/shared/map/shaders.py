# shaders.py

VERTEX_SHADER = """
#version 330
in vec2 in_vert;
in vec2 in_uv;
out vec2 v_uv;

void main() {
    v_uv = in_uv;
    // Map -1..1 coordinates to full screen quad
    gl_Position = vec4(in_vert, 0.0, 1.0);
}
"""

FRAGMENT_SHADER = """
#version 330

in vec2 v_uv;
out vec4 f_color;

// --- UNIFORMS ---
uniform sampler2D u_map_texture;    // The raw Region Map (regions.png)
uniform sampler2D u_lookup_texture; // The 1D State Data (Pixel 0 = Region 0 Color)
uniform vec2      u_texture_size;   // Size of map in pixels (e.g., 4096.0, 2048.0)
uniform int       u_hover_id;       // Currently hovered region ID
uniform int       u_selected_id;    // Currently selected region ID

// --- CONSTANTS ---
// Must match Python LUT width
const float MAX_REGIONS = 8192.0; 

// --- HELPER: Decode Color to ID ---
// Python packing: B | (G << 8) | (R << 16)
// GLSL Texture: R, G, B channels are 0.0 to 1.0
int get_id(vec2 uv) {
    vec4 c = texture(u_map_texture, uv);
    
    // Convert 0.0-1.0 to 0-255 integers
    int r = int(round(c.r * 255.0));
    int g = int(round(c.g * 255.0));
    int b = int(round(c.b * 255.0));
    
    // Reassemble ID based on your specific packing (Blue is LSB)
    return b + (g << 8) + (r << 16);
}

void main() {
    // 1. Get the Region ID at this specific pixel
    int region_id = get_id(v_uv);

    // 2. Discard water (Assuming ID 0 is water/void)
    if (region_id == 0) {
        // Output transparent or water color
        f_color = vec4(0.1, 0.1, 0.25, 1.0); 
        return;
    }

    // 3. Fetch Owner Color from the Lookup Texture (LUT)
    // Map the Integer ID to a UV coordinate (0.0 to 1.0) along the 1D texture
    float lut_u = (float(region_id) + 0.5) / MAX_REGIONS;
    
    // We read from the middle of the pixel row (v=0.5)
    vec4 country_color = texture(u_lookup_texture, vec2(lut_u, 0.5));

    // 4. Border Detection (Edge Detection)
    // Check pixel to the Right and pixel Below.
    vec2 step = 1.0 / u_texture_size;
    
    int id_right = get_id(v_uv + vec2(step.x, 0.0));
    int id_down  = get_id(v_uv + vec2(0.0, step.y));
    
    // If neighbor is different, we are on a border
    bool is_border = (region_id != id_right) || (region_id != id_down);

    // 5. Visual Effects (Selection/Hover)
    vec3 final_rgb = country_color.rgb;
    
    if (region_id == u_selected_id) {
        final_rgb += 0.2; // Brighten selected
    } else if (region_id == u_hover_id) {
        final_rgb += 0.1; // Slightly brighten hover
    }

    // Apply Border
    if (is_border) {
        // Black border with 50% opacity blend or solid black
        final_rgb = mix(final_rgb, vec3(0.0), 0.7); 
    }

    f_color = vec4(final_rgb, 1.0);
}
"""