"""
Sentiment analysis module using HuggingFace models and keyword-based rules.
"""
from typing import Dict, List, Optional, Tuple
import logging
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
import torch

from config import get_huggingface_model, get_keywords_positive, get_keywords_negative

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """Sentiment analyzer combining HuggingFace model with keyword rules."""
    
    def __init__(self):
        self.model_name = None
        self.pipeline = None
        self.keywords_positive = []
        self.keywords_negative = []
        self._load_model()
        self._load_keywords()
    
    def _load_model(self) -> None:
        """Load HuggingFace sentiment analysis model."""
        # Determine device once
        device = 0 if torch.cuda.is_available() else -1
        
        try:
            model_name = get_huggingface_model()
            if model_name != self.model_name:
                logger.info(f"Loading sentiment model: {model_name}")
                
                self.pipeline = pipeline(
                    "sentiment-analysis",
                    model=model_name,
                    device=device,
                    return_all_scores=False
                )
                self.model_name = model_name
                logger.info("Model loaded successfully")
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            # Fallback to a simpler model if the default fails
            try:
                logger.info("Trying fallback model...")
                self.pipeline = pipeline(
                    "sentiment-analysis",
                    model="distilbert-base-uncased-finetuned-sst-2-english",
                    device=device
                )
                self.model_name = "distilbert-base-uncased-finetuned-sst-2-english"
            except Exception as e2:
                logger.error(f"Fallback model also failed: {e2}")
                self.pipeline = None
    
    def _load_keywords(self) -> None:
        """Load positive and negative keywords from configuration."""
        self.keywords_positive = [kw.lower() for kw in get_keywords_positive()]
        self.keywords_negative = [kw.lower() for kw in get_keywords_negative()]
    
    def reload_config(self) -> None:
        """Reload model and keywords from configuration."""
        self._load_model()
        self._load_keywords()
    
    def _check_keywords(self, text: str) -> Optional[Tuple[str, float]]:
        """
        Check if text contains positive or negative keywords.
        Returns (label, confidence) if keyword found, None otherwise.
        """
        if not text:
            return None
        
        text_lower = text.lower()
        
        # Check for positive keywords
        for keyword in self.keywords_positive:
            if keyword in text_lower:
                return ("POSITIVE", 0.9)  # High confidence for keyword match
        
        # Check for negative keywords
        for keyword in self.keywords_negative:
            if keyword in text_lower:
                return ("NEGATIVE", 0.9)  # High confidence for keyword match
        
        return None
    
    def analyze(self, text: str) -> Dict[str, any]:
        """
        Analyze sentiment of text using model + keyword rules.
        Returns dict with label, score, and method.
        """
        if not text or not text.strip():
            return {
                "label": "NEUTRAL",
                "score": 0.5,
                "method": "empty"
            }
        
        # First check keywords (takes priority)
        keyword_result = self._check_keywords(text)
        if keyword_result:
            label, score = keyword_result
            return {
                "label": label,
                "score": score,
                "method": "keyword"
            }
        
        # If no keyword match, use model
        if self.pipeline is None:
            return {
                "label": "NEUTRAL",
                "score": 0.5,
                "method": "fallback"
            }
        
        try:
            result = self.pipeline(text[:512])  # Limit length for model input
            
            # Map model labels to our standard labels
            model_label = result[0]["label"].upper()
            model_score = result[0]["score"]
            
            # Handle different model label formats
            if "POSITIVE" in model_label or "POS" in model_label:
                label = "POSITIVE"
            elif "NEGATIVE" in model_label or "NEG" in model_label:
                label = "NEGATIVE"
            else:
                label = "NEUTRAL"
            
            return {
                "label": label,
                "score": float(model_score),
                "method": "model"
            }
        except Exception as e:
            logger.error(f"Error in sentiment analysis: {e}")
            return {
                "label": "NEUTRAL",
                "score": 0.5,
                "method": "error"
            }
    
    def analyze_batch(self, texts: List[str]) -> List[Dict[str, any]]:
        """Analyze multiple texts in batch."""
        return [self.analyze(text) for text in texts]


# Global analyzer instance
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
