"""
Dataset Versioning with SHA-256 Hash Tracking

Provides lightweight version control for ML datasets without requiring
external tools like DVC. Each dataset version is stored with a manifest
containing metadata and checksums.
"""
import os
import json
import hashlib
import shutil
from datetime import datetime
from typing import Optional, Dict, Any, List
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class DatasetVersioner:
    """
    Manages versioned datasets with hash-based tracking.
    
    Structure:
        data/datasets/
        ├── v1/
        │   ├── train.parquet
        │   ├── val.parquet  
        │   ├── test.parquet
        │   └── manifest.json
        ├── v2/
        └── versions.json  # Index of all versions
    """
    
    def __init__(self, base_path: str = "data/datasets"):
        self.base_path = base_path
        self.versions_file = os.path.join(base_path, "versions.json")
        os.makedirs(base_path, exist_ok=True)
        
        if not os.path.exists(self.versions_file):
            self._init_versions_file()
    
    def _init_versions_file(self):
        """Initialize the versions index file."""
        with open(self.versions_file, 'w') as f:
            json.dump({
                'versions': [],
                'latest': None,
                'created_at': datetime.now().isoformat()
            }, f, indent=2)
    
    def _get_versions_index(self) -> Dict[str, Any]:
        """Load the versions index."""
        with open(self.versions_file, 'r') as f:
            return json.load(f)
    
    def _update_versions_index(self, version: str):
        """Update the versions index with a new version."""
        index = self._get_versions_index()
        index['versions'].append(version)
        index['latest'] = version
        index['updated_at'] = datetime.now().isoformat()
        
        with open(self.versions_file, 'w') as f:
            json.dump(index, f, indent=2)
    
    @staticmethod
    def _compute_hash(df: pd.DataFrame) -> str:
        """Compute SHA-256 hash of a DataFrame."""
        # Convert to bytes and hash
        data_bytes = df.to_csv(index=False).encode('utf-8')
        return hashlib.sha256(data_bytes).hexdigest()[:16]
    
    @staticmethod
    def _compute_file_hash(filepath: str) -> str:
        """Compute SHA-256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()[:16]
    
    def _get_next_version(self) -> str:
        """Generate the next version number."""
        index = self._get_versions_index()
        if not index['versions']:
            return "v1"
        
        latest = index['versions'][-1]
        num = int(latest[1:])  # Strip 'v' prefix
        return f"v{num + 1}"
    
    def save_version(
        self,
        train_df: pd.DataFrame,
        val_df: pd.DataFrame,
        test_df: pd.DataFrame,
        description: str = "",
        source: str = "synthetic"
    ) -> str:
        """
        Save a new dataset version.
        
        Args:
            train_df: Training data
            val_df: Validation data
            test_df: Test data
            description: Optional description of this version
            source: Data source (synthetic, production, etc.)
        
        Returns:
            Version string (e.g., 'v1')
        """
        version = self._get_next_version()
        version_path = os.path.join(self.base_path, version)
        os.makedirs(version_path, exist_ok=True)
        
        # Save datasets as parquet (efficient storage)
        train_path = os.path.join(version_path, "train.parquet")
        val_path = os.path.join(version_path, "val.parquet")
        test_path = os.path.join(version_path, "test.parquet")
        
        train_df.to_parquet(train_path, index=False)
        val_df.to_parquet(val_path, index=False)
        test_df.to_parquet(test_path, index=False)
        
        # Create manifest with metadata
        manifest = {
            'version': version,
            'created_at': datetime.now().isoformat(),
            'description': description,
            'source': source,
            'splits': {
                'train': {
                    'records': len(train_df),
                    'hash': self._compute_file_hash(train_path),
                    'columns': list(train_df.columns)
                },
                'val': {
                    'records': len(val_df),
                    'hash': self._compute_file_hash(val_path),
                    'columns': list(val_df.columns)
                },
                'test': {
                    'records': len(test_df),
                    'hash': self._compute_file_hash(test_path),
                    'columns': list(test_df.columns)
                }
            },
            'total_records': len(train_df) + len(val_df) + len(test_df),
            'schema': {
                'features': [c for c in train_df.columns if c != 'target'],
                'target': 'target' if 'target' in train_df.columns else None
            }
        }
        
        manifest_path = os.path.join(version_path, "manifest.json")
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        # Update versions index
        self._update_versions_index(version)
        
        logger.info(f"Dataset version {version} saved with {manifest['total_records']} total records")
        return version
    
    def load_version(self, version: str = "latest") -> Dict[str, pd.DataFrame]:
        """
        Load a specific dataset version.
        
        Args:
            version: Version to load ('latest' or 'v1', 'v2', etc.)
        
        Returns:
            Dict with 'train', 'val', 'test' DataFrames
        """
        if version == "latest":
            index = self._get_versions_index()
            version = index.get('latest')
            if not version:
                raise ValueError("No dataset versions found")
        
        version_path = os.path.join(self.base_path, version)
        if not os.path.exists(version_path):
            raise ValueError(f"Dataset version {version} not found")
        
        return {
            'train': pd.read_parquet(os.path.join(version_path, "train.parquet")),
            'val': pd.read_parquet(os.path.join(version_path, "val.parquet")),
            'test': pd.read_parquet(os.path.join(version_path, "test.parquet"))
        }
    
    def get_manifest(self, version: str = "latest") -> Dict[str, Any]:
        """Get the manifest for a dataset version."""
        if version == "latest":
            index = self._get_versions_index()
            version = index.get('latest')
            if not version:
                raise ValueError("No dataset versions found")
        
        manifest_path = os.path.join(self.base_path, version, "manifest.json")
        with open(manifest_path, 'r') as f:
            return json.load(f)
    
    def list_versions(self) -> List[Dict[str, Any]]:
        """List all dataset versions with their manifests."""
        index = self._get_versions_index()
        versions = []
        
        for v in index['versions']:
            try:
                manifest = self.get_manifest(v)
                versions.append({
                    'version': v,
                    'created_at': manifest['created_at'],
                    'total_records': manifest['total_records'],
                    'description': manifest.get('description', '')
                })
            except Exception as e:
                logger.warning(f"Could not load manifest for {v}: {e}")
        
        return versions
    
    def validate_version(self, version: str) -> bool:
        """Validate dataset integrity by checking hashes."""
        manifest = self.get_manifest(version)
        version_path = os.path.join(self.base_path, version)
        
        for split_name, split_info in manifest['splits'].items():
            file_path = os.path.join(version_path, f"{split_name}.parquet")
            actual_hash = self._compute_file_hash(file_path)
            
            if actual_hash != split_info['hash']:
                logger.error(f"Hash mismatch for {split_name}: expected {split_info['hash']}, got {actual_hash}")
                return False
        
        logger.info(f"Dataset version {version} validated successfully")
        return True
    
    def delete_version(self, version: str):
        """Delete a dataset version (with safety check)."""
        index = self._get_versions_index()
        
        if version == index.get('latest') and len(index['versions']) == 1:
            raise ValueError("Cannot delete the only dataset version")
        
        version_path = os.path.join(self.base_path, version)
        if os.path.exists(version_path):
            shutil.rmtree(version_path)
        
        # Update index
        index['versions'].remove(version)
        if index['latest'] == version:
            index['latest'] = index['versions'][-1] if index['versions'] else None
        
        with open(self.versions_file, 'w') as f:
            json.dump(index, f, indent=2)
        
        logger.info(f"Dataset version {version} deleted")
