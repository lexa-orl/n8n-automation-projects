from PIL import Image
from pathlib import Path

p = Path('test_run/input_dir/nested')
p.mkdir(parents=True, exist_ok=True)
img = Image.new('RGB', (200, 200), color=(255, 255, 255))
for x in range(50, 150):
    for y in range(80, 140):
        img.putpixel((x, y), (30, 30, 30))
img.save(p / 'shoe.jpg', quality=90)
print('Created test image at', (p / 'shoe.jpg').resolve())
