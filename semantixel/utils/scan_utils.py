import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from semantixel.core.logging import logger

def scan_directory(directory, exclude_directories):
    """
    Recursively scans a directory for image and video files, excluding any directories specified.
    """
    media_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".mp4", ".mkv", ".avi", ".mov"}
    images = []
    try:
        if not os.path.isdir(directory):
            return []
            
        with os.scandir(directory) as entries:
            for entry in entries:
                if (
                    entry.is_file()
                    and not entry.name.startswith("._")
                    and entry.name.lower().endswith(tuple(media_extensions))
                ):
                    images.append(entry.path)
                elif entry.is_dir():
                    # Check if this directory is in the exclude list
                    if not any(
                        os.path.commonpath([os.path.abspath(entry.path), os.path.abspath(excl)]) == os.path.abspath(excl)
                        for excl in exclude_directories
                    ):
                        images.extend(scan_directory(entry.path, exclude_directories))
    except PermissionError:
        logger.debug(f"Permission denied: {directory}")
    except Exception as e:
        logger.error(f"Error scanning {directory}: {e}")
    return images

def fast_scan_for_media(directories, exclude_directories=None):
    """
    Scans multiple directories for media files in parallel, excluding specified directories.
    """
    if exclude_directories is None:
        exclude_directories = []

    start_time = time.time()
    all_images = []

    cpu_count = os.cpu_count() or 1
    with tqdm(total=len(directories), desc="Scanning directories") as pbar:
        with ThreadPoolExecutor(max_workers=cpu_count) as executor:
            future_to_dir = {
                executor.submit(scan_directory, d, exclude_directories): d
                for d in directories
            }
            for future in as_completed(future_to_dir):
                d = future_to_dir[future]
                try:
                    images = future.result()
                    all_images.extend(images)
                    pbar.update()
                except Exception as e:
                    logger.error(f"Error processing {d}: {e}")

    end_time = time.time()
    return all_images, end_time - start_time
