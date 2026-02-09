import argparse
import os
from os import scandir
import fnmatch
import shutil
from pathlib import Path
from typing import Iterable
import time

from PIL import Image, ImageFile, UnidentifiedImageError, ImageOps
from loguru import logger

ImageFile.LOAD_TRUNCATED_IMAGES = True
PATTERNS = ("*.gif", "*.jpg", "*.jpeg", "*.png", "*.tif", "*.jfif")


@logger.catch()
def sync_images(source: str | os.PathLike, dest: str | os.PathLike,
                patterns: Iterable, size: tuple[int, int] = None, square: bool = False) -> None:
    source_files = filter_tree(scan_tree(source), patterns)
    dest_files = filter_tree(scan_tree(dest), patterns)

    actions = determine_actions(source_files, dest_files, source, dest)

    copied, deleted = 0, 0
    for action, *paths in actions:
        if action == "COPY":
            logger.info(f"Copying: {paths[0]} -> {paths[1]}")
            os.makedirs(os.path.dirname(paths[1]), exist_ok=True)
            shutil.copyfile(*paths)
            if size is not None:
                resize_image(paths[1], size, square)
            copied += 1

        elif action == "DELETE":
            logger.info(f"Deleting: {paths[0]}")
            os.remove(paths[0])
            deleted += 1

    logger.info(f"Finished. Copied: {copied}, deleted: {deleted}.")


@logger.catch()
def resize_image(path: Path, size: tuple[int, int], square: bool):
    try:
        img = Image.open(path)
    except UnidentifiedImageError:
        logger.warning(f"Cannot identify image: {path}")
        return
    original_format = img.format
    img.getexif().clear()
    img.thumbnail(size)

    if square:
        img = img.convert("RGB")
        img = ImageOps.pad(img, size, color='white')

    if original_format == "PNG" and img.mode == "RGBA" and path.suffix.lower() in (".jpg", ".jpeg"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        background.save(path)
    elif original_format == "GIF" and path.suffix.lower() in (".jpg", ".jpeg"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img)
        background.save(path)
    else:
        img.save(path)


def scan_tree(root: str | os.PathLike, path_rel_to: str | os.PathLike = None) -> Iterable[str]:
    """Returns list of related file paths for root provided."""
    if path_rel_to is None:
        path_rel_to = root
    try:
        entries = scandir(root)
    except OSError as e:
        logger.warning(f"Cannot scan directory {root}: {e}")
        return
    for entry in entries:
        if entry.is_dir(follow_symlinks=False):
            yield from scan_tree(entry.path, path_rel_to)
        else:
            rel_dir = os.path.relpath(entry.path, path_rel_to)
            yield rel_dir


def filter_tree(paths: Iterable, patterns: Iterable) -> Iterable:
    """Filter files that match Unix shell-style wildcards pattern."""
    for path in paths:
        if any(fnmatch.fnmatch(path, p) for p in patterns):
            yield path


@logger.catch()
def determine_actions(source_files: Iterable[Path], dest_files: Iterable[Path],
                      source_folder: str, dest_folder: str) -> Iterable:
    source_files = set(source_files)
    dest_files = set(dest_files)

    for rel_path in source_files:
        if rel_path not in dest_files:
            source_path = Path(source_folder) / rel_path
            dest_path = Path(dest_folder) / rel_path
            yield "COPY", source_path, dest_path

    for rel_path in dest_files:
        if rel_path not in source_files:
            yield "DELETE", Path(dest_folder) / rel_path


if __name__ == '__main__':
    start_time = time.time()

    os.makedirs("./log", exist_ok=True)
    logger.add("./log/sync_resize.log", rotation="10 MB", backtrace=False, catch=True, encoding="utf8",
               format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {file}:{function}:{line} - {message}")
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=str)
    parser.add_argument("--dest", required=True, type=str)
    parser.add_argument("--size", required=False, type=int, nargs=2, default=[800, 800])
    parser.add_argument("--square", required=False, dest="square", action="store_true")
    args = parser.parse_args()

    logger.info(f"Started. source={args.source}, dest={args.dest}, "
                f"size={args.size[0]}x{args.size[1]}, square={args.square}")

    sync_images(source=args.source, dest=args.dest, size=args.size, patterns=PATTERNS, square=args.square)

    logger.info(f"Execution time: {int(time.time() - start_time)} seconds.")
