"""
Data Splitter for Train/Validation/Test Sets

Implements proper stratified splitting for balanced class distributions
in credit risk classification.
"""
import pandas as pd
import numpy as np
from typing import Tuple
from sklearn.model_selection import train_test_split
import logging

logger = logging.getLogger(__name__)


class DataSplitter:
    """
    Stratified data splitting for ML training.
    
    Ensures balanced class representation across train/val/test sets.
    Default split: 60% train, 20% validation, 20% test
    """
    
    def __init__(
        self,
        train_ratio: float = 0.6,
        val_ratio: float = 0.2,
        test_ratio: float = 0.2,
        random_seed: int = 42
    ):
        assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 0.001, \
            "Split ratios must sum to 1.0"
        
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
        self.random_seed = random_seed
    
    def split(
        self,
        df: pd.DataFrame,
        target_col: str = 'target',
        stratify: bool = True
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Split data into train, validation, and test sets.
        
        Args:
            df: Full dataset
            target_col: Name of the target column for stratification
            stratify: Whether to use stratified sampling
            
        Returns:
            Tuple of (train_df, val_df, test_df)
        """
        if len(df) < 10:
            raise ValueError("Dataset too small for splitting")
        
        stratify_col = df[target_col] if stratify and target_col in df.columns else None
        
        # First split: train vs (val + test)
        val_test_ratio = self.val_ratio + self.test_ratio
        
        train_df, temp_df = train_test_split(
            df,
            test_size=val_test_ratio,
            random_state=self.random_seed,
            stratify=stratify_col
        )
        
        # Second split: val vs test from the temporary set
        val_ratio_adjusted = self.val_ratio / val_test_ratio
        
        stratify_temp = temp_df[target_col] if stratify and target_col in temp_df.columns else None
        
        val_df, test_df = train_test_split(
            temp_df,
            test_size=(1 - val_ratio_adjusted),
            random_state=self.random_seed,
            stratify=stratify_temp
        )
        
        # Reset indices
        train_df = train_df.reset_index(drop=True)
        val_df = val_df.reset_index(drop=True)
        test_df = test_df.reset_index(drop=True)
        
        # Log split statistics
        logger.info(f"Data split completed:")
        logger.info(f"  Train: {len(train_df)} samples ({len(train_df)/len(df)*100:.1f}%)")
        logger.info(f"  Val:   {len(val_df)} samples ({len(val_df)/len(df)*100:.1f}%)")
        logger.info(f"  Test:  {len(test_df)} samples ({len(test_df)/len(df)*100:.1f}%)")
        
        if stratify and target_col in df.columns:
            self._log_class_distributions(train_df, val_df, test_df, target_col)
        
        return train_df, val_df, test_df
    
    def _log_class_distributions(
        self,
        train_df: pd.DataFrame,
        val_df: pd.DataFrame,
        test_df: pd.DataFrame,
        target_col: str
    ):
        """Log class distributions across splits."""
        for name, split_df in [('Train', train_df), ('Val', val_df), ('Test', test_df)]:
            counts = split_df[target_col].value_counts().sort_index()
            dist = counts / len(split_df) * 100
            logger.debug(f"  {name} class distribution: {dict(dist.round(1))}")
    
    def get_split_indices(
        self,
        n_samples: int,
        stratify_labels: np.ndarray = None
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Get indices for train/val/test splits (useful for cross-validation).
        
        Args:
            n_samples: Total number of samples
            stratify_labels: Optional labels for stratification
            
        Returns:
            Tuple of (train_indices, val_indices, test_indices)
        """
        indices = np.arange(n_samples)
        
        val_test_ratio = self.val_ratio + self.test_ratio
        
        train_idx, temp_idx = train_test_split(
            indices,
            test_size=val_test_ratio,
            random_state=self.random_seed,
            stratify=stratify_labels
        )
        
        val_ratio_adjusted = self.val_ratio / val_test_ratio
        stratify_temp = stratify_labels[temp_idx] if stratify_labels is not None else None
        
        val_idx, test_idx = train_test_split(
            temp_idx,
            test_size=(1 - val_ratio_adjusted),
            random_state=self.random_seed,
            stratify=stratify_temp
        )
        
        return train_idx, val_idx, test_idx
