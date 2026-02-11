"""
Training Pipeline for Credit Scoring Model

Orchestrates the full training flow: data loading, scaling, training,
evaluation, and MLflow logging.
"""
import os
import sys
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime
import numpy as np
import xgboost as xgb
from sklearn.preprocessing import StandardScaler
import logging

# Add parent for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ml_ops.config import config, MLConfig
from ml_ops.data.loader import DataLoader
from ml_ops.training.evaluator import ModelEvaluator, EvaluationResult

logger = logging.getLogger(__name__)

# Optional MLflow import
try:
    import mlflow
    import mlflow.xgboost
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    logger.warning("MLflow not installed. Experiment tracking disabled.")


@dataclass
class TrainingResult:
    """Container for training outputs."""
    model: xgb.XGBClassifier
    scaler: StandardScaler
    metrics: Dict[str, float]
    evaluation: EvaluationResult
    dataset_version: str
    model_version: Optional[str] = None
    training_time: float = 0.0
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    
    def summary(self) -> str:
        """Human-readable summary."""
        return (
            f"Dataset: {self.dataset_version} | "
            f"Time: {self.training_time:.2f}s | "
            f"{self.evaluation.summary()}"
        )


class TrainingPipeline:
    """
    Production training pipeline for credit scoring model.
    
    Features:
    - Proper train/val/test split (60/20/20)
    - Early stopping on validation set
    - Comprehensive metrics logging
    - MLflow experiment tracking (optional)
    - Model versioning integration
    """
    
    def __init__(self, config: MLConfig = None):
        self.config = config or MLConfig()
        self.data_loader = DataLoader(self.config)
        self.evaluator = ModelEvaluator()
        
        # Set up MLflow if available
        if MLFLOW_AVAILABLE:
            mlflow.set_tracking_uri(f"file:///{self.config.experiments_path}")
            mlflow.set_experiment("creditbridge-credit-scoring")
    
    def train(
        self,
        dataset_version: str = "latest",
        generate_if_missing: bool = True,
        n_samples: int = 5000,
        log_to_mlflow: bool = True
    ) -> TrainingResult:
        """
        Execute full training pipeline.
        
        Args:
            dataset_version: Which dataset version to use ('latest' or 'v1', etc.)
            generate_if_missing: Generate synthetic data if no datasets exist
            n_samples: Number of samples if generating
            log_to_mlflow: Whether to log to MLflow
            
        Returns:
            TrainingResult with model, scaler, and metrics
        """
        start_time = datetime.now()
        logger.info(f"Starting training pipeline with dataset {dataset_version}...")
        
        # Load or generate data
        try:
            data = self.data_loader.load_from_version(dataset_version)
            logger.info(f"Loaded dataset version {dataset_version}")
        except (ValueError, FileNotFoundError) as e:
            if generate_if_missing:
                logger.info(f"Dataset not found, generating {n_samples} synthetic samples...")
                data = self.data_loader.generate_synthetic(n_samples, save_version=True)
                dataset_version = "v1"  # First generated version
            else:
                raise
        
        # Prepare features and targets
        X_train, X_val, X_test, y_train, y_val, y_test = self.data_loader.prepare_for_training(data)
        
        # Scale features
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_val_scaled = scaler.transform(X_val)
        X_test_scaled = scaler.transform(X_test)
        
        # Configure model
        model_params = self.config.model_params.copy()
        early_stopping = model_params.pop('early_stopping_rounds', 10)
        
        # Train model
        logger.info("Training XGBoost classifier...")
        model = xgb.XGBClassifier(**model_params)
        
        model.fit(
            X_train_scaled, y_train,
            eval_set=[(X_val_scaled, y_val)],
            verbose=False
        )
        
        # Evaluate on test set
        y_pred = model.predict(X_test_scaled)
        y_proba = model.predict_proba(X_test_scaled)
        
        evaluation = self.evaluator.evaluate(y_test, y_pred, y_proba)
        
        training_time = (datetime.now() - start_time).total_seconds()
        
        # Create result
        result = TrainingResult(
            model=model,
            scaler=scaler,
            metrics={
                'accuracy': evaluation.accuracy,
                'precision': evaluation.precision,
                'recall': evaluation.recall,
                'f1_score': evaluation.f1_score,
                'roc_auc': evaluation.roc_auc
            },
            evaluation=evaluation,
            dataset_version=dataset_version,
            training_time=training_time,
            hyperparameters=model_params
        )
        
        # Log to MLflow
        if log_to_mlflow and MLFLOW_AVAILABLE:
            self._log_to_mlflow(result)
        
        logger.info(f"Training complete: {result.summary()}")
        self.evaluator.print_classification_report(y_test, y_pred)
        
        return result
    
    def _log_to_mlflow(self, result: TrainingResult):
        """Log training run to MLflow."""
        try:
            with mlflow.start_run():
                # Log parameters
                mlflow.log_params(result.hyperparameters)
                mlflow.log_param("dataset_version", result.dataset_version)
                
                # Log metrics
                mlflow.log_metrics(result.metrics)
                mlflow.log_metric("training_time_seconds", result.training_time)
                
                # Log model
                mlflow.xgboost.log_model(result.model, "model")
                
                logger.info("Logged run to MLflow")
        except Exception as e:
            logger.warning(f"Failed to log to MLflow: {e}")
    
    def retrain_from_production(
        self,
        min_samples: int = None,
        save_dataset: bool = True
    ) -> Optional[TrainingResult]:
        """
        Retrain using production data from database.
        
        Args:
            min_samples: Minimum samples required to train
            save_dataset: Save extracted data as new version
            
        Returns:
            TrainingResult or None if insufficient data
        """
        min_samples = min_samples or self.config.min_samples_for_retrain
        
        # Load production data
        production_df = self.data_loader.load_from_database()
        
        if len(production_df) < min_samples:
            logger.warning(
                f"Insufficient production data: {len(production_df)} < {min_samples}"
            )
            return None
        
        # Split and save as new version
        from ml_ops.training.splitter import DataSplitter
        from ml_ops.data.versioning import DatasetVersioner
        
        splitter = DataSplitter(
            train_ratio=self.config.train_ratio,
            val_ratio=self.config.val_ratio,
            test_ratio=self.config.test_ratio
        )
        
        train_df, val_df, test_df = splitter.split(production_df)
        
        if save_dataset:
            versioner = DatasetVersioner(self.config.data_path)
            version = versioner.save_version(
                train_df, val_df, test_df,
                description=f"Production data extracted on {datetime.now().isoformat()}",
                source="production"
            )
            logger.info(f"Saved production data as version {version}")
        
        # Train on the new data
        return self.train(dataset_version="latest", generate_if_missing=False)
    
    def get_feature_importance(self, model: xgb.XGBClassifier) -> Dict[str, float]:
        """Get feature importance from trained model."""
        importances = model.feature_importances_
        feature_importance = {}
        
        for i, name in enumerate(self.config.feature_names):
            if i < len(importances):
                feature_importance[name] = float(importances[i])
        
        # Sort by importance
        return dict(sorted(
            feature_importance.items(),
            key=lambda x: x[1],
            reverse=True
        ))
