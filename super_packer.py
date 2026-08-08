import os
import sys
import plistlib
import math
import zlib
import struct
import random
import string
from PIL import Image

# --- ЛОГИКА ОБРЕЗКИ (TRIMMING) ---
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

# --- ЛОГИКА УПАКОВКИ (MAXRECTS) ---
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

# --- ЛОГИКА ЗАЩИТЫ (CCZ & JUNK) ---
def to_ccz(image, output_path):
    import io
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    data = img_byte_arr.getvalue()
    compressed = zlib.compress(data)
    header = struct.pack(">4sHHII", b"CCZ!", 0, 1, 0, len(data))
    with open(output_path, 'wb') as f:
        f.write(header + compressed)

def add_junk_frames(frames):
    for _ in range(500):
        junk_name = ''.join(random.choices(string.ascii_letters + string.digits, k=12)) + ".png"
        frames[junk_name] = {
            'aliases': [],
            'spriteOffset': f"{{{random.randint(-50,50)},{random.randint(-50,50)}}}",
            'spriteSize': "{1,1}",
            'spriteSourceSize': "{1,1}",
            'textureRect': f"{{{{{random.randint(0,100)},{random.randint(0,100)}}},{{1,1}}}}",
            'textureRotated': False
        }

# --- ОСНОВНАЯ ФУНКЦИЯ ---
def super_pack(folder_path, target_base_name):
    print(f"[*] Начало сборки атласа для: {target_base_name}")
    images = []
    for f in sorted(os.listdir(folder_path)):
        if f.lower().endswith('.png'):
            img = Image.open(os.path.join(folder_path, f)).convert('RGBA')
            trimmed, rect, offset = trim(img)
            images.append({
                'name': f,
                'orig_size': img.size,
                'trimmed_img': trimmed,
                'size': trimmed.size,
                'offset': offset
            })
    
    if not images:
        print("[-] Ошибка: В папке нет PNG файлов.")
        return

    images.sort(key=lambda x: x['size'][1], reverse=True)
    total_area = sum(img['size'][0] * img['size'][1] for img in images)
    side = int(math.sqrt(total_area * 1.3))
    side = max(side, max(img['size'][0] for img in images), max(img['size'][1] for img in images))
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
    
    # ПРИМЕНЯЕМ ЗАЩИТУ
    target_png_name = target_base_name + ".pvr.ccz"
    add_junk_frames(frames)
    
    # Сохраняем CCZ
    to_ccz(atlas, target_base_name + ".pvr.ccz")
    
    # Сохраняем PLIST с правильными внутренними ссылками
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
    
    with open(target_base_name + ".plist", 'wb') as f:
        plistlib.dump(plist_data, f)
    
    print(f"[+] Готово! Созданы файлы:")
    print(f"    - {target_base_name}.plist")
    print(f"    - {target_base_name}.pvr.ccz")
    print("[!] Просто скопируйте их в папку с игрой.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Использование: python super_packer.py <папка_со_спрайтами> <целевое_имя>")
        print("Пример: python super_packer.py mainmenu_assets_unpacked mainmenu_assets")
    else:
        super_pack(sys.argv[1], sys.argv[2])
