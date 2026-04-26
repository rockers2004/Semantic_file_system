import torch
from typing import List, Optional
from transformers import AutoTokenizer, AutoModel
from semantixel.providers.base import TextEmbeddingProvider
from semantixel.core.logging import logger

class HFTextEmbeddingProvider(TextEmbeddingProvider):
    """
    Hugging Face Transformers implementation of Text Embeddings.
    """
    def __init__(self, checkpoint: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.checkpoint = checkpoint
        self.tokenizer = None
        self.model = None
        self.device = (
            "mps"
            if torch.backends.mps.is_available()
            else ("cuda" if torch.cuda.is_available() else "cpu")
        )

    def load(self):
        if self.model is not None:
            return
            
        logger.info(f"Loading HF Text Embedding model: {self.checkpoint} on {self.device}")
        
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.checkpoint, local_files_only=True)
            self.model = AutoModel.from_pretrained(self.checkpoint, local_files_only=True)
        except (OSError, ValueError):
            logger.info(f"Model {self.checkpoint} not found locally. Downloading...")
            self.tokenizer = AutoTokenizer.from_pretrained(self.checkpoint)
            self.model = AutoModel.from_pretrained(self.checkpoint)
            
        self.model.to(self.device)
        self.model.eval()

    def unload(self):
        if self.model is not None:
            logger.info("Unloading Text Embedding model")
            self.model = None
            self.tokenizer = None
            if self.device == "cuda":
                torch.cuda.empty_cache()

    def _mean_pooling(self, model_output, attention_mask):
        token_embeddings = model_output[0]
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)

    def get_embeddings(self, text: str) -> List[float]:
        self.load()
        
        encoded_input = self.tokenizer([text], padding=True, truncation=True, return_tensors='pt').to(self.device)
        with torch.no_grad():
            model_output = self.model(**encoded_input)

        # Perform pooling
        sentence_embeddings = self._mean_pooling(model_output, encoded_input['attention_mask'])
        
        # Normalize
        sentence_embeddings = torch.nn.functional.normalize(sentence_embeddings, p=2, dim=1)
        
        return sentence_embeddings[0].tolist()
