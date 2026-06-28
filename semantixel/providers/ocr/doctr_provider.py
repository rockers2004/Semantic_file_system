"""DocTR OCR provider for text extraction from images."""

import torch
import re
import numpy as np
import cv2
from typing import List, Union, Optional
from PIL import Image, ImageEnhance, ImageFilter
from doctr.models import ocr_predictor
from concurrent.futures import ThreadPoolExecutor
from semantixel.providers.base import OCRProvider
from semantixel.providers.registry import provider
from semantixel.core.logging import logger
from semantixel.core.device import detect_device, clear_gpu_cache


@provider("ocr", "doctr")
class DoctrOCRProvider(OCRProvider):
    """DocTR implementation of OCR.

    Uses a detection-recognition pipeline (``db_mobilenet_v3_large`` +
    ``crnn_mobilenet_v3_large`` by default) to extract text from images.
    Applies contrast/brightness/sharpness enhancement and bilateral
    filtering before inference.
    """

    def __init__(
        self,
        det_arch: str = "db_mobilenet_v3_large",
        reco_arch: str = "crnn_mobilenet_v3_large",
    ):
        self.det_arch = det_arch
        self.reco_arch = reco_arch
        self.model = None
        self.device = detect_device()

    def load(self):
        """Load the DocTR OCR model onto the selected device."""
        if self.model is not None:
            return

        logger.info(
            "Loading Doctr OCR model: %s, %s on %s",
            self.det_arch,
            self.reco_arch,
            self.device,
        )
        self.model = ocr_predictor(self.det_arch, self.reco_arch, pretrained=True)
        self.model.to(self.device)

    def unload(self):
        """Unload model and free GPU memory."""
        if self.model is not None:
            logger.info("Unloading OCR model")
            self.model = None
            clear_gpu_cache(self.device)

    @staticmethod
    def _enhance_image(image_input: Union[str, Image.Image]) -> np.ndarray:
        """Apply pre-processing enhancements to improve OCR accuracy.

        Steps: contrast -> brightness -> sharpen -> bilateral filter.
        """
        if isinstance(image_input, str):
            image = Image.open(image_input).convert("RGB")
        else:
            image = image_input.convert("RGB")

        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)

        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(1.1)

        image = image.filter(ImageFilter.SHARPEN)

        image_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        image_cv = cv2.bilateralFilter(image_cv, 9, 75, 75)
        image = cv2.cvtColor(image_cv, cv2.COLOR_BGR2RGB)

        if len(image.shape) == 2:
            image = np.stack([image] * 3, axis=-1)
        if image.shape[-1] == 4:
            image = image[:, :, :3]

        return image

    @staticmethod
    def _clean_text(text: str) -> Optional[str]:
        """Normalise and filter OCR output.

        Removes excessive whitespace, non-alphanumeric characters
        (keeping basic punctuation), and single-character words.
        Returns ``None`` if nothing meaningful remains.
        """
        if not text:
            return None
        text = " ".join(text.split())
        text = re.sub(r"[^\w\s\.\,\-\:\;\!\?]", "", text)
        words = text.split()
        words = [w for w in words if len(w) > 1 or w.isdigit()]
        text = " ".join(words)
        return text if text else None

    @staticmethod
    def _process_page(page, threshold: float) -> Optional[str]:
        """Aggregate words from a DocTR page into a single string.

        Args:
            page: A DocTR ``Page`` object.
            threshold: Minimum confidence to include a word.

        Returns:
            Cleaned text, or ``None`` if the page is empty or meaningless.
        """
        try:
            text = " ".join(
                word.value
                for block in page.blocks
                for line in block.lines
                for word in line.words
                if word.confidence > threshold
            )
        except Exception:
            return None

        text = DoctrOCRProvider._clean_text(text)

        if text is None:
            return None

        if (
            text == ""
            or not any(char.isalpha() for char in text)
            or len(text) < 3
            or all(len(word) == 1 for word in text.split() if word.isalpha())
        ):
            return None

        return text

    def apply_ocr(
        self, images: List[Union[str, Image.Image]], threshold: float = 0.4
    ) -> List[Optional[str]]:
        """Apply OCR to a batch of images.

        Args:
            images: List of image file paths or PIL Image objects.
            threshold: Minimum per-word confidence (0-1).

        Returns:
            List of extracted text strings (``None`` for images with no text).
        """
        if not images:
            return []

        self.load()

        with ThreadPoolExecutor() as executor:
            processed_images = list(executor.map(self._enhance_image, images))

        output = self.model(processed_images)
        return [self._process_page(p, threshold) for p in output.pages]
