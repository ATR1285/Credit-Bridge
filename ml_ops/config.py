# ML Ops Configuration
from dataclasses import dataclass, field
from typing import Dict, Any
import os

@dataclass
class MLConfig:
    """Configuration for ML pipeline."""
    
    # Paths
    base_path: str = "x:/Creditbridge"
    data_path: str = field(default_factory=lambda: os.path.join("data", "datasets"))
    registry_path: str = field(default_factory=lambda: os.path.join("models", "registry"))
    active_path: str = field(default_factory=lambda: os.path.join("models", "active"))
    baseline_path: str = field(default_factory=lambda: os.path.join("data", "drift_baselines"))
    experiments_path: str = field(default_factory=lambda: "experiments")
    
    # Data splits
    train_ratio: float = 0.6
    val_ratio: float = 0.2
    test_ratio: float = 0.2
    random_seed: int = 42
    
    # Model hyperparameters
    model_params: Dict[str, Any] = field(default_factory=lambda: {
        'n_estimators': 250,
        'max_depth': 6,
        'learning_rate': 0.08,
        'subsample': 0.9,
        'colsample_bytree': 0.85,
        'objective': 'multi:softprob',
        'num_class': 3,
        'reg_lambda': 1.5,
        'eval_metric': 'mlogloss',
        'random_state': 42,
        'early_stopping_rounds': 10,
        'verbosity': 0
    })
    
    # Drift detection
    psi_threshold: float = 0.2  # < 0.1 no drift, 0.1-0.2 moderate, > 0.2 significant
    drift_check_sample_size: int = 1000
    
    # Retraining
    min_samples_for_retrain: int = 500
    auto_activate_on_improvement: bool = True
    
    # Feature names (should match ml_model.py)
    feature_names: list = field(default_factory=lambda: [
        # Behavioral features
        'income_stability_index',
        'expense_control_ratio', 
        'payment_consistency_score',
        'digital_engagement_score',
        'savings_growth_rate',
        'business_health_index',
        # Document-derived features
        'doc_income_verification_score',
        'doc_expense_verification_score',
        'doc_authenticity_score',
        'doc_completeness_score',
        'doc_consistency_score'
    ])

# Default config instance
config = MLConfig()
