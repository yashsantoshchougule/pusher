from PIL import Image
import os

files = [
    'media_1794888787427_46724f66.jpg',
    'media_1794888806351_a5d876b9.jpg',
    'media_1794890342556_38383f6a.png',
    'media_1794899003927_f39c17d3.jpg'
]

base_dir = r'C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\.user_uploaded'

for f in files:
    p = os.path.join(base_dir, f)
    if os.path.exists(p):
        im = Image.open(p)
        print(f"File: {f}, Size: {im.size}, Mode: {im.mode}")
