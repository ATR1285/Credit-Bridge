"""
Data Loader for ML Pipeline

Handles loading data from versioned datasets or generating synthetic data
using the existing CreditMLModel's generation capabilities.
"""
import os
import sys
import pandas as pd
import numpy as np
from typing import Optional, Dict, Tuple
import logging

# Add parent directory for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)


class DataLoader:
    """
    Unified data loading for ML pipeline.
    
    Supports:
    - Loading from versioned datasets
    - Generating synthetic data via CreditMLModel
    - Production data extraction from database
    """
    
    def __init__(self, config=None):
        from ml_ops.config import config as default_config
        self.config = config or default_config
        self._credit_model = None
    
    @property
    def credit_model(self):
        """Lazy load CreditMLModel to avoid circular imports."""
        if self._credit_model is None:
            from ml_model import CreditMLModel
            self._credit_model = CreditMLModel()
        return self._credit_model
    
    def load_from_version(self, version: str = "latest") -> Dict[str, pd.DataFrame]:
        """
        Load data from a versioned dataset.
        
        Args:
            version: Dataset version to load
            
        Returns:
            Dict with 'train', 'val', 'test' DataFrames
        """
        from ml_ops.data.versioning import DatasetVersioner
        
        versioner = DatasetVersioner(self.config.data_path)
        return versioner.load_version(version)
    
    def generate_synthetic(
        self,
        n_samples: int = 5000,
        save_version: bool = True
    ) -> Dict[str, pd.DataFrame]:
        """
        Generate synthetic training data.
        
        Uses the existing CreditMLModel.generate_training_data() method
        and splits into train/val/test sets.
        
        Args:
            n_samples: Total number of samples to generate
            save_version: Whether to save as a new dataset version
            
        Returns:
            Dict with 'train', 'val', 'test' DataFrames
        """
        from ml_ops.training.splitter import DataSplitter
        
        logger.info(f"Generating {n_samples} synthetic samples...")
        
        # Generate using existing method
        full_df = self.credit_model.generate_training_data(n_samples)
        
        # Split into train/val/test
        splitter = DataSplitter(
            train_ratio=self.config.train_ratio,
            val_ratio=self.config.val_ratio,
            test_ratio=self.config.test_ratio,
            random_seed=self.config.random_seed
        )
        
        train_df, val_df, test_df = splitter.split(full_df)
        
        data = {
            'train': train_df,
            'val': val_df,
            'test': test_df
        }
        
        if save_version:
            from ml_ops.data.versioning import DatasetVersioner
            versioner = DatasetVersioner(self.config.data_path)
            version = versioner.save_version(
                train_df, val_df, test_df,
                description=f"Synthetic data with {n_samples} samples",
                source="synthetic"
            )
            logger.info(f"Saved as dataset version {version}")
        
        return data
    
    def load_from_database(
        self,
        limit: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Load production data from the database.
        
        Extracts assessment data and converts to feature vectors.
        
        Args:
            limit: Maximum number of records
            start_date: Filter by assessment date (ISO format)
            end_date: Filter by assessment date (ISO format)
            
        Returns:
            DataFrame with features and targets
        """
        from app import app, CreditAssessment, FinancialProfile
        import json
        
        with app.app_context():
            query = CreditAssessment.query.filter(
                CreditAssessment.status.in_(['approved', 'rejected'])
            )
            
            if start_date:
                from datetime import datetime
                query = query.filter(CreditAssessment.assessment_date >= datetime.fromisoformat(start_date))
            
            if end_date:
                from datetime import datetime
                query = query.filter(CreditAssessment.assessment_date <= datetime.fromisoformat(end_date))
            
            if limit:
                query = query.limit(limit)
            
            assessments = query.all()
            
            if not assessments:
                logger.warning("No production data found matching criteria")
                return pd.DataFrame()
            
            # Extract features from assessments
            records = []
            for assessment in assessments:
                try:
                    features_dict = json.loads(assessment.features_json) if assessment.features_json else {}
                    
                    # Map to standard feature names
                    record = {}
                    for feature_name in self.config.feature_names:
                        record[feature_name] = features_dict.get(feature_name, 0.0)
                    
                    # Create target from risk category
                    risk_map = {'Low': 0, 'Medium': 1, 'High': 2}
                    record['target'] = risk_map.get(assessment.risk_category, 1)
                    
                    records.append(record)
                except Exception as e:
                    logger.warning(f"Error extracting features from assessment {assessment.id}: {e}")
            
            df = pd.DataFrame(records)
            logger.info(f"Loaded {len(df)} production records")
            return df
    
    def get_feature_distributions(self, df: pd.DataFrame) -> Dict[str, np.ndarray]:
        """
        Extract feature value distributions for drift detection.
        
        Args:
            df: DataFrame with features
            
        Returns:
            Dict mapping feature names to value arrays
        """
        distributions = {}
        for feature in self.config.feature_names:
            if feature in df.columns:
                distributions[feature] = df[feature].values
        return distributions
    
    def prepare_for_training(
        self,
        data: Dict[str, pd.DataFrame]
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Prepare data for XGBoost training.
        
        Args:
            data: Dict with 'train', 'val', 'test' DataFrames
            
        Returns:
            Tuple of (X_train, X_val, X_test, y_train, y_val, y_test)
        """
        feature_cols = self.config.feature_names
        
        X_train = data['train'][feature_cols].values
        X_val = data['val'][feature_cols].values
        X_test = data['test'][feature_cols].values
        
        y_train = data['train']['target'].values
        y_val = data['val']['target'].values
        y_test = data['test']['target'].values
        
        return X_train, X_val, X_test, y_train, y_val, y_test
