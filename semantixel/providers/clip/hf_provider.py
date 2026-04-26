import torch
import warnings
import os
from typing import List, Union, Optional
from PIL import Image
from transformers import CLIPProcessor, CLIPModel
from concurrent.futures import ThreadPoolExecutor
from semantixel.providers.base import CLIPProvider
from semantixel.core.logging import logger

# Suppress warnings
warnings.filterwarnings("ignore")

class HFCLIPProvider(CLIPProvider):
    """
    Hugging Face Transformers implementation of CLIP.
    """
    def __init__(self, checkpoint: str = "openai/clip-vit-base-patch32"):
        self.checkpoint = checkpoint
        self.model: Optional[CLIPModel] = None
        self.processor: Optional[CLIPProcessor] = None
        self.device = (
            "mps"
            if torch.backends.mps.is_available()
            else ("cuda" if torch.cuda.is_available() else "cpu")
        )

    def load(self):
        """Loads model and processor lazily."""
        if self.model is not None:
            return

        logger.info(f"Loading HF CLIP model: {self.checkpoint} on {self.device}")
        
        # Configure for offline usage if preferred, but allow auto-download if missing
        try:
            self.model = CLIPModel.from_pretrained(self.checkpoint, local_files_only=True)
            self.processor = CLIPProcessor.from_pretrained(self.checkpoint, local_files_only=True, use_fast=True)
        except (OSError, ValueError):
            logger.info(f"Model {self.checkpoint} not found locally. Downloading...")
            self.model = CLIPModel.from_pretrained(self.checkpoint)
            self.processor = CLIPProcessor.from_pretrained(self.checkpoint, use_fast=True)
            
        self.model.to(self.device)
        self.model.eval() # Ensure eval mode
        
        if self.device == "cuda":
            torch.cuda.empty_cache()

    def unload(self):
        """Unload model from GPU/Memory."""
        if self.model is not None:
            logger.info(f"Unloading CLIP model: {self.checkpoint}")
            self.model = None
            self.processor = None
            if self.device == "cuda":
                torch.cuda.empty_cache()

    def _open_image(self, image_input: Union[str, Image.Image]) -> Image.Image:
        if isinstance(image_input, Image.Image):
            return image_input
        return Image.open(image_input).convert("RGB")

    def get_image_embeddings(self, images: List[Union[str, Image.Image]]) -> List[List[float]]:
        if not images:
            return []
        
        self.load() # Ensure loaded
        
        with ThreadPoolExecutor() as executor:
            pil_images = list(executor.map(self._open_image, images))
            
        inputs = self.processor(images=pil_images, return_tensors="pt").to(self.device)
        with torch.no_grad():
            image_features = self.model.get_image_features(**inputs)
            
        # Normalize to unit length (L2 normalization)
        image_features = image_features / image_features.norm(p=2, dim=-1, keepdim=True)
            
        return [feat.tolist() for feat in image_features.cpu()]

    def get_text_embeddings(self, text: str) -> List[float]:
        self.load()
        with torch.no_grad():
            inputs = self.processor(text=[text], return_tensors="pt").to(self.device)
            text_features = self.model.get_text_features(**inputs)
            # Normalize to unit length
            text_features = text_features / text_features.norm(p=2, dim=-1, keepdim=True)
        return text_features.cpu()[0].tolist()
