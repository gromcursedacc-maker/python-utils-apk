import os
import sys
import plistlib
import math
import zlib
import struct
import random
import string
import re
from PIL import Image, ImageDraw

# --- SHARED UTILS ---
def parse_plist_coords(s):
    return [float(x) for x in s.replace('{', '').replace('}', '').split(',')]

# --- PACKER LOGIC ---
def trim(img):
    bbox = img.getbbox()
    if not bbox:
        return img, (0, 0, img.width, img.height), (0, 0)
    trimmed_img = img.crop(bbox)
    orig_w, orig_h = img.size
    trim_w, trim_h = trimmed_img.size
    left, top, right, bottom = bbox
    offset_x = (left + right - orig_w) / 2.0
    offset_y = (orig_h - (top + bottom)) / 2.0
    return trimmed_img, (0, 0, trim_w, trim_h), (offset_x, offset_y)

class MaxRectsPacker:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.free_rects = [(0, 0, width, height)]

    def insert(self, w, h):
        best_rect = None
        best_score = float('inf')
        for i, (fx, fy, fw, fh) in enumerate(self.free_rects):
            if fw >= w and fh >= h:
                score = fw * fh - w * h
                if score < best_score:
                    best_score = score
                    best_rect = (fx, fy, w, h)
        if best_rect:
            self._split(best_rect)
            return best_rect
        return None

    def _split(self, used):
        ux, uy, uw, uh = used
        new_free = []
        for fx, fy, fw, fh in self.free_rects:
            if ux >= fx + fw or ux + uw <= fx or uy >= fy + fh or uy + uh <= fy:
                new_free.append((fx, fy, fw, fh))
                continue
            if ux > fx: new_free.append((fx, fy, ux - fx, fh))
            if ux + uw < fx + fw: new_free.append((ux + uw, fy, fx + fw - (ux + uw), fh))
            if uy > fy: new_free.append((fx, fy, fw, uy - fy))
            if uy + uh < fy + fh: new_free.append((fx, uy + uh, fw, fy + fh - (uy + uh)))
        self.free_rects = []
        for i, r1 in enumerate(new_free):
            is_contained = False
            for j, r2 in enumerate(new_free):
                if i != j and r1[0] >= r2[0] and r1[1] >= r2[1] and \
                   r1[0]+r1[2] <= r2[0]+r2[2] and r1[1]+r1[3] <= r2[1]+r2[3]:
                    is_contained = True
                    break
            if not is_contained:
                self.free_rects.append(r1)

def to_ccz(image, output_path):
    import io
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    data = img_byte_arr.getvalue()
    compressed = zlib.compress(data)
    header = struct.pack(">4sHHII", b"CCZ!", 0, 1, 0, len(data))
    with open(output_path, 'wb') as f:
        f.write(header + compressed)

def super_pack(folder_path, target_base_name, logger=print):
    logger(f"[*] Сборка атласа: {target_base_name}")
    if not os.path.exists(folder_path):
        logger(f"[-] Ошибка: Путь {folder_path} не существует")
        return
    
    images = []
    for f in sorted(os.listdir(folder_path)):
        if f.lower().endswith('.png'):
            img = Image.open(os.path.join(folder_path, f)).convert('RGBA')
            trimmed, rect, offset = trim(img)
            images.append({'name': f, 'orig_size': img.size, 'trimmed_img': trimmed, 'size': trimmed.size, 'offset': offset})
    
    if not images:
        logger("[-] Ошибка: PNG файлы не найдены")
        return

    images.sort(key=lambda x: x['size'][1], reverse=True)
    total_area = sum(img['size'][0] * img['size'][1] for img in images)
    side = max(int(math.sqrt(total_area * 1.3)), max(img['size'][0] for img in images), max(img['size'][1] for img in images))
    side = 2**(int(math.log2(side-1))+1) if side > 0 else 2
    
    while True:
        packer = MaxRectsPacker(side, side)
        results = []
        success = True
        for img in images:
            placed = packer.insert(img['size'][0], img['size'][1])
            if not placed:
                success = False
                break
            results.append({'img': img, 'rect': placed})
        if success: break
        side *= 2

    atlas = Image.new('RGBA', (side, side), (0, 0, 0, 0))
    frames = {}
    for res in results:
        img_data = res['img']
        x, y, w, h = res['rect']
        atlas.paste(img_data['trimmed_img'], (x, y))
        frames[img_data['name']] = {
            'aliases': [],
            'spriteOffset': f"{{{img_data['offset'][0]},{img_data['offset'][1]}}}",
            'spriteSize': f"{{{w},{h}}}",
            'spriteSourceSize': f"{{{img_data['orig_size'][0]},{img_data['orig_size'][1]}}}",
            'textureRect': f"{{{{{x},{y}}},{{{w},{h}}}}}",
            'textureRotated': False
        }
    
    target_png_name = target_base_name + ".pvr.ccz"
    to_ccz(atlas, os.path.join(os.path.dirname(folder_path), target_png_name))
    
    plist_data = {
        'frames': frames,
        'metadata': {
            'format': 3,
            'pixelFormat': 'RGBA8888',
            'realTextureFileName': target_png_name,
            'size': f"{{{side},{side}}}",
            'smartupdate': "$TexturePacker:SmartUpdate:" + ''.join(random.choices(string.hexdigits, k=32)),
            'textureFileName': target_png_name
        }
    }
    
    with open(os.path.join(os.path.dirname(folder_path), target_base_name + ".plist"), 'wb') as f:
        plistlib.dump(plist_data, f)
    
    logger(f"[+] Готово: {target_base_name}.plist и .pvr.ccz")

# --- UNPACKER LOGIC ---
def unpack(plist_path, logger=print):
    if not plist_path.endswith('.plist'): plist_path += '.plist'
    png_path = plist_path.replace('.plist', '.png')
    if not os.path.exists(png_path):
        png_path = plist_path.replace('.plist', '.pvr.ccz') # Try CCZ if PNG not found
        # Note: In a real app, we'd need a CCZ decoder here, 
        # but for simplicity let's assume standard PNG or already handled CCZ
    
    output_dir = plist_path.replace('.plist', '_unpacked')
    if not os.path.exists(plist_path):
        logger(f"[-] Ошибка: {plist_path} не найден")
        return

    with open(plist_path, 'rb') as f:
        plist_data = plistlib.load(f)
    
    # Check if we can open the texture
    try:
        atlas = Image.open(png_path).convert('RGBA')
    except:
        logger(f"[-] Ошибка: Не удалось открыть текстуру {png_path}")
        return

    frames = plist_data['frames']
    os.makedirs(output_dir, exist_ok=True)
    
    for name, data in frames.items():
        logger(f"Распаковка {name}...")
        rect = parse_plist_coords(data['textureRect'])
        rotated = data.get('textureRotated', False)
        source_size = parse_plist_coords(data['spriteSourceSize'])
        offset = parse_plist_coords(data.get('spriteOffset', '{0,0}'))
        
        x, y, w, h = rect
        if rotated: w, h = h, w
        
        sprite = atlas.crop((int(x), int(y), int(x + w), int(y + h)))
        if rotated: sprite = sprite.rotate(90, expand=True)
        
        full_w, full_h = int(source_size[0]), int(source_size[1])
        result = Image.new('RGBA', (full_w, full_h), (0, 0, 0, 0))
        paste_x = int((full_w - sprite.size[0]) / 2 + offset[0])
        paste_y = int((full_h - sprite.size[1]) / 2 - offset[1])
        result.paste(sprite, (paste_x, paste_y))
        
        save_path = os.path.join(output_dir, name if name.lower().endswith('.png') else name + '.png')
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        result.save(save_path)

    logger(f"[+] Готово! Распаковано в {output_dir}")

# --- BMFONT LOGIC ---
def parse_fnt(fnt_path):
    chars = []
    info, common, page = "", "", ""
    with open(fnt_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            if line.startswith('info '): info = line
            elif line.startswith('common '): common = line
            elif line.startswith('page '): page = line
            elif line.startswith('char '):
                parts = re.findall(r'(\w+)=("[^"]*"|\S+)', line)
                chars.append({k: v.strip('"') for k, v in parts})
    return info, common, page, chars

def extract_glyphs(fnt_path, img_path, output_dir, logger=print):
    if not os.path.exists(fnt_path) or not os.path.exists(img_path):
        logger("[-] Ошибка: Файлы не найдены")
        return
    os.makedirs(output_dir, exist_ok=True)
    _, _, _, chars = parse_fnt(fnt_path)
    atlas = Image.open(img_path)
    for char in chars:
        char_id = char['id']
        x, y, w, h = int(char['x']), int(char['y']), int(char['width']), int(char['height'])
        if w > 0 and h > 0:
            glyph = atlas.crop((x, y, x + w, y + h))
            glyph.save(os.path.join(output_dir, f"{char_id}.png"))
    logger(f"[+] Извлечено {len(chars)} глифов в {output_dir}")
