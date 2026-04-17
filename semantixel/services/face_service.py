import os
import pickle
import numpy as np
from deepface import DeepFace
from typing import List, Dict, Any
from semantixel.core.config import config
from semantixel.core.logging import logger
from semantixel.utils.scan_utils import fast_scan_for_media

class FaceService:
    """
    Service for face detection and matching.
    """
    def __init__(self, face_db_path: str = "face_db/known_faces.pkl"):
        self.face_db_path = face_db_path
        self.known_faces = {}
        self.load_db()

    def load_db(self):
        if os.path.exists(self.face_db_path):
            try:
                with open(self.face_db_path, 'rb') as f:
                    self.known_faces = pickle.load(f)
                logger.info(f"Loaded {len(self.known_faces)} known faces")
            except Exception as e:
                logger.error(f"Error loading face database: {e}")
        else:
            logger.warning(f"Face database not found: {self.face_db_path}")

    def search_by_name(self, name_query: str, threshold: float = 0.6) -> List[str]:
        name = name_query.lower().strip()
        if name not in self.known_faces:
            logger.warning(f"Face for '{name}' not found in database")
            return []

        target_embedding = np.array(self.known_faces[name])
        results = []

        # Get all valid image paths
        include_dirs = config.include_directories
        exclude_dirs = config.exclude_directories
        paths, _ = fast_scan_for_media(include_dirs, exclude_dirs)
        image_paths = [p for p in paths if p.lower().endswith(('.png', '.jpg', '.jpeg'))]

        logger.info(f"Searching for '{name}' across {len(image_paths)} images")

        for img_path in image_paths:
            try:
                # Extract face embeddings from current image
                embeddings = DeepFace.represent(img_path=img_path, model_name='Facenet', enforce_detection=False)
                
                for embedding_data in embeddings:
                    current_embedding = np.array(embedding_data['embedding'])
                    # Cosine similarity
                    norm_target = np.linalg.norm(target_embedding)
                    norm_current = np.linalg.norm(current_embedding)
                    if norm_target == 0 or norm_current == 0:
                        continue
                        
                    similarity = np.dot(target_embedding, current_embedding) / (norm_target * norm_current)
                    
                    if similarity > threshold:
                        results.append(img_path)
                        logger.debug(f"Face match found in {img_path} (sim: {similarity:.3f})")
                        break
            except Exception:
                continue

        return results
