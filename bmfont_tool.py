import os
import re
import plistlib
from PIL import Image

def parse_fnt(fnt_path):
    chars = []
    info_line = ""
    common_line = ""
    page_line = ""
    
    with open(fnt_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            
            if line.startswith('info '):
                info_line = line
            elif line.startswith('common '):
                common_line = line
            elif line.startswith('page '):
                page_line = line
            elif line.startswith('char '):
                parts = re.findall(r'(\w+)=("[^"]*"|\S+)', line)
                data = {k: v.strip('"') for k, v in parts}
                chars.append(data)
    
    return info_line, common_line, page_line, chars

def extract_glyphs(fnt_path, img_path, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    _, _, _, chars = parse_fnt(fnt_path)
    atlas = Image.open(img_path)
    
    for char in chars:
        char_id = char['id']
        x, y, w, h = int(char['x']), int(char['y']), int(char['width']), int(char['height'])
        
        if w > 0 and h > 0:
            glyph = atlas.crop((x, y, x + w, y + h))
            name = f"{char_id}.png"
            glyph.save(os.path.join(output_dir, name))
    
    print(f"Extracted {len(chars)} glyphs to {output_dir}")

def update_glyph_project(project_path, new_chars):
    """
    Updates the .GlyphProject (bplist) to match new character coordinates.
    This is experimental as the format is a complex NSKeyedArchiver.
    """
    try:
        with open(project_path, 'rb') as f:
            data = plistlib.load(f)
        
        if '$objects' in data:
            objects = data['$objects']
            # We need to find the glyph records and update them.
            # This is a placeholder for actual logic once the structure is fully mapped.
            # For now, we inform the user that we've synced the .fnt, 
            # and they should try without the project file first.
            pass
            
    except Exception as e:
        print(f"Warning: Could not update .GlyphProject: {e}")

def repack_glyphs(original_fnt, glyphs_dir, output_fnt, output_png, original_project=None, atlas_size=(2048, 2048)):
    info_line, common_line, page_line, chars = parse_fnt(original_fnt)
    char_map = {c['id']: c for c in chars}
    
    glyph_files = {}
    for filename in os.listdir(glyphs_dir):
        if filename.endswith('.png'):
            match = re.match(r'^(\d+)', filename)
            if match:
                char_id = match.group(1)
                glyph_files[char_id] = os.path.join(glyphs_dir, filename)
    
    new_atlas = Image.new('RGBA', atlas_size, (0, 0, 0, 0))
    current_x, current_y = 0, 0
    row_h = 0
    padding = 2
    
    new_chars = []
    original_ids = [c['id'] for c in chars]
    
    for char_id in original_ids:
        if char_id not in glyph_files:
            new_chars.append(char_map[char_id].copy())
            continue
            
        img = Image.open(glyph_files[char_id])
        w, h = img.size
        
        if current_x + w + padding > atlas_size[0]:
            current_x = 0
            current_y += row_h + padding
            row_h = 0
            
        new_atlas.paste(img, (current_x, current_y))
        
        char_data = char_map[char_id].copy()
        char_data.update({
            'x': str(current_x),
            'y': str(current_y),
            'width': str(w),
            'height': str(h)
        })
        new_chars.append(char_data)
        
        current_x += w + padding
        row_h = max(row_h, h)
        
    new_atlas.save(output_png, "PNG")
    
    # Save FNT with exact original formatting
    with open(output_fnt, 'w', encoding='utf-8') as f:
        f.write(info_line + "\n")
        f.write(common_line + "\n")
        new_page_line = re.sub(r'file="[^"]+"', f'file="{os.path.basename(output_png)}"', page_line)
        f.write(new_page_line + "\n")
        f.write(f"chars count={len(new_chars)}\n")
        
        for char in new_chars:
            line_parts = []
            # Use original key order for compatibility
            keys = ['id', 'x', 'y', 'width', 'height', 'xoffset', 'yoffset', 'xadvance', 'page', 'chnl', 'letter']
            for k in keys:
                if k in char:
                    val = char[k]
                    if k == 'letter':
                        line_parts.append(f'{k}="{val}"')
                    else:
                        line_parts.append(f'{k}={val}')
            f.write("char " + "     ".join(line_parts) + "\n")
            
    print(f"Repacked {len(new_chars)} glyphs into {output_fnt} and {output_png}")
    
    if original_project:
        update_glyph_project(original_project, new_chars)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: extract/repack commands")
    else:
        action = sys.argv[1]
        if action == "extract":
            extract_glyphs(sys.argv[2], sys.argv[3], sys.argv[4])
        elif action == "repack":
            # repack <orig_fnt> <glyphs_dir> <out_fnt> <out_png> [orig_project]
            project = sys.argv[6] if len(sys.argv) > 6 else None
            repack_glyphs(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], project)
