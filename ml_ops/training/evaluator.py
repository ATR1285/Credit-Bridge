"""
Model Evaluator for Credit Scoring

Calculates comprehensive metrics: accuracy, precision, recall, F1, ROC-AUC.
Generates confusion matrices and per-class metrics.
"""
import numpy as np
from typing import Dict, Any, Optional, List
from sklearn.metrics import (
    accuracy_score, precision_recall_fscore_support,
    roc_auc_score, confusion_matrix, classification_report
)
from dataclasses import dataclass, asdict
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Container for all evaluation metrics."""
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    roc_auc: float
    confusion_matrix: List[List[int]]
    per_class_metrics: Dict[str, Dict[str, float]]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    def summary(self) -> str:
        """Human-readable summary."""
        return (
            f"Accuracy: {self.accuracy:.4f} | "
            f"Precision: {self.precision:.4f} | "
            f"Recall: {self.recall:.4f} | "
            f"F1: {self.f1_score:.4f} | "
            f"ROC-AUC: {self.roc_auc:.4f}"
        )


class ModelEvaluator:
    """
    Comprehensive model evaluation for multi-class credit risk prediction.
    
    Target classes:
    - 0: Low Risk
    - 1: Medium Risk
    - 2: High Risk
    """
    
    CLASS_NAMES = ['Low Risk', 'Medium Risk', 'High Risk']
    
    def __init__(self, class_names: Optional[List[str]] = None):
        self.class_names = class_names or self.CLASS_NAMES
    
    def evaluate(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_proba: Optional[np.ndarray] = None
    ) -> EvaluationResult:
        """
        Perform comprehensive evaluation.
        
        Args:
            y_true: True labels
            y_pred: Predicted labels
            y_proba: Prediction probabilities (optional, needed for ROC-AUC)
            
        Returns:
            EvaluationResult with all metrics
        """
        # Basic metrics
        accuracy = accuracy_score(y_true, y_pred)
        
        # Weighted averages for multi-class
        precision, recall, f1, _ = precision_recall_fscore_support(
            y_true, y_pred, average='weighted', zero_division=0
        )
        
        # ROC-AUC (one-vs-rest for multi-class)
        roc_auc = 0.0
        if y_proba is not None:
            try:
                roc_auc = roc_auc_score(y_true, y_proba, multi_class='ovr', average='weighted')
            except Exception as e:
                logger.warning(f"Could not calculate ROC-AUC: {e}")
        
        # Confusion matrix
        cm = confusion_matrix(y_true, y_pred).tolist()
        
        # Per-class metrics
        per_class = self._get_per_class_metrics(y_true, y_pred)
        
        result = EvaluationResult(
            accuracy=float(accuracy),
            precision=float(precision),
            recall=float(recall),
            f1_score=float(f1),
            roc_auc=float(roc_auc),
            confusion_matrix=cm,
            per_class_metrics=per_class
        )
        
        logger.info(f"Evaluation complete: {result.summary()}")
        return result
    
    def _get_per_class_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray
    ) -> Dict[str, Dict[str, float]]:
        """Calculate metrics for each class."""
        precision, recall, f1, support = precision_recall_fscore_support(
            y_true, y_pred, average=None, zero_division=0
        )
        
        per_class = {}
        for i, class_name in enumerate(self.class_names):
            if i < len(precision):
                per_class[class_name] = {
                    'precision': float(precision[i]),
                    'recall': float(recall[i]),
                    'f1_score': float(f1[i]),
                    'support': int(support[i])
                }
        
        return per_class
    
    def print_classification_report(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray
    ):
        """Print sklearn classification report."""
        report = classification_report(
            y_true, y_pred,
            target_names=self.class_names,
            zero_division=0
        )
        print("\nClassification Report:")
        print(report)
    
    def compare_models(
        self,
        results: Dict[str, EvaluationResult]
    ) -> str:
        """
        Compare multiple model evaluation results.
        
        Args:
            results: Dict mapping model names to EvaluationResults
            
        Returns:
            Comparison summary string
        """
        lines = ["Model Comparison:", "-" * 60]
        header = f"{'Model':<20} {'Acc':>8} {'Prec':>8} {'Rec':>8} {'F1':>8} {'AUC':>8}"
        lines.append(header)
        lines.append("-" * 60)
        
        for name, result in results.items():
            line = (
                f"{name:<20} {result.accuracy:>8.4f} {result.precision:>8.4f} "
                f"{result.recall:>8.4f} {result.f1_score:>8.4f} {result.roc_auc:>8.4f}"
            )
            lines.append(line)
        
        return "\n".join(lines)
    
    def check_improvement(
        self,
        current: EvaluationResult,
        previous: EvaluationResult,
        threshold: float = 0.0
    ) -> bool:
        """
        Check if current model is better than previous.
        
        Uses accuracy as primary metric with optional threshold.
        
        Args:
            current: New model evaluation
            previous: Previous model evaluation
            threshold: Minimum improvement required
            
        Returns:
            True if current model is better
        """
        improvement = current.accuracy - previous.accuracy
        is_better = improvement >= threshold
        
        if is_better:
            logger.info(f"Model improved by {improvement:.4f}")
        else:
            logger.info(f"Model did not improve (diff: {improvement:.4f})")
        
        return is_better
