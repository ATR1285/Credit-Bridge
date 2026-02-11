"""
Data Drift Detection using PSI (Population Stability Index)

Detects when production data distribution shifts from the training baseline,
indicating the model may need retraining.
"""
import os
import json
import numpy as np
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class DriftResult:
    """Container for drift detection results."""
    overall_drift: bool
    overall_psi: float
    feature_results: Dict[str, Dict[str, Any]]
    recommendation: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'overall_drift': self.overall_drift,
            'overall_psi': self.overall_psi,
            'feature_results': self.feature_results,
            'recommendation': self.recommendation
        }
    
    def summary(self) -> str:
        drifted = [f for f, r in self.feature_results.items() if r.get('drift')]
        return (
            f"Overall PSI: {self.overall_psi:.4f} | "
            f"Drift: {'Yes' if self.overall_drift else 'No'} | "
            f"Features drifted: {len(drifted)}/{len(self.feature_results)}"
        )


class DriftDetector:
    """
    Population Stability Index (PSI) based drift detector.
    
    PSI Interpretation:
    - PSI < 0.1: No significant drift
    - 0.1 <= PSI < 0.2: Moderate drift (monitor)
    - PSI >= 0.2: Significant drift (retrain recommended)
    
    PSI Formula:
    PSI = Σ (Actual% - Expected%) × ln(Actual% / Expected%)
    """
    
    # PSI thresholds
    THRESHOLD_MODERATE = 0.1
    THRESHOLD_SIGNIFICANT = 0.2
    
    def __init__(
        self,
        baseline_path: str = "data/drift_baselines",
        psi_threshold: float = 0.2
    ):
        self.baseline_path = baseline_path
        self.psi_threshold = psi_threshold
        self.baseline: Optional[Dict[str, np.ndarray]] = None
        
        os.makedirs(baseline_path, exist_ok=True)
        self._load_baseline()
    
    def _load_baseline(self):
        """Load baseline distributions from file."""
        baseline_file = os.path.join(self.baseline_path, "baseline.json")
        
        if os.path.exists(baseline_file):
            with open(baseline_file, 'r') as f:
                data = json.load(f)
                self.baseline = {
                    k: np.array(v) for k, v in data.get('distributions', {}).items()
                }
            logger.info(f"Loaded baseline with {len(self.baseline)} features")
        else:
            logger.info("No baseline found. Call save_baseline() to create one.")
    
    def save_baseline(
        self,
        distributions: Dict[str, np.ndarray],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Save baseline distributions for future drift detection.
        
        Args:
            distributions: Dict mapping feature names to value arrays
            metadata: Optional metadata (dataset version, date, etc.)
        """
        baseline_file = os.path.join(self.baseline_path, "baseline.json")
        
        # Convert numpy arrays to lists for JSON
        data = {
            'distributions': {k: v.tolist() for k, v in distributions.items()},
            'metadata': metadata or {},
            'created_at': str(np.datetime64('now'))
        }
        
        with open(baseline_file, 'w') as f:
            json.dump(data, f)
        
        self.baseline = distributions
        logger.info(f"Saved baseline with {len(distributions)} features")
    
    def calculate_psi(
        self,
        expected: np.ndarray,
        actual: np.ndarray,
        n_buckets: int = 10
    ) -> float:
        """
        Calculate Population Stability Index between two distributions.
        
        Args:
            expected: Baseline (training) distribution
            actual: Current (production) distribution
            n_buckets: Number of buckets for discretization
            
        Returns:
            PSI value (0 = no drift, higher = more drift)
        """
        # Handle edge cases
        if len(expected) == 0 or len(actual) == 0:
            return 0.0
        
        # Create buckets from expected distribution
        # Use percentiles to create equal-frequency buckets
        breakpoints = np.percentile(expected, np.linspace(0, 100, n_buckets + 1))
        
        # Ensure unique breakpoints
        breakpoints = np.unique(breakpoints)
        if len(breakpoints) < 3:
            # Fall back to equal-width bins
            breakpoints = np.linspace(expected.min(), expected.max(), n_buckets + 1)
        
        # Make first and last breakpoints -inf and +inf
        breakpoints[0] = -np.inf
        breakpoints[-1] = np.inf
        
        # Calculate proportions in each bucket
        expected_counts = np.histogram(expected, breakpoints)[0]
        actual_counts = np.histogram(actual, breakpoints)[0]
        
        expected_percents = expected_counts / len(expected)
        actual_percents = actual_counts / len(actual)
        
        # Avoid log(0) and division by zero
        # Replace zeros with small value
        expected_percents = np.clip(expected_percents, 0.0001, None)
        actual_percents = np.clip(actual_percents, 0.0001, None)
        
        # PSI formula
        psi = np.sum(
            (actual_percents - expected_percents) * 
            np.log(actual_percents / expected_percents)
        )
        
        return float(psi)
    
    def detect_drift(
        self,
        current_data: Dict[str, np.ndarray]
    ) -> DriftResult:
        """
        Detect drift across all features.
        
        Args:
            current_data: Dict mapping feature names to value arrays
            
        Returns:
            DriftResult with per-feature and overall drift status
        """
        if self.baseline is None:
            raise ValueError("No baseline loaded. Call save_baseline() first.")
        
        feature_results = {}
        psi_values = []
        
        for feature, current_values in current_data.items():
            if feature not in self.baseline:
                logger.warning(f"Feature {feature} not in baseline, skipping")
                continue
            
            baseline_values = self.baseline[feature]
            psi = self.calculate_psi(baseline_values, current_values)
            psi_values.append(psi)
            
            # Determine drift status
            if psi >= self.THRESHOLD_SIGNIFICANT:
                status = 'significant'
                has_drift = True
            elif psi >= self.THRESHOLD_MODERATE:
                status = 'moderate'
                has_drift = False  # Only significant triggers overall drift
            else:
                status = 'stable'
                has_drift = False
            
            feature_results[feature] = {
                'psi': round(psi, 4),
                'drift': has_drift,
                'status': status
            }
        
        # Calculate overall PSI (average)
        overall_psi = np.mean(psi_values) if psi_values else 0.0
        
        # Check if any feature has significant drift
        overall_drift = any(
            r.get('drift', False) for r in feature_results.values()
        )
        
        # Determine recommendation
        if overall_drift:
            recommendation = 'retrain_recommended'
        elif overall_psi >= self.THRESHOLD_MODERATE:
            recommendation = 'monitor_closely'
        else:
            recommendation = 'no_action_needed'
        
        result = DriftResult(
            overall_drift=overall_drift,
            overall_psi=round(overall_psi, 4),
            feature_results=feature_results,
            recommendation=recommendation
        )
        
        logger.info(f"Drift detection: {result.summary()}")
        return result
    
    def detect_from_dataframe(self, df, feature_columns: List[str]) -> DriftResult:
        """
        Detect drift from a pandas DataFrame.
        
        Args:
            df: DataFrame with production data
            feature_columns: List of feature column names
            
        Returns:
            DriftResult
        """
        current_data = {}
        for col in feature_columns:
            if col in df.columns:
                current_data[col] = df[col].values
        
        return self.detect_drift(current_data)
    
    def create_baseline_from_dataset(self, dataset_version: str = "latest"):
        """
        Create baseline from a versioned dataset.
        
        Args:
            dataset_version: Which dataset version to use
        """
        from ml_ops.data.loader import DataLoader
        from ml_ops.config import config
        
        loader = DataLoader(config)
        data = loader.load_from_version(dataset_version)
        
        # Use training data as baseline
        train_df = data['train']
        distributions = loader.get_feature_distributions(train_df)
        
        self.save_baseline(
            distributions,
            metadata={
                'source': 'dataset',
                'version': dataset_version,
                'n_samples': len(train_df)
            }
        )
