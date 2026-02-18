"""
Sentiment analysis module using HuggingFace models (opcional) and keyword-based rules.
Si transformers/torch no están instalados (ej. en Vercel), solo se usan keywords + NEUTRAL.
"""
from typing import Dict, List, Optional, Tuple
import logging

# Import opcional: en Vercel no instalamos transformers/torch para ahorrar memoria
try:
    from transformers import pipeline
    import torch
    _TRANSFORMERS_AVAILABLE = True
except ImportError:
    _TRANSFORMERS_AVAILABLE = False
    pipeline = None
    torch = None

from config import get_huggingface_model, get_keywords_positive, get_keywords_negative

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """Sentiment analyzer: keywords siempre; modelo HuggingFace solo si está instalado."""

    def __init__(self):
        self.model_name = None
        self.pipeline = None
        self.keywords_positive = []
        self.keywords_negative = []
        self._model_loaded = False
        self._load_keywords()

    def _ensure_model_loaded(self) -> None:
        """Carga el modelo solo cuando hace falta y si transformers está disponible."""
        if not _TRANSFORMERS_AVAILABLE:
            return
        if self._model_loaded and self.pipeline is not None:
            return
        self._load_model()

    def _load_model(self) -> None:
        """Carga el modelo HuggingFace solo si transformers/torch están instalados."""
        if not _TRANSFORMERS_AVAILABLE:
            logger.info("Sentiment model skipped (transformers/torch not installed - keyword-only mode)")
            return
        if self._model_loaded and self.pipeline is not None:
            return

        device = -1  # CPU only

        try:
            model_name = get_huggingface_model()
            if model_name != self.model_name:
                logger.info(f"Loading sentiment model: {model_name} (CPU mode for memory efficiency)")

                model_kwargs = {
                    "device": device,
                    "return_all_scores": False,
                    "batch_size": 1,
                    "padding": False,
                }
                try:
                    model_kwargs["torch_dtype"] = torch.float16
                    logger.info("Using float16 precision for memory efficiency")
                except Exception as e:
                    logger.debug(f"Could not use float16: {e}")

                self.pipeline = pipeline(
                    "sentiment-analysis",
                    model=model_name,
                    **model_kwargs
                )
                self.model_name = model_name
                self._model_loaded = True
                logger.info("Model loaded successfully (CPU mode)")
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            try:
                logger.info("Trying lighter fallback model...")
                self.pipeline = pipeline(
                    "sentiment-analysis",
                    model="distilbert-base-uncased-finetuned-sst-2-english",
                    device=device,
                    batch_size=1
                )
                self.model_name = "distilbert-base-uncased-finetuned-sst-2-english"
                self._model_loaded = True
                logger.info("Fallback model loaded (lighter, CPU mode)")
            except Exception as e2:
                logger.error(f"Fallback model also failed: {e2}")
                self.pipeline = None
                self._model_loaded = False

    def _load_keywords(self) -> None:
        """Load positive and negative keywords from configuration."""
        self.keywords_positive = [kw.lower() for kw in get_keywords_positive()]
        self.keywords_negative = [kw.lower() for kw in get_keywords_negative()]

    def reload_config(self) -> None:
        """Reload model and keywords from configuration."""
        self._model_loaded = False
        self.pipeline = None
        self.model_name = None
        self._load_keywords()

    def _check_keywords(self, text: str) -> Optional[Tuple[str, float]]:
        """Check if text contains positive or negative keywords."""
        if not text:
            return None
        text_lower = text.lower()
        for keyword in self.keywords_positive:
            if keyword in text_lower:
                return ("POSITIVE", 0.9)
        for keyword in self.keywords_negative:
            if keyword in text_lower:
                return ("NEGATIVE", 0.9)
        return None

    def analyze(self, text: str) -> Dict[str, any]:
        """
        Analyze sentiment: keywords first; if no match and model available, use model;
        otherwise NEUTRAL (ideal para Vercel sin transformers).
        """
        if not text or not text.strip():
            return {"label": "NEUTRAL", "score": 0.5, "method": "empty"}

        keyword_result = self._check_keywords(text)
        if keyword_result:
            label, score = keyword_result
            return {"label": label, "score": score, "method": "keyword"}

        self._ensure_model_loaded()

        if self.pipeline is None:
            return {"label": "NEUTRAL", "score": 0.5, "method": "fallback"}

        try:
            result = self.pipeline(text[:512])
            model_label = result[0]["label"].upper()
            model_score = result[0]["score"]
            if "POSITIVE" in model_label or "POS" in model_label:
                label = "POSITIVE"
            elif "NEGATIVE" in model_label or "NEG" in model_label:
                label = "NEGATIVE"
            else:
                label = "NEUTRAL"
            return {"label": label, "score": float(model_score), "method": "model"}
        except Exception as e:
            logger.error(f"Error in sentiment analysis: {e}")
            return {"label": "NEUTRAL", "score": 0.5, "method": "error"}

    def analyze_batch(self, texts: List[str], batch_size: int = 10) -> List[Dict[str, any]]:
        """Analyze multiple texts in batches."""
        results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_results = [self.analyze(text) for text in batch]
            results.extend(batch_results)
            if i % (batch_size * 5) == 0:
                import gc
                gc.collect()
        return results


_analyzer_instance: Optional[SentimentAnalyzer] = None


def get_analyzer() -> SentimentAnalyzer:
    """Get or create the global sentiment analyzer instance."""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = SentimentAnalyzer()
    return _analyzer_instance


def reload_analyzer() -> None:
    """Reload the analyzer with updated configuration."""
    global _analyzer_instance
    if _analyzer_instance:
        _analyzer_instance.reload_config()
    else:
        _analyzer_instance = SentimentAnalyzer()
