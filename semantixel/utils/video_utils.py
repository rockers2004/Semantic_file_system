import cv2
from PIL import Image
import os
from semantixel.core.logging import logger

def get_histogram(frame):
    """Calculates and normalizes the HSV histogram for a given frame."""
    if frame is None:
        return None
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
    cv2.normalize(hist, hist, alpha=0, beta=1, norm_type=cv2.NORM_MINMAX)
    return hist

def calculate_histogram_difference(hist1, hist2):
    """
    Calculates the Bhattacharyya distance between two normalized histograms.
    A lower distance means the frames are more similar (0.0 is identical).
    """
    if hist1 is None or hist2 is None:
        return 1.0
    return cv2.compareHist(hist1, hist2, cv2.HISTCMP_BHATTACHARYYA)

def extract_frames_in_memory(video_path, fps=0.5, similarity_threshold=0.6):
    """
    Extracts frames from a video file at a specified frame rate (fps) using a generator.
    Includes scene detection to drop redundant frames based on a similarity threshold.
    
    Yields dicts with 'image' (PIL.Image) and 'timestamp' (float).
    """
    if not os.path.exists(video_path):
        logger.error(f"Video file not found at {video_path}")
        return
        
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        logger.error(f"Could not open video file {video_path}")
        return
        
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    if video_fps <= 0:
        video_fps = 30.0 # fallback if cv2 cannot detect fps
        
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    if video_fps == 0:
        cap.release()
        return
        
    video_duration_sec = total_frames / video_fps
    
    current_sec = 0.0
    prev_hist = None
    frames_yielded = 0
    frames_skipped = 0
    
    try:
        while current_sec < video_duration_sec:
            # Seek directly to the target timestamp in milliseconds
            cap.set(cv2.CAP_PROP_POS_MSEC, current_sec * 1000.0)
            ret, frame = cap.read()
            
            if not ret:
                break
                
            current_hist = get_histogram(frame)
            
            # Perform scene detection
            if prev_hist is not None:
                dist = calculate_histogram_difference(prev_hist, current_hist)
                # If distance is lower than threshold, scenes are too similar, skip this frame
                if dist < similarity_threshold:
                    frames_skipped += 1
                    current_sec += 1.0 / fps
                    continue
                    
            # Keep this frame's histogram for the next comparison
            prev_hist = current_hist
            
            # Convert BGR (OpenCV) to RGB (PIL)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(frame_rgb)
            
            frames_yielded += 1
            
            yield {
                "image": pil_image,
                "timestamp": round(current_sec, 3)
            }
            
            current_sec += 1.0 / fps
    finally:
        total_checked = frames_yielded + frames_skipped
        if total_checked > 0:
            logger.debug(f"[Video Indexed] {os.path.basename(video_path)} | Kept: {frames_yielded} frames | Skipped: {frames_skipped} redundant frames")
            
        cap.release()
