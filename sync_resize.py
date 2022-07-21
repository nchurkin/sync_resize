import argparse
import os
from os import scandir
import fnmatch
import shutil
from pathlib import Path
from typing import Iterable
import time

from PIL import Image, ImageFile, UnidentifiedImageError
from loguru import logger

ImageFile.LOAD_TRUNCATED_IMAGES = True
IMAGE_QUALITY = 80
PATTERNS = ("*.gif", "*.jpg", "*.jpeg", "*.png", "*.tif", "*.jfif")


@logger.catch()
def sync_images(source: str | os.PathLike, dest: str | os.PathLike,
                patterns: Iterable, size: tuple[int, int] = None) -> None:
    source_files = filter_tree(scan_tree(source), patterns)
    dest_files = filter_tree(scan_tree(dest), patterns)

    actions = determine_actions(source_files, dest_files, source, dest)

    for action, *paths in actions:
        print(action, *paths)

        if action == "COPY":
            os.makedirs(os.path.dirname(paths[1]), exist_ok=True)
            shutil.copyfile(*paths)
            if size is not None:
                resize_image(paths[1], size)

        elif action == "DELETE":
            os.remove(paths[0])


@logger.catch()
def resize_image(path: Path, size: tuple[int, int]):
    try:
        img = Image.open(path)
    except UnidentifiedImageError:
        return
    img.getexif().clear()
    img.thumbnail(size)
    if img.format == "PNG" and img.mode == "RGBA" and path.suffix.lower() in (".jpg", ".jpeg"):
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        background.save(path, optimize=True, quality=IMAGE_QUALITY)
    elif img.format == "GIF" and path.suffix.lower() in (".jpg", ".jpeg"):
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img)
        background.save(path, optimize=True, quality=IMAGE_QUALITY)
    else:
        img.save(path, optimize=True, quality=IMAGE_QUALITY)


@logger.catch()
def scan_tree(root: str | os.PathLike, path_rel_to: str | os.PathLike = None) -> Iterable[str]:
    if path_rel_to is None:
        path_rel_to = root
    for entry in scandir(root):
        if entry.is_dir(follow_symlinks=False):
            yield from scan_tree(entry.path, path_rel_to)
        else:
            rel_dir = os.path.relpath(entry.path, path_rel_to)
            yield rel_dir


def filter_tree(paths: Iterable, patterns: Iterable) -> Iterable:
    for path in paths:
        if any(fnmatch.fnmatch(path, p) for p in patterns):
            yield path


@logger.catch()
def determine_actions(source_files: Iterable[Path], dest_files: Iterable[Path],
                      source_folder: str, dest_folder: str) -> Iterable:
    for rel_dir in source_files:
        if rel_dir not in dest_files:
            source_path = Path(source_folder) / rel_dir
            dest_path = Path(dest_folder) / rel_dir
            yield "COPY", source_path, dest_path

    for rel_dir in dest_files:
        if rel_dir not in source_files:
            yield "DELETE", dest_folder / rel_dir


if __name__ == '__main__':
    start_time = time.time()

    logger.add('./log/sync_resize.log', rotation='10 MB', backtrace=False, catch=True, encoding='utf8')
    logger.info("Started.")

    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=str)
    parser.add_argument("--dest", required=True, type=str)
    parser.add_argument("--size", required=False, type=int, nargs=2, default=[800, 800])
    args = parser.parse_args()

    sync_images(source=args.source, dest=args.dest, size=args.size, patterns=PATTERNS)

    logger.info(f"Execution time: {int(time.time() - start_time)} seconds.")
