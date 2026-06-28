"""Semantic graph generation — builds a similarity graph from embeddings."""

import os
import time
from typing import Any, Dict, List
import torch
import torch.nn.functional as F
from semantixel.core.logging import logger
from semantixel.media import parse_media_id


class GraphService:
    """Generates a semantic similarity graph from a ChromaDB collection.

    Each node represents an indexed media item.  Edges connect the top-3
    nearest neighbours (cosine similarity > 0.5).
    """

    TOP_K_NEIGHBORS = 3
    MIN_SIMILARITY = 0.5

    def __init__(self, image_collection):
        self.image_collection = image_collection

    def generate(self) -> Dict[str, Any]:
        """Build and return the graph.

        Returns:
            A dict with ``"nodes"`` and ``"links"`` lists suitable for
            JSON serialisation.
        """
        t0 = time.time()
        data = self.image_collection.get(include=["embeddings", "metadatas"])
        ids = data["ids"]
        embeddings = data["embeddings"]

        if not ids:
            return {"nodes": [], "links": []}

        nodes = self._build_nodes(ids, data.get("metadatas") or [])
        links = self._build_links(ids, embeddings)

        logger.info(
            "Generated Semantic Graph: %d nodes, %d edges in %.3fs",
            len(nodes),
            len(links),
            time.time() - t0,
        )
        return {"nodes": nodes, "links": links}

    # Internal

    @staticmethod
    def _build_nodes(ids: List[str], metadatas: List[Any]) -> List[Dict[str, Any]]:
        """Convert ChromaDB records into graph node dicts."""
        nodes = []
        for doc_id, metadata in zip(ids, metadatas):
            try:
                parsed = parse_media_id(doc_id).to_result()
            except ValueError:
                from semantixel.media import describe_local_media

                parsed = describe_local_media(doc_id).to_result()

            nodes.append({
                "id": doc_id,
                **parsed,
                "fileName": os.path.basename(parsed["path"]),
            })
        return nodes

    @staticmethod
    def _build_links(
        ids: List[str], embeddings: List[List[float]]
    ) -> List[Dict[str, Any]]:
        """Compute cosine-similarity edges between all node pairs."""
        if len(ids) < 2:
            return []

        embs_tensor = torch.tensor(embeddings)
        sim_matrix = F.cosine_similarity(
            embs_tensor.unsqueeze(1), embs_tensor.unsqueeze(0), dim=2
        )

        links = []
        seen_edges: set = set()

        sim_matrix.fill_diagonal_(-1.0)
        top_values, top_indices = torch.topk(
            sim_matrix,
            min(GraphService.TOP_K_NEIGHBORS, len(ids) - 1),
            dim=1,
        )

        for i, source_id in enumerate(ids):
            for j in range(top_indices.shape[1]):
                target_idx = top_indices[i, j].item()
                similarity = top_values[i, j].item()
                target_id = ids[target_idx]

                if similarity > GraphService.MIN_SIMILARITY:
                    edge_tuple = tuple(sorted([source_id, target_id]))
                    if edge_tuple not in seen_edges:
                        seen_edges.add(edge_tuple)
                        links.append({
                            "source": source_id,
                            "target": target_id,
                            "value": float(similarity),
                        })

        return links
