#!/usr/bin/env python3
from pathlib import Path
import re
import sys
from PIL import Image, ImageOps

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pillow_heif = None

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
STATIC_IMAGES = ROOT / "static" / "images"

FOLDER_OVERRIDES = {
    "Weddel seals under ice, in recycled window glass, or cast in scrap glass; the gift which says, you have my \"seal of approval\".": "Seals"
}

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tiff", ".gif"}
MAX_DIMENSION = 1080
WEBP_QUALITY = 85


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[‘’“”\"'`]+", "", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text


def parse_layout() -> list[dict]:
    entries = []
    current_section = None
    current_item = None
    multiline = False
    multiline_key = None

    for raw_line in (DATA_DIR / "layout.md").read_text(encoding="utf-8").splitlines():
        if multiline:
            if raw_line.startswith("    "):
                current_item[multiline_key] += raw_line[4:] + "\n"
                continue
            multiline = False
            multiline_key = None

        line = raw_line.rstrip("\n")
        stripped = line.lstrip()
        indent = len(line) - len(stripped)

        if not stripped:
            continue

        if stripped.startswith("- Ceramics"):
            current_section = "ceramics"
            continue

        if stripped.startswith("- Glass"):
            current_section = "glass"
            continue

        if stripped.startswith("- name:"):
            if indent == 0:
                current_section = None
            if current_item:
                entries.append(current_item)
            name = stripped[len("- name:"):].strip()
            current_item = {
                "name": name,
                "section": current_section,
                "text": "",
                "main_image": "",
            }
            continue

        if stripped.startswith("main-image:") and current_item is not None:
            current_item["main_image"] = stripped[len("main-image:"):].strip()
            continue

    if current_item:
        entries.append(current_item)

    return entries


def normalize_folder_name(page_name: str) -> str:
    if page_name in FOLDER_OVERRIDES:
        return FOLDER_OVERRIDES[page_name]

    normalized = slugify(page_name)
    for folder in sorted([d.name for d in DATA_DIR.iterdir() if d.is_dir()]):
        if slugify(folder) == normalized:
            return folder

    raise ValueError(f"Could not map page '{page_name}' to a folder in data/")


def load_image(path: Path) -> Image.Image | None:
    suffix = path.suffix.lower()
    try:
        if suffix in (".heic", ".heif") and pillow_heif is not None:
            heif_file = pillow_heif.open_heif(path)
            if hasattr(heif_file, "to_pillow"):
                return heif_file.to_pillow()
        return Image.open(path)
    except Exception as exc:
        print(f"Warning: could not open {path}: {exc}")
        return None


def process_image(src_path: Path, dest_path: Path) -> None:
    image = load_image(src_path)
    if image is None:
        return

    image = ImageOps.exif_transpose(image)
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if image.mode in ("LA", "RGBA") else "RGB")

    image.thumbnail((MAX_DIMENSION, MAX_DIMENSION), Image.LANCZOS)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.unlink(missing_ok=True)
    image.save(dest_path, "WEBP", quality=WEBP_QUALITY, method=6)
    print(f"Processed {src_path.name} -> {dest_path.relative_to(ROOT)}")


def main() -> None:
    if not STATIC_IMAGES.exists():
        STATIC_IMAGES.mkdir(parents=True, exist_ok=True)

    for entry in parse_layout():
        page_name = entry["name"]
        folder_name = normalize_folder_name(page_name)
        slug = slugify(folder_name)
        source_folder = DATA_DIR / folder_name
        target_folder = STATIC_IMAGES / slug

        if not source_folder.exists():
            print(f"Skipping {page_name}: folder {source_folder} does not exist")
            continue

        for src_path in sorted(source_folder.iterdir()):
            if src_path.suffix.lower() not in ALLOWED_EXTENSIONS:
                continue
            target_path = target_folder / f"{src_path.stem}.webp"
            process_image(src_path, target_path)

    print("Image processing complete.")


if __name__ == "__main__":
    main()
