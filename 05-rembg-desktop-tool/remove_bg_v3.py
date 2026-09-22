"""
remove_bg_v3.py

Pipeline v3 (quality-first):
- Uses rembg for initial segmentation (session reuse).
- Generates adaptive trimap (erode/dilate) and saves it under annotations/ preserving folder structure.
- Saves rembg RGBA result to <input>_v3_ready preserving tree.
- CLI options let you tune trimap radii and max resize side.

Notes:
- This version focuses on high-quality masks + producing trimaps and annotations for later high-quality matting (ONNX/GCA).
- If you place an ONNX matting model and we implement a specific matting runner later, the trimaps produced here will be used.
"""

from rembg import remove, new_session
from PIL import Image
from pathlib import Path
from tqdm import tqdm
import numpy as np
import argparse
import cv2
import sys
import onnxruntime as ort
import os


def is_image_file(p: Path):
    return p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def generate_trimap(alpha_channel: np.ndarray, erode_radius: int, dilate_radius: int):
    # alpha_channel: 0-255
    # produce trimap: 0 background, 128 unknown, 255 foreground
    fg = (alpha_channel > 200).astype(np.uint8) * 255
    bg = (alpha_channel < 50).astype(np.uint8) * 255

    kernel_e = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (erode_radius * 2 + 1, erode_radius * 2 + 1))
    kernel_d = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_radius * 2 + 1, dilate_radius * 2 + 1))

    sure_fg = cv2.erode(fg, kernel_e, iterations=1)
    sure_bg = cv2.dilate(bg, kernel_d, iterations=1)

    trimap = np.full_like(alpha_channel, 128, dtype=np.uint8)
    trimap[sure_bg == 255] = 0
    trimap[sure_fg == 255] = 255
    return trimap


def process_folder(input_root: Path, out_suffix: str = "_v3_ready", erode: int = 5, dilate: int = 5, max_side: int = 0):
    out_root = input_root.parent / f"{input_root.name}{out_suffix}"
    ann_root = input_root.parent / (input_root.name + "_annotations")
    out_root.mkdir(exist_ok=True)
    ann_root.mkdir(exist_ok=True)

    model_name = os.environ.get('REMBG_MODEL', 'u2net')
    print('Loading rembg model:', model_name)
    session = new_session(model_name)
    matting_session = None
    matting_model_path = os.environ.get('REM_MATTING_ONNX')
    if matting_model_path:
        try:
            matting_session = ort.InferenceSession(matting_model_path, providers=['CUDAExecutionProvider','CPUExecutionProvider'])
            print('Loaded matting ONNX model:', matting_model_path)
        except Exception as e:
            print('Could not load matting model from REM_MATTING_ONNX:', e)

    files = [p for p in input_root.rglob("*") if p.is_file() and is_image_file(p)]
    if not files:
        print("No image files found in", input_root)
        return

    for src in tqdm(files, desc="Processing v3"):
        try:
            rel = src.relative_to(input_root)
            dest_dir = out_root / rel.parent
            dest_dir.mkdir(parents=True, exist_ok=True)
            ann_dir = ann_root / rel.parent
            ann_dir.mkdir(parents=True, exist_ok=True)

            img = Image.open(src).convert("RGBA")
            w, h = img.size

            # optional resize for very large images
            if max_side > 0 and max(w, h) > max_side:
                scale = max_side / max(w, h)
                new_size = (int(w * scale), int(h * scale))
                img_small = img.resize(new_size, Image.LANCZOS)
                result_small = remove(img_small, session=session)
                # resize alpha back to original size
                if hasattr(result_small, 'save'):
                    alpha_small = np.array(result_small.split()[-1])
                    alpha = cv2.resize(alpha_small, (w, h), interpolation=cv2.INTER_LINEAR)
                    rgba = np.array(img)
                    rgba[:, :, 3] = alpha
                    result = Image.fromarray(rgba)
                else:
                    result = result_small
            else:
                result = remove(img, session=session)

            out_path = dest_dir / (src.stem + ".png")
            if hasattr(result, 'save'):
                result.save(out_path)
                alpha = np.array(result.split()[-1])
            else:
                # bytes
                from io import BytesIO

                result = Image.open(BytesIO(result)).convert('RGBA')
                result.save(out_path)
                alpha = np.array(result.split()[-1])

            # generate and save trimap
            trimap = generate_trimap(alpha, erode, dilate)
            trimap_path = ann_dir / (src.stem + "_trimap.png")
            Image.fromarray(trimap).save(trimap_path)

            # also save automatic mask (binary) for convenience
            mask = (alpha > 127).astype(np.uint8) * 255
            mask_path = ann_dir / (src.stem + "_mask.png")
            Image.fromarray(mask).save(mask_path)

            # If matting model present, try to run it and overwrite alpha
            if matting_session is not None:
                try:
                    new_alpha = run_onnx_matting(matting_session, np.array(img.convert('RGB')), trimap)
                    if new_alpha is not None:
                        rgba = np.array(Image.open(out_path).convert('RGBA'))
                        rgba[:, :, 3] = new_alpha
                        Image.fromarray(rgba).save(out_path)
                        # save matting alpha
                        Image.fromarray(new_alpha).save(ann_dir / (src.stem + '_matting_alpha.png'))
                except Exception as e:
                    print('Matting failed for', src, e)

        except Exception as e:
            print("Error processing:", src, e)

    print("Done. Output written to:", out_root)


def cli():
    p = argparse.ArgumentParser()
    p.add_argument('--input', '-i', required=True, help='Input folder')
    p.add_argument('--out-suffix', default='_v3_ready')
    p.add_argument('--erode', type=int, default=5)
    p.add_argument('--dilate', type=int, default=5)
    p.add_argument('--max-side', type=int, default=0, help='Resize longest side to this for faster processing (0 = keep size)')
    p.add_argument('--matting', '-m', help='Path to ONNX matting model to run on generated trimaps')
    args = p.parse_args()

    input_path = Path(args.input)
    if not input_path.exists() or not input_path.is_dir():
        print('Input must be a folder')
        sys.exit(1)

    # allow matting model path via env var or CLI
    if args.matting:
        os.environ['REM_MATTING_ONNX'] = args.matting
    process_folder(input_path.resolve(), out_suffix=args.out_suffix, erode=args.erode, dilate=args.dilate, max_side=args.max_side)


def run_onnx_matting(session: ort.InferenceSession, img_rgb: np.ndarray, trimap: np.ndarray):
    """
    Generic ONNX matting runner.
    Attempts to map inputs: if model expects image and trimap, we pass them.
    Returns alpha uint8 HxW or None on failure.
    """
    # preprocess: try common shapes
    h, w = trimap.shape[:2]

    # Normalize image to float32 [1,3,H,W]
    img = img_rgb.astype(np.float32)
    # try both 0-255 and 0-1
    img_0_1 = (img / 255.0).astype(np.float32)

    input_names = [i.name for i in session.get_inputs()]
    output_names = [o.name for o in session.get_outputs()]

    feeds = {}
    try_orders = []
    # Heuristic: if model has 'trimap' or 'tmap' input, use trimap
    trimap_input = None
    for n in input_names:
        ln = n.lower()
        if 'trimap' in ln or 'tmap' in ln:
            trimap_input = n
            break
    # Determine image input
    img_input = None
    for n in input_names:
        ln = n.lower()
        if 'img' in ln or 'image' in ln or 'src' in ln or 'input' in ln:
            img_input = n
            break

    # Build feed dict
    if img_input:
        feeds[img_input] = img_0_1.transpose(2, 0, 1)[None, :].astype(np.float32)
    if trimap_input:
        feeds[trimap_input] = (trimap.astype(np.float32)[None, None, :, :])

    # If no mapping found, try first two inputs
    if not feeds and len(input_names) >= 1:
        # assume first is image
        feeds[input_names[0]] = img_0_1.transpose(2, 0, 1)[None, :].astype(np.float32)
        if len(input_names) >= 2:
            feeds[input_names[1]] = (trimap.astype(np.float32)[None, None, :, :])

    # run
    try:
        out = session.run(None, feeds)
    except Exception as e:
        # last resort: try uint8 image
        try:
            feeds2 = {k: (v.astype(np.uint8) if v.dtype==np.float32 else v) for k,v in feeds.items()}
            out = session.run(None, feeds2)
        except Exception as e2:
            print('ONNX run error:', e, e2)
            return None

    # Pick plausible output
    alpha = None
    for o in out:
        arr = np.array(o)
        if arr.ndim == 4 and arr.shape[1] == 1:
            # 1x1xHxW or 1xHxWx1
            if arr.shape[0] == 1:
                if arr.shape[2] == h and arr.shape[3] == w:
                    alpha = arr[0,0,:,:]
                    break
        if arr.ndim == 3 and (arr.shape[1] == h and arr.shape[2] == w):
            alpha = arr[0,:,:]
            break
        if arr.ndim == 2 and arr.shape[0] == h and arr.shape[1] == w:
            alpha = arr
            break

    if alpha is None:
        # try squeeze
        for o in out:
            arr = np.array(o)
            arr = np.squeeze(arr)
            if arr.ndim == 2 and arr.shape[0] == h and arr.shape[1] == w:
                alpha = arr
                break

    if alpha is None:
        print('Could not interpret ONNX outputs, outputs shapes:', [np.array(o).shape for o in out])
        return None

    # normalize to 0-255
    a = alpha.astype(np.float32)
    a = a - a.min()
    if a.max() > 0:
        a = a / a.max()
    a = (a * 255.0).round().astype(np.uint8)
    return a


if __name__ == '__main__':
    cli()
