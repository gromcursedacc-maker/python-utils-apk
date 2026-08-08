import os
import sys
import plistlib
from PIL import Image, ImageDraw

def parse_plist_coords(s):
    """Converts '{x,y}' or '{{x,y},{w,h}}' to list of floats."""
    return [float(x) for x in s.replace('{', '').replace('}', '').split(',')]

def unpack(plist_path):
    if not plist_path.endswith('.plist'):
        plist_path += '.plist'
    
    png_path = plist_path.replace('.plist', '.png')
    output_dir = plist_path.replace('.plist', '_unpacked')
    
    if not os.path.exists(plist_path) or not os.path.exists(png_path):
        print(f"Error: {plist_path} or {png_path} not found.")
        return

    with open(plist_path, 'rb') as f:
        plist_data = plistlib.load(f)
    
    atlas = Image.open(png_path).convert('RGBA')
    frames = plist_data['frames']
    
    os.makedirs(output_dir, exist_ok=True)
    
    for name, data in frames.items():
        print(f"Unpacking {name}...")
        
        # Basic rect info
        rect = parse_plist_coords(data['textureRect'])
        rotated = data.get('textureRotated', False)
        source_size = parse_plist_coords(data['spriteSourceSize'])
        offset = parse_plist_coords(data.get('spriteOffset', '{0,0}'))
        
        x, y, w, h = rect
        if rotated:
            w, h = h, w
        
        # Crop the raw rectangle
        crop_box = (int(x), int(y), int(x + w), int(y + h))
        sprite = atlas.crop(crop_box)
        
        # Handle Polygon Masking if verticesUV exist
        if 'verticesUV' in data:
            uv_list = [float(v) for v in data['verticesUV'].split()]
            # verticesUV are absolute in atlas. Convert to relative to crop_box.
            rel_uv = []
            for i in range(0, len(uv_list), 2):
                rel_uv.append((uv_list[i] - x, uv_list[i+1] - y))
            
            # Create mask
            mask = Image.new('L', sprite.size, 0)
            draw = ImageDraw.Draw(mask)
            draw.polygon(rel_uv, fill=255)
            
            # Apply mask
            new_sprite = Image.new('RGBA', sprite.size, (0, 0, 0, 0))
            new_sprite.paste(sprite, (0, 0), mask=mask)
            sprite = new_sprite

        if rotated:
            sprite = sprite.rotate(90, expand=True)
        
        # Restore to full source size with offset
        # Cocos2d offset: (0,0) is center. 
        # offset_x = (source_w - sprite_w) / 2 + offset_x
        # but usually it's easier to just use the spriteSourceSize and center it.
        full_w, full_h = int(source_size[0]), int(source_size[1])
        result = Image.new('RGBA', (full_w, full_h), (0, 0, 0, 0))
        
        curr_w, curr_h = sprite.size
        # Paste based on offset
        # Cocos2d-x logic: center of spriteSourceSize is (0,0)
        paste_x = int((full_w - curr_w) / 2 + offset[0])
        paste_y = int((full_h - curr_h) / 2 - offset[1])
        
        result.paste(sprite, (paste_x, paste_y))
        
        # Save
        save_path = os.path.join(output_dir, name)
        if not save_path.lower().endswith('.png'):
            save_path += '.png'
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        result.save(save_path)

    print(f"Done! Unpacked to {output_dir}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python improved_unpacker.py <path_to_plist>")
    else:
        unpack(sys.argv[1])
