from rembg import remove, new_session
from PIL import Image
from pathlib import Path
from tqdm import tqdm
import sys


def is_image_file(p: Path):
    return p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def process_folder(input_root: Path):
    # Output folder: sibling inside input_root parent, named <inputname>_ready
    out_root = input_root.parent / f"{input_root.name}_ready"
    out_root.mkdir(exist_ok=True)

    print(f"Creating rembg session (model will be downloaded on first run if needed)...")
    session = new_session()

    files = [p for p in input_root.rglob('*') if p.is_file() and is_image_file(p)]
    if not files:
        print("No image files found in", input_root)
        return

    for src in tqdm(files, desc="Processing files"):
        try:
            rel = src.relative_to(input_root)
            dest_dir = out_root / rel.parent
            dest_dir.mkdir(parents=True, exist_ok=True)

            img = Image.open(src).convert("RGBA")
            result = remove(img, session=session)

            # Ensure we save as PNG with same stem
            out_path = dest_dir / (src.stem + ".png")
            if hasattr(result, "save"):
                result.save(out_path)
            else:
                with open(out_path, "wb") as f:
                    f.write(result)
        except Exception as e:
            print("Error processing:", src, e)

    print("Done. Output written to:", out_root)


def main():
    # Accept path as CLI arg or prompt the user
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
    else:
        input_str = input("Enter path to folder to process: ").strip()
        input_path = Path(input_str)

    if not input_path.exists() or not input_path.is_dir():
        print("Provided path does not exist or is not a folder:", input_path)
        return

    process_folder(input_path.resolve())


if __name__ == "__main__":
    main()