"""
Tests for ML Ops Pipeline

Run with: python -m pytest ml_ops/tests/ -v
"""
import os
import sys
import tempfile
import shutil
import unittest
import numpy as np
import pandas as pd

# Add parent paths for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


class TestDatasetVersioner(unittest.TestCase):
    """Test dataset versioning functionality."""
    
    def setUp(self):
        """Create temporary directory for tests."""
        self.test_dir = tempfile.mkdtemp()
        self.data_path = os.path.join(self.test_dir, "datasets")
    
    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir)
    
    def _create_sample_df(self, n=100):
        """Create sample DataFrame for testing."""
        return pd.DataFrame({
            'income_stability_index': np.random.random(n),
            'expense_control_ratio': np.random.random(n),
            'payment_consistency_score': np.random.random(n),
            'target': np.random.randint(0, 3, n)
        })
    
    def test_save_and_load_version(self):
        """Test saving and loading a dataset version."""
        from ml_ops.data.versioning import DatasetVersioner
        
        versioner = DatasetVersioner(self.data_path)
        
        train_df = self._create_sample_df(60)
        val_df = self._create_sample_df(20)
        test_df = self._create_sample_df(20)
        
        version = versioner.save_version(train_df, val_df, test_df, "Test dataset")
        
        self.assertEqual(version, "v1")
        
        # Load and verify
        loaded = versioner.load_version("v1")
        self.assertEqual(len(loaded['train']), 60)
        self.assertEqual(len(loaded['val']), 20)
        self.assertEqual(len(loaded['test']), 20)
    
    def test_latest_version(self):
        """Test loading latest version."""
        from ml_ops.data.versioning import DatasetVersioner
        
        versioner = DatasetVersioner(self.data_path)
        
        # Save two versions
        versioner.save_version(
            self._create_sample_df(50),
            self._create_sample_df(25),
            self._create_sample_df(25)
        )
        versioner.save_version(
            self._create_sample_df(100),
            self._create_sample_df(50),
            self._create_sample_df(50)
        )
        
        # Latest should be v2
        loaded = versioner.load_version("latest")
        self.assertEqual(len(loaded['train']), 100)
    
    def test_manifest(self):
        """Test manifest creation."""
        from ml_ops.data.versioning import DatasetVersioner
        
        versioner = DatasetVersioner(self.data_path)
        versioner.save_version(
            self._create_sample_df(60),
            self._create_sample_df(20),
            self._create_sample_df(20),
            description="Test manifest"
        )
        
        manifest = versioner.get_manifest("v1")
        
        self.assertEqual(manifest['version'], "v1")
        self.assertEqual(manifest['total_records'], 100)
        self.assertEqual(manifest['description'], "Test manifest")
        self.assertIn('train', manifest['splits'])


class TestDataSplitter(unittest.TestCase):
    """Test data splitting functionality."""
    
    def test_split_ratios(self):
        """Test that splits match expected ratios."""
        from ml_ops.training.splitter import DataSplitter
        
        splitter = DataSplitter(train_ratio=0.6, val_ratio=0.2, test_ratio=0.2)
        
        df = pd.DataFrame({
            'feature1': np.random.random(1000),
            'target': np.random.randint(0, 3, 1000)
        })
        
        train, val, test = splitter.split(df)
        
        # Check approximate ratios (allow 5% tolerance)
        self.assertAlmostEqual(len(train) / 1000, 0.6, delta=0.05)
        self.assertAlmostEqual(len(val) / 1000, 0.2, delta=0.05)
        self.assertAlmostEqual(len(test) / 1000, 0.2, delta=0.05)
    
    def test_stratified_split(self):
        """Test that stratification preserves class distribution."""
        from ml_ops.training.splitter import DataSplitter
        
        splitter = DataSplitter()
        
        # Create imbalanced dataset
        df = pd.DataFrame({
            'feature1': np.random.random(1000),
            'target': [0]*700 + [1]*200 + [2]*100  # 70%, 20%, 10%
        })
        
        train, val, test = splitter.split(df, stratify=True)
        
        # Check class distributions are similar
        for split_df in [train, val, test]:
            dist = split_df['target'].value_counts(normalize=True)
            self.assertAlmostEqual(dist.get(0, 0), 0.7, delta=0.1)


class TestDriftDetector(unittest.TestCase):
    """Test drift detection functionality."""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        shutil.rmtree(self.test_dir)
    
    def test_psi_no_drift(self):
        """Test PSI calculation with no drift."""
        from ml_ops.monitoring.drift_detector import DriftDetector
        
        detector = DriftDetector(self.test_dir)
        
        # Same distribution
        expected = np.random.normal(0.5, 0.1, 1000)
        actual = np.random.normal(0.5, 0.1, 1000)
        
        psi = detector.calculate_psi(expected, actual)
        
        # PSI should be low (< 0.1)
        self.assertLess(psi, 0.1)
    
    def test_psi_with_drift(self):
        """Test PSI calculation with significant drift."""
        from ml_ops.monitoring.drift_detector import DriftDetector
        
        detector = DriftDetector(self.test_dir)
        
        # Different distributions (significant shift)
        expected = np.random.normal(0.3, 0.05, 1000)
        actual = np.random.normal(0.7, 0.05, 1000)
        
        psi = detector.calculate_psi(expected, actual)
        
        # PSI should be high (> 0.2)
        self.assertGreater(psi, 0.2)
    
    def test_detect_drift(self):
        """Test full drift detection flow."""
        from ml_ops.monitoring.drift_detector import DriftDetector
        
        detector = DriftDetector(self.test_dir)
        
        # Create and save baseline
        baseline = {
            'feature1': np.random.normal(0.5, 0.1, 1000),
            'feature2': np.random.normal(0.5, 0.1, 1000)
        }
        detector.save_baseline(baseline)
        
        # Check with drifted data
        current = {
            'feature1': np.random.normal(0.8, 0.1, 1000),  # Drifted
            'feature2': np.random.normal(0.5, 0.1, 1000)   # Same
        }
        
        result = detector.detect_drift(current)
        
        self.assertTrue(result.feature_results['feature1']['drift'])
        self.assertFalse(result.feature_results['feature2']['drift'])


class TestModelRegistry(unittest.TestCase):
    """Test model registry functionality."""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.registry_path = os.path.join(self.test_dir, "registry")
        self.active_path = os.path.join(self.test_dir, "active")
    
    def tearDown(self):
        shutil.rmtree(self.test_dir)
    
    def test_register_and_load(self):
        """Test model registration and loading."""
        from ml_ops.registry.model_registry import ModelRegistry
        from sklearn.preprocessing import StandardScaler
        import xgboost as xgb
        
        registry = ModelRegistry(self.registry_path, self.active_path)
        
        # Create dummy model
        model = xgb.XGBClassifier(n_estimators=10)
        X = np.random.random((100, 5))
        y = np.random.randint(0, 3, 100)
        model.fit(X, y)
        
        scaler = StandardScaler()
        scaler.fit(X)
        
        metrics = {'accuracy': 0.85, 'f1_score': 0.82}
        
        version = registry.register(model, scaler, metrics, "v1")
        
        self.assertEqual(version, "v1.0.0")
        
        # Verify metadata
        metadata = registry.get_metadata(version)
        self.assertEqual(metadata['metrics']['accuracy'], 0.85)
    
    def test_activation(self):
        """Test model activation."""
        from ml_ops.registry.model_registry import ModelRegistry
        from sklearn.preprocessing import StandardScaler
        import xgboost as xgb
        
        registry = ModelRegistry(self.registry_path, self.active_path)
        
        model = xgb.XGBClassifier(n_estimators=10)
        X = np.random.random((100, 5))
        y = np.random.randint(0, 3, 100)
        model.fit(X, y)
        scaler = StandardScaler().fit(X)
        
        version = registry.register(model, scaler, {'accuracy': 0.9}, "v1")
        registry.activate(version)
        
        self.assertEqual(registry.get_active_version(), version)
        
        # Load active model
        loaded_model, loaded_scaler, metadata = registry.load_active()
        self.assertIsNotNone(loaded_model)
    
    def test_auto_activate_if_better(self):
        """Test auto-activation based on metrics."""
        from ml_ops.registry.model_registry import ModelRegistry
        from sklearn.preprocessing import StandardScaler
        import xgboost as xgb
        
        registry = ModelRegistry(self.registry_path, self.active_path)
        
        model = xgb.XGBClassifier(n_estimators=10)
        X = np.random.random((100, 5))
        y = np.random.randint(0, 3, 100)
        model.fit(X, y)
        scaler = StandardScaler().fit(X)
        
        # Register and activate first version
        v1 = registry.register(model, scaler, {'accuracy': 0.85}, "v1")
        registry.activate(v1)
        
        # Register second version with better accuracy
        v2 = registry.register(model, scaler, {'accuracy': 0.90}, "v1")
        
        activated = registry.auto_activate_if_better(v2)
        
        self.assertTrue(activated)
        self.assertEqual(registry.get_active_version(), v2)


class TestModelEvaluator(unittest.TestCase):
    """Test model evaluation functionality."""
    
    def test_evaluate(self):
        """Test comprehensive evaluation."""
        from ml_ops.training.evaluator import ModelEvaluator
        
        evaluator = ModelEvaluator()
        
        y_true = np.array([0, 0, 1, 1, 2, 2, 0, 1, 2])
        y_pred = np.array([0, 0, 1, 2, 2, 2, 0, 1, 1])  # Some errors
        y_proba = np.random.random((9, 3))
        y_proba = y_proba / y_proba.sum(axis=1, keepdims=True)  # Normalize
        
        result = evaluator.evaluate(y_true, y_pred, y_proba)
        
        self.assertGreater(result.accuracy, 0)
        self.assertGreater(result.f1_score, 0)
        self.assertEqual(len(result.confusion_matrix), 3)
        self.assertIn('Low Risk', result.per_class_metrics)


def run_ml_ops_tests():
    """Run all ML ops tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestDatasetVersioner))
    suite.addTests(loader.loadTestsFromTestCase(TestDataSplitter))
    suite.addTests(loader.loadTestsFromTestCase(TestDriftDetector))
    suite.addTests(loader.loadTestsFromTestCase(TestModelRegistry))
    suite.addTests(loader.loadTestsFromTestCase(TestModelEvaluator))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_ml_ops_tests()
    sys.exit(0 if success else 1)
