from rembg import remove, new_session
from PIL import Image
from pathlib import Path
from tqdm import tqdm
import sys
import numpy as np
from scipy import ndimage as ndi


def is_image_file(p: Path):
    return p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def refine_alpha_with_enclosed_bg(img: Image.Image, rgba: np.ndarray, bright_thresh=240, std_thresh=20, alpha_smooth_sigma=1.0):
    """
    - img: original PIL Image (RGB or L)
    - rgba: numpy array HxWx4 (uint8)
    Returns modified rgba with enclosed white-ish background blobs removed (alpha=0) and smoothed alpha.
    """
    h, w = rgba.shape[:2]
    alpha = rgba[:, :, 3].astype(np.uint8)

    fg_mask = alpha > 127
    bg_mask = ~fg_mask

    labels, n = ndi.label(bg_mask)

    gray = np.array(img.convert('L'))

    for lab in range(1, n + 1):
        comp = labels == lab
        if not comp.any():
            continue

        # does component touch border?
        rows, cols = np.where(comp)
        if (rows == 0).any() or (rows == h - 1).any() or (cols == 0).any() or (cols == w - 1).any():
            # connected to border -> keep as background
            continue

        # enclosed component: check brightness and variance
        vals = gray[comp]
        mean = float(vals.mean()) if vals.size > 0 else 0.0
        std = float(vals.std()) if vals.size > 0 else 0.0

        # if area looks like background (very bright and low variance), remove it
        if mean >= bright_thresh and std <= std_thresh:
            alpha[comp] = 0

    # smooth alpha a bit to remove hard edges after changes
    alpha_f = alpha.astype(np.float32) / 255.0
    if alpha_smooth_sigma > 0:
        alpha_f = ndi.gaussian_filter(alpha_f, sigma=alpha_smooth_sigma)
    alpha = np.clip((alpha_f * 255.0).round(), 0, 255).astype(np.uint8)

    rgba[:, :, 3] = alpha
    return rgba


def process_folder(input_root: Path, out_suffix="_v2_ready"):
    out_root = input_root.parent / f"{input_root.name}{out_suffix}"
    out_root.mkdir(exist_ok=True)

    print(f"Creating rembg session (model will be downloaded on first run if needed)...")
    session = new_session()

    files = [p for p in input_root.rglob('*') if p.is_file() and is_image_file(p)]
    if not files:
        print("No image files found in", input_root)
        return

    for src in tqdm(files, desc="Processing files v2"):
        try:
            rel = src.relative_to(input_root)
            dest_dir = out_root / rel.parent
            dest_dir.mkdir(parents=True, exist_ok=True)

            img = Image.open(src).convert("RGBA")
            result = remove(img, session=session)

            if not hasattr(result, 'save'):
                # bytes -> load into PIL
                from io import BytesIO

                result = Image.open(BytesIO(result)).convert('RGBA')

            rgba = np.array(result)

            rgba = refine_alpha_with_enclosed_bg(img.convert('RGB'), rgba,
                                                bright_thresh=240, std_thresh=20, alpha_smooth_sigma=1.0)

            out_path = dest_dir / (src.stem + ".png")
            Image.fromarray(rgba).save(out_path)
        except Exception as e:
            print("Error processing:", src, e)

    print("Done. Output written to:", out_root)


def main():
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
    else:
        input_str = input("Enter path to folder to process (v2): ").strip()
        input_path = Path(input_str)

    if not input_path.exists() or not input_path.is_dir():
        print("Provided path does not exist or is not a folder:", input_path)
        return

    process_folder(input_path.resolve())


if __name__ == "__main__":
    main()
