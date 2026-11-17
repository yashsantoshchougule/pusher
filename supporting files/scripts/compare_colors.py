from PIL import Image

def analyze_image(path, name):
    im = Image.open(path)
    w, h = im.size
    print(f"\n--- {name} ({w}x{h}) ---")
    
    # Sample points:
    # 1. Canvas outer background
    p_canvas = im.getpixel((20, 20))
    # 2. Main card background (around form or beside image)
    p_card = im.getpixel((int(w * 0.8), int(h * 0.2)))
    # 3. Input field background
    p_input = im.getpixel((int(w * 0.6), int(h * 0.33)))
    # 4. Create account button background
    p_btn = im.getpixel((int(w * 0.65), int(h * 0.58)))
    # 5. Tab bar active
    p_tab = im.getpixel((int(w * 0.7), int(h * 0.19)))

    print(f"Canvas: #{p_canvas[0]:02x}{p_canvas[1]:02x}{p_canvas[2]:02x}")
    print(f"Card/Form bg: #{p_card[0]:02x}{p_card[1]:02x}{p_card[2]:02x}")
    print(f"Input bg: #{p_input[0]:02x}{p_input[1]:02x}{p_input[2]:02x}")
    print(f"Button bg: #{p_btn[0]:02x}{p_btn[1]:02x}{p_btn[2]:02x}")
    print(f"Active Tab bg: #{p_tab[0]:02x}{p_tab[1]:02x}{p_tab[2]:02x}")

base = r'C:\Users\Yash chougule\.gemini\antigravity\brain\5eb00978-652c-460d-ac2a-f0798cfc1e1d\.user_uploaded'
analyze_image(f"{base}\\media_1794888787427_46724f66.jpg", "Image 1 (media_1794888787427)")
analyze_image(f"{base}\\media_1794888806351_a5d876b9.jpg", "Image 2 (media_1794888806351)")
analyze_image(f"{base}\\media_1794890342556_38383f6a.png", "Image 3 (media_1794890342556)")
analyze_image(f"{base}\\media_1794899003927_f39c17d3.jpg", "Current Upload (media_1794899003927)")
