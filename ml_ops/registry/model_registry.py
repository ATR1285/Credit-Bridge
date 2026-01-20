"""
Model Registry for Version Control

Manages model versions with semantic versioning, metadata tracking,
and safe activation/rollback capabilities.
"""
import os
import sys
import json
import shutil
import joblib
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)


class ModelRegistry:
    """
    Production model registry with versioning.
    
    Structure:
        models/
        ├── registry/
        │   ├── v1.0.0/
        │   │   ├── model.pkl
        │   │   ├── scaler.pkl
        │   │   └── metadata.json
        │   └── v1.1.0/
        ├── active/
        │   ├── model.pkl
        │   ├── scaler.pkl
        │   └── metadata.json
        └── versions.json
    """
    
    def __init__(self, registry_path: str = "models/registry", active_path: str = "models/active"):
        self.registry_path = registry_path
        self.active_path = active_path
        self.versions_file = os.path.join(registry_path, "versions.json")
        
        os.makedirs(registry_path, exist_ok=True)
        os.makedirs(active_path, exist_ok=True)
        
        if not os.path.exists(self.versions_file):
            self._init_versions_file()
    
    def _init_versions_file(self):
        """Initialize the versions index."""
        with open(self.versions_file, 'w') as f:
            json.dump({
                'versions': [],
                'active': None,
                'created_at': datetime.now().isoformat()
            }, f, indent=2)
    
    def _get_versions_index(self) -> Dict[str, Any]:
        """Load versions index."""
        with open(self.versions_file, 'r') as f:
            return json.load(f)
    
    def _update_versions_index(self, version: str, active: bool = False):
        """Update versions index."""
        index = self._get_versions_index()
        if version not in index['versions']:
            index['versions'].append(version)
        if active:
            index['active'] = version
        index['updated_at'] = datetime.now().isoformat()
        
        with open(self.versions_file, 'w') as f:
            json.dump(index, f, indent=2)
    
    def _get_next_version(self, bump: str = 'patch') -> str:
        """
        Generate next semantic version.
        
        Args:
            bump: 'major', 'minor', or 'patch'
        """
        index = self._get_versions_index()
        
        if not index['versions']:
            return "v1.0.0"
        
        latest = index['versions'][-1]
        parts = latest.lstrip('v').split('.')
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
        
        if bump == 'major':
            return f"v{major + 1}.0.0"
        elif bump == 'minor':
            return f"v{major}.{minor + 1}.0"
        else:  # patch
            return f"v{major}.{minor}.{patch + 1}"
    
    def register(
        self,
        model,
        scaler,
        metrics: Dict[str, float],
        dataset_version: str,
        hyperparameters: Optional[Dict[str, Any]] = None,
        bump: str = 'patch',
        description: str = ""
    ) -> str:
        """
        Register a new model version.
        
        Args:
            model: Trained XGBoost model
            scaler: Fitted StandardScaler
            metrics: Evaluation metrics
            dataset_version: Dataset version used for training
            hyperparameters: Model hyperparameters
            bump: Version bump type ('major', 'minor', 'patch')
            description: Optional description
            
        Returns:
            Version string (e.g., 'v1.0.1')
        """
        version = self._get_next_version(bump)
        version_path = os.path.join(self.registry_path, version)
        os.makedirs(version_path, exist_ok=True)
        
        # Save model artifacts
        joblib.dump(model, os.path.join(version_path, "model.pkl"))
        joblib.dump(scaler, os.path.join(version_path, "scaler.pkl"))
        
        # Create metadata
        metadata = {
            'version': version,
            'created_at': datetime.now().isoformat(),
            'dataset_version': dataset_version,
            'metrics': metrics,
            'hyperparameters': hyperparameters or {},
            'description': description,
            'model_type': 'XGBClassifier',
            'framework_version': {
                'xgboost': self._get_xgboost_version(),
                'sklearn': self._get_sklearn_version()
            }
        }
        
        with open(os.path.join(version_path, "metadata.json"), 'w') as f:
            json.dump(metadata, f, indent=2)
        
        self._update_versions_index(version)
        
        logger.info(f"Registered model version {version} (accuracy: {metrics.get('accuracy', 0):.4f})")
        return version
    
    def _get_xgboost_version(self) -> str:
        try:
            import xgboost
            return xgboost.__version__
        except:
            return "unknown"
    
    def _get_sklearn_version(self) -> str:
        try:
            import sklearn
            return sklearn.__version__
        except:
            return "unknown"
    
    def activate(self, version: str):
        """
        Set a version as the active (production) model.
        
        Args:
            version: Version to activate
        """
        version_path = os.path.join(self.registry_path, version)
        if not os.path.exists(version_path):
            raise ValueError(f"Version {version} not found in registry")
        
        # Copy artifacts to active directory
        for filename in ['model.pkl', 'scaler.pkl', 'metadata.json']:
            src = os.path.join(version_path, filename)
            dst = os.path.join(self.active_path, filename)
            if os.path.exists(src):
                shutil.copy(src, dst)
        
        self._update_versions_index(version, active=True)
        logger.info(f"Activated model version {version}")
    
    def load_active(self) -> Tuple[Any, Any, Dict[str, Any]]:
        """
        Load the currently active model.
        
        Returns:
            Tuple of (model, scaler, metadata)
        """
        model_path = os.path.join(self.active_path, "model.pkl")
        scaler_path = os.path.join(self.active_path, "scaler.pkl")
        meta_path = os.path.join(self.active_path, "metadata.json")
        
        if not os.path.exists(model_path):
            raise ValueError("No active model found")
        
        model = joblib.load(model_path)
        scaler = joblib.load(scaler_path) if os.path.exists(scaler_path) else None
        
        metadata = {}
        if os.path.exists(meta_path):
            with open(meta_path, 'r') as f:
                metadata = json.load(f)
        
        return model, scaler, metadata
    
    def load_version(self, version: str) -> Tuple[Any, Any, Dict[str, Any]]:
        """
        Load a specific model version.
        
        Returns:
            Tuple of (model, scaler, metadata)
        """
        version_path = os.path.join(self.registry_path, version)
        if not os.path.exists(version_path):
            raise ValueError(f"Version {version} not found")
        
        model = joblib.load(os.path.join(version_path, "model.pkl"))
        scaler = joblib.load(os.path.join(version_path, "scaler.pkl"))
        
        with open(os.path.join(version_path, "metadata.json"), 'r') as f:
            metadata = json.load(f)
        
        return model, scaler, metadata
    
    def get_active_version(self) -> Optional[str]:
        """Get the currently active version."""
        index = self._get_versions_index()
        return index.get('active')
    
    def list_versions(self) -> List[Dict[str, Any]]:
        """
        List all registered versions with metadata.
        
        Returns:
            List of version metadata dicts
        """
        index = self._get_versions_index()
        versions = []
        
        for v in index['versions']:
            meta_path = os.path.join(self.registry_path, v, "metadata.json")
            if os.path.exists(meta_path):
                with open(meta_path, 'r') as f:
                    metadata = json.load(f)
                    metadata['is_active'] = (v == index.get('active'))
                    versions.append(metadata)
        
        return versions
    
    def get_metadata(self, version: str) -> Dict[str, Any]:
        """Get metadata for a specific version."""
        meta_path = os.path.join(self.registry_path, version, "metadata.json")
        if not os.path.exists(meta_path):
            raise ValueError(f"Version {version} not found")
        
        with open(meta_path, 'r') as f:
            return json.load(f)
    
    def rollback(self, version: str):
        """
        Rollback to a previous model version.
        
        Args:
            version: Version to rollback to
        """
        logger.warning(f"Rolling back to model version {version}")
        self.activate(version)
    
    def compare_versions(self, v1: str, v2: str) -> Dict[str, Any]:
        """
        Compare metrics between two versions.
        
        Returns:
            Dict with comparison results
        """
        meta1 = self.get_metadata(v1)
        meta2 = self.get_metadata(v2)
        
        comparison = {
            'versions': [v1, v2],
            'metrics_diff': {}
        }
        
        metrics1 = meta1.get('metrics', {})
        metrics2 = meta2.get('metrics', {})
        
        for metric in set(metrics1.keys()) | set(metrics2.keys()):
            val1 = metrics1.get(metric, 0)
            val2 = metrics2.get(metric, 0)
            comparison['metrics_diff'][metric] = {
                v1: val1,
                v2: val2,
                'diff': val2 - val1,
                'better': v2 if val2 > val1 else v1
            }
        
        return comparison
    
    def delete_version(self, version: str):
        """Delete a model version (with safety checks)."""
        index = self._get_versions_index()
        
        if version == index.get('active'):
            raise ValueError("Cannot delete the active model version")
        
        if len(index['versions']) == 1:
            raise ValueError("Cannot delete the only model version")
        
        version_path = os.path.join(self.registry_path, version)
        if os.path.exists(version_path):
            shutil.rmtree(version_path)
        
        index['versions'].remove(version)
        with open(self.versions_file, 'w') as f:
            json.dump(index, f, indent=2)
        
        logger.info(f"Deleted model version {version}")
    
    def auto_activate_if_better(
        self,
        new_version: str,
        metric: str = 'accuracy',
        threshold: float = 0.0
    ) -> bool:
        """
        Automatically activate new version if it's better than current.
        
        Args:
            new_version: New model version
            metric: Metric to compare
            threshold: Minimum improvement required
            
        Returns:
            True if new version was activated
        """
        active = self.get_active_version()
        
        if not active:
            self.activate(new_version)
            return True
        
        current_meta = self.get_metadata(active)
        new_meta = self.get_metadata(new_version)
        
        current_value = current_meta.get('metrics', {}).get(metric, 0)
        new_value = new_meta.get('metrics', {}).get(metric, 0)
        
        if new_value >= current_value + threshold:
            self.activate(new_version)
            logger.info(f"Auto-activated {new_version} ({metric}: {current_value:.4f} → {new_value:.4f})")
            return True
        else:
            logger.info(f"Kept {active} as active ({metric}: {new_value:.4f} < {current_value:.4f})")
            return False
