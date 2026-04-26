import os
import chromadb
from tqdm import tqdm
from typing import List, Tuple, Dict, Any, Optional
from semantixel.core.config import config
from semantixel.core.logging import logger
from semantixel.services.model_manager import model_manager
from semantixel.services.bm25_service import BM25Service
from semantixel.utils.scan_utils import fast_scan_for_media
from semantixel.utils.video_utils import extract_frames_in_memory

class IndexService:
    """
    Core service for managing the media index (VectorDB + Keyword search).
    """
    
    def __init__(self, db_path: str = "db"):
        self.db_path = db_path
        self.client = chromadb.PersistentClient(path=db_path)
        self.image_collection = self.client.get_or_create_collection(
            "images", metadata={"hnsw:space": "cosine"}
        )
        self.text_collection = self.client.get_or_create_collection(
            "texts", metadata={"hnsw:space": "cosine"}
        )
        self.bm25_service = BM25Service(index_path=os.path.join(db_path, "bm25_index.pkl"))
        self.video_extensions = {".mp4", ".mkv", ".avi", ".mov"}

    def run_full_scan(self):
        """
        Scans directories and indexes all found media.
        """
        logger.info("Starting full media scan and index update")
        include_dirs = config.include_directories
        exclude_dirs = config.exclude_directories
        
        if not include_dirs:
            logger.warning("No include_directories configured. Skipping scan.")
            return

        paths, elapsed = fast_scan_for_media(include_dirs, exclude_dirs)
        logger.info(f"Found {len(paths)} media files in {elapsed:.2f}s")
        
        self.index_media(paths)
        self.cleanup_index(paths)

    def index_media(self, paths: List[str]):
        """
        Processes and indexes the provided paths.
        """
        batch_size = config.batch_size
        deep_scan = config.deep_scan
        
        with tqdm(total=len(paths), desc="Indexing media") as pbar:
            processing_inputs = []
            processing_ids = []
            processing_metadatas = []
            
            def flush_batch():
                if not processing_inputs:
                    return
                
                logger.debug(f"Flushing batch of {len(processing_inputs)} items")
                
                # Visual Embeddings
                image_embeddings = model_manager.clip.get_image_embeddings(processing_inputs)
                self.image_collection.upsert(
                    ids=processing_ids,
                    embeddings=image_embeddings,
                    metadatas=processing_metadatas
                )
                
                # OCR & Text Embeddings
                ocr_texts = model_manager.ocr.apply_ocr(processing_inputs)
                
                for idx, text in enumerate(ocr_texts):
                    if text:
                        current_id = processing_ids[idx]
                        metadata = processing_metadatas[idx]
                        
                        # Semantic Text Search
                        text_embedding = model_manager.text_embed.get_embeddings(text)
                        self.text_collection.upsert(
                            ids=[current_id],
                            embeddings=[text_embedding],
                            metadatas=[metadata]
                        )
                        
                        # Keyword Search
                        self.bm25_service.add_document(current_id, text)
                
                processing_inputs.clear()
                processing_ids.clear()
                processing_metadatas.clear()

            for path in paths:
                is_video = path.lower().endswith(tuple(self.video_extensions))
                needs_indexing = False
                
                # Check if already indexed
                if is_video:
                    results = self.image_collection.get(where={"source_video": path})
                    if not results["ids"]:
                        needs_indexing = True
                else:
                    results = self.image_collection.get(ids=[path])
                    if not results["ids"]:
                        needs_indexing = True
                    elif deep_scan:
                        # Deep scan logic (e.g., checksum or average) - for now just check existence
                        # To be fully production-ready, we should hash the file
                        pass

                if needs_indexing:
                    if is_video:
                        for frame in extract_frames_in_memory(path):
                            processing_inputs.append(frame["image"])
                            composite_id = f"{path}:::{frame['timestamp']}"
                            processing_ids.append(composite_id)
                            processing_metadatas.append({
                                "source_video": path,
                                "timestamp": frame['timestamp'],
                                "type": "video_frame"
                            })
                            
                            if len(processing_inputs) >= batch_size:
                                flush_batch()
                    else:
                        processing_inputs.append(path)
                        processing_ids.append(path)
                        processing_metadatas.append({"type": "image"})
                        
                        if len(processing_inputs) >= batch_size:
                            flush_batch()
                
                pbar.update(1)
            
            flush_batch() # Last one
            self.bm25_service.rebuild()

    def cleanup_index(self, valid_paths: List[str]):
        """
        Removes stale entries from the index.
        """
        logger.info("Cleaning up index...")
        all_ids = self.image_collection.get()["ids"]
        valid_paths_set = set(valid_paths)
        
        ids_to_delete = []
        for doc_id in all_ids:
            base_path = doc_id.split(":::")[0] if ":::" in doc_id else doc_id
            if base_path not in valid_paths_set:
                ids_to_delete.append(doc_id)
        
        if ids_to_delete:
            logger.info(f"Removing {len(ids_to_delete)} stale entries")
            self.image_collection.delete(ids=ids_to_delete)
            # Find matching text IDs (they use same doc_id)
            self.text_collection.delete(ids=ids_to_delete)
            # BM25 is harder to clean individually, but rebuild() handles it if we don't call add_document for them
            # For now, we'll just leave them in BM25 until next rebuild or implement delete in BM25Service
