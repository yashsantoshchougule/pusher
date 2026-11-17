import sys
from PIL import Image

def analyze(path):
    im = Image.open(path)
    w, h = im.size
    print(f"File: {path} ({w}x{h})")
    # background sample
    bg = im.getpixel((30, 30 if h < 600 else 150))
    # card sample
    card = im.getpixel((int(w * 0.7), int(h * 0.2 if h < 600 else h * 0.25)))
    # input box
    input_box = im.getpixel((int(w * 0.7), int(h * 0.35 if h < 600 else h * 0.4)))
    # button
    btn = im.getpixel((int(w * 0.7), int(h * 0.61 if h < 600 else h * 0.62)))
    print(f"  Background: #{bg[0]:02x}{bg[1]:02x}{bg[2]:02x} {bg}")
    print(f"  Card: #{card[0]:02x}{card[1]:02x}{card[2]:02x} {card}")
    print(f"  Input: #{input_box[0]:02x}{input_box[1]:02x}{input_box[2]:02x} {input_box}")
    print(f"  Btn: #{btn[0]:02x}{btn[1]:02x}{btn[2]:02x} {btn}")

analyze(r"C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\.user_uploaded\media_1794888787427_46724f66.jpg")
analyze(r"C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\.user_uploaded\media_1794888806351_a5d876b9.jpg")
