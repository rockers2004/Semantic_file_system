import torch
import torch.nn.functional as F
import time
import os
from typing import List, Dict, Any, Tuple, Optional
from semantixel.services.model_manager import model_manager
from semantixel.services.index_service import IndexService
from semantixel.services.face_service import FaceService
from semantixel.core.logging import logger

class SearchService:
    """
    Core search logic for semantic retrieval and graph generation.
    """
    
    def __init__(self, index_service: IndexService, face_service: FaceService):
        self.index_service = index_service
        self.face_service = face_service
        self.image_collection = index_service.image_collection
        self.text_collection = index_service.text_collection
        self.bm25_service = index_service.bm25_service

    def _process_item_id(self, item_id: str) -> Dict[str, Any]:
        """Format an ID to JSON results."""
        if ":::" in item_id:
            video_path, timestamp = item_id.split(":::")
            return {
                "path": video_path,
                "type": "video",
                "timestamp": float(timestamp),
                "composite_id": item_id
            }
        else:
            return {
                "path": item_id,
                "type": "image"
            }

    def semantic_text_search(self, query: str, top_k: int = 5, threshold: float = 0.0, media_type: str = "image") -> List[Dict[str, Any]]:
        """
        Performs semantic search on images using CLIP text embeddings.
        """
        logger.info(f"Semantic Text Search: {query} (top_k={top_k}, type={media_type})")
        text_embedding = model_manager.clip.get_text_embeddings(query)
        
        # Increase pool for deduplication
        query_k = top_k * 10
        results = self.image_collection.query(
            query_embeddings=[text_embedding],
            n_results=query_k
        )
        
        return self._filter_results(results, top_k, threshold, media_type)

    def semantic_image_search(self, image_path: str, top_k: int = 5, threshold: float = 0.0, media_type: str = "all") -> List[Dict[str, Any]]:
        """CLIP Image similarity search."""
        embedding = model_manager.clip.get_image_embeddings([image_path])[0]
        
        query_k = top_k * 10
        results = self.image_collection.query(
            query_embeddings=[embedding],
            n_results=query_k
        )
        
        # Exclude self if top result is remarkably similar
        return self._filter_results(results, top_k, threshold, media_type, exclude_path=image_path)

    def keyword_search(self, query: str, top_k: int = 5, threshold: float = 0.0, media_type: str = "all") -> List[Dict[str, Any]]:
        """BM25 search."""
        ids = self.bm25_service.search(query, top_k, threshold, media_type)
        return [self._process_item_id(id) for id in ids]

    def _filter_results(self, results: Dict[str, Any], top_k: int, threshold: float, media_type: str, exclude_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Filtering and deduplication (limit frames per video)."""
        paths = results["ids"][0]
        distances = results["distances"][0]
        
        similarities = [1 - d for d in distances]
        final_results = []
        video_counts = {}
        MAX_FRAMES_PER_VIDEO = 1
        
        for p, s in zip(paths, similarities):
            if s <= threshold:
                continue
                
            if exclude_path and p == exclude_path:
                continue
                
            is_video = ":::" in p
            if media_type == "image" and is_video:
                continue
            if media_type == "video" and not is_video:
                continue
                
            if is_video:
                base_video_path = p.split(":::")[0]
                count = video_counts.get(base_video_path, 0)
                if count >= MAX_FRAMES_PER_VIDEO:
                    continue
                video_counts[base_video_path] = count + 1
            
            final_results.append(self._process_item_id(p))
            
            if len(final_results) >= top_k:
                break
                
        return final_results

    def generate_graph_data(self) -> Dict[str, Any]:
        """Calculates pairwise cosine similarity and creates node-link graph data."""
        t0 = time.time()
        data = self.image_collection.get(include=["embeddings"])
        ids = data["ids"]
        embeddings = data["embeddings"]
        
        if not ids:
            return {"nodes": [], "links": []}
            
        nodes = []
        for doc_id in ids:
            nodes.append({
                "id": doc_id,
                "composite_id": doc_id,
                **self._process_item_id(doc_id),
                "fileName": os.path.basename(doc_id.split(":::")[0])
            })
            
        # Use PyTorch for efficiency
        embs_tensor = torch.tensor(embeddings)
        sim_matrix = F.cosine_similarity(embs_tensor.unsqueeze(1), embs_tensor.unsqueeze(0), dim=2)
        
        links = []
        TOP_K_NEIGHBORS = 3
        MIN_SIMILARITY = 0.5
        
        sim_matrix.fill_diagonal_(-1.0)
        top_values, top_indices = torch.topk(sim_matrix, min(TOP_K_NEIGHBORS, len(ids) - 1), dim=1)
        
        seen_edges = set()
        for i, source_id in enumerate(ids):
            for j in range(top_indices.shape[1]):
                target_idx = top_indices[i, j].item()
                similarity = top_values[i, j].item()
                target_id = ids[target_idx]
                
                if similarity > MIN_SIMILARITY:
                    edge_tuple = tuple(sorted([source_id, target_id]))
                    if edge_tuple not in seen_edges:
                        seen_edges.add(edge_tuple)
                        links.append({
                            "source": source_id,
                            "target": target_id,
                            "value": float(similarity)
                        })
        
        logger.info(f"Generated Semantic Graph: {len(nodes)} nodes, {len(links)} edges in {time.time()-t0:.3f}s")
        return {"nodes": nodes, "links": links}

    def integrated_face_search(self, query: str, top_k: int = 10, threshold: float = 0.3, media_type: str = "image") -> List[Dict[str, Any]]:
        """
        Combines face recognition by name and semantic context search.
        Query format example: "Find Karunya playing cricket"
        """
        import re
        query_lower = query.lower().strip()
        
        # Simple regex for "Find [name] [activity]"
        name, activity = None, None
        match = re.search(r'find\s+(\w+)\s+(.+)', query_lower)
        if match:
            name, activity = match.group(1), match.group(2)
        else:
            match = re.search(r'find\s+(\w+)', query_lower)
            if match:
                name = match.group(1)
            else:
                name = query_lower # Fallback
                
        # 1. Face Search
        face_paths = self.face_service.search_by_name(name)
        if not face_paths:
            return []
            
        if not activity:
            return [self._process_item_id(p) for p in face_paths[:top_k]]
            
        # 2. Semantic Search Filter
        semantic_results = self.semantic_text_search(activity, top_k=top_k * 5, threshold=threshold, media_type=media_type)
        semantic_paths = {r["path"] for r in semantic_results}
        
        # 3. Intersection
        final_ids = [p for p in face_paths if p in semantic_paths]
        return [self._process_item_id(p) for p in final_ids[:top_k]]
