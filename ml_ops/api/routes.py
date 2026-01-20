"""
Flask API Routes for ML Operations

Provides REST endpoints for:
- Manual retraining
- Metrics retrieval
- Drift detection
- Model version management
"""
import os
import sys
from flask import Blueprint, jsonify, request
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logger = logging.getLogger(__name__)

# Create blueprint
ml_bp = Blueprint('ml', __name__, url_prefix='/ml')


def require_bank_auth(f):
    """Decorator to require bank employee authentication."""
    from functools import wraps
    from flask import session, redirect, url_for
    
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'employee_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated


@ml_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'ml-ops',
        'version': '1.0.0'
    })


@ml_bp.route('/retrain', methods=['POST'])
@require_bank_auth
def retrain():
    """
    Trigger model retraining.
    
    Request body:
    {
        "dataset_version": "latest",  # or "v1", "v2", etc.
        "n_samples": 5000,            # for synthetic generation
        "activate": true              # auto-activate if better
    }
    """
    try:
        from ml_ops.training.pipeline import TrainingPipeline
        from ml_ops.registry.model_registry import ModelRegistry
        from ml_ops.config import config
        
        data = request.get_json() or {}
        dataset_version = data.get('dataset_version', 'latest')
        n_samples = data.get('n_samples', 5000)
        auto_activate = data.get('activate', True)
        
        logger.info(f"Starting retraining with dataset {dataset_version}...")
        
        # Run training pipeline
        pipeline = TrainingPipeline(config)
        result = pipeline.train(
            dataset_version=dataset_version,
            generate_if_missing=True,
            n_samples=n_samples
        )
        
        # Register model
        registry = ModelRegistry(config.registry_path, config.active_path)
        version = registry.register(
            model=result.model,
            scaler=result.scaler,
            metrics=result.metrics,
            dataset_version=result.dataset_version,
            hyperparameters=result.hyperparameters
        )
        
        # Auto-activate if requested and better
        activated = False
        if auto_activate:
            activated = registry.auto_activate_if_better(version)
        
        return jsonify({
            'status': 'success',
            'model_version': version,
            'metrics': result.metrics,
            'training_time': result.training_time,
            'dataset_version': result.dataset_version,
            'activated': activated
        })
        
    except Exception as e:
        logger.error(f"Retraining failed: {e}")
        return jsonify({'error': str(e)}), 500


@ml_bp.route('/metrics', methods=['GET'])
def get_metrics():
    """
    Get metrics for active or specific model version.
    
    Query params:
    - version: specific version (default: active)
    """
    try:
        from ml_ops.registry.model_registry import ModelRegistry
        from ml_ops.config import config
        
        registry = ModelRegistry(config.registry_path, config.active_path)
        version = request.args.get('version')
        
        if version:
            metadata = registry.get_metadata(version)
        else:
            version = registry.get_active_version()
            if not version:
                return jsonify({'error': 'No active model found'}), 404
            metadata = registry.get_metadata(version)
        
        return jsonify({
            'version': metadata['version'],
            'metrics': metadata['metrics'],
            'created_at': metadata['created_at'],
            'dataset_version': metadata.get('dataset_version')
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return jsonify({'error': str(e)}), 500


@ml_bp.route('/drift-check', methods=['POST'])
@require_bank_auth
def check_drift():
    """
    Run drift detection on provided data or production data.
    
    Request body (optional):
    {
        "use_production_data": true,  # Extract from database
        "limit": 1000                 # Max samples to check
    }
    
    Or provide feature distributions directly:
    {
        "feature_data": {
            "income_stability_index": [0.5, 0.6, ...],
            ...
        }
    }
    """
    try:
        from ml_ops.monitoring.drift_detector import DriftDetector
        from ml_ops.data.loader import DataLoader
        from ml_ops.config import config
        
        data = request.get_json() or {}
        
        detector = DriftDetector(config.baseline_path, config.psi_threshold)
        
        # Check if baseline exists
        if detector.baseline is None:
            return jsonify({
                'error': 'No baseline found. Train a model first to create baseline.'
            }), 400
        
        if data.get('use_production_data', False):
            # Load from database
            loader = DataLoader(config)
            limit = data.get('limit', config.drift_check_sample_size)
            production_df = loader.load_from_database(limit=limit)
            
            if len(production_df) == 0:
                return jsonify({
                    'error': 'No production data found'
                }), 400
            
            result = detector.detect_from_dataframe(
                production_df, config.feature_names
            )
        elif 'feature_data' in data:
            # Use provided data
            import numpy as np
            feature_data = {
                k: np.array(v) for k, v in data['feature_data'].items()
            }
            result = detector.detect_drift(feature_data)
        else:
            return jsonify({
                'error': 'Provide feature_data or set use_production_data=true'
            }), 400
        
        return jsonify(result.to_dict())
        
    except Exception as e:
        logger.error(f"Drift check failed: {e}")
        return jsonify({'error': str(e)}), 500


@ml_bp.route('/models', methods=['GET'])
def list_models():
    """List all registered model versions."""
    try:
        from ml_ops.registry.model_registry import ModelRegistry
        from ml_ops.config import config
        
        registry = ModelRegistry(config.registry_path, config.active_path)
        versions = registry.list_versions()
        
        return jsonify({
            'count': len(versions),
            'active': registry.get_active_version(),
            'versions': versions
        })
        
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        return jsonify({'error': str(e)}), 500


@ml_bp.route('/models/<version>/activate', methods=['POST'])
@require_bank_auth
def activate_model(version):
    """Activate a specific model version."""
    try:
        from ml_ops.registry.model_registry import ModelRegistry
        from ml_ops.config import config
        
        registry = ModelRegistry(config.registry_path, config.active_path)
        registry.activate(version)
        
        return jsonify({
            'status': 'success',
            'message': f'Model {version} activated',
            'active_version': version
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Activation failed: {e}")
        return jsonify({'error': str(e)}), 500


@ml_bp.route('/models/<version>', methods=['GET'])
def get_model_details(version):
    """Get details for a specific model version."""
    try:
        from ml_ops.registry.model_registry import ModelRegistry
        from ml_ops.config import config
        
        registry = ModelRegistry(config.registry_path, config.active_path)
        metadata = registry.get_metadata(version)
        
        return jsonify(metadata)
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Error getting model details: {e}")
        return jsonify({'error': str(e)}), 500


@ml_bp.route('/models/compare', methods=['GET'])
def compare_models():
    """
    Compare two model versions.
    
    Query params:
    - v1: First version
    - v2: Second version
    """
    try:
        from ml_ops.registry.model_registry import ModelRegistry
        from ml_ops.config import config
        
        v1 = request.args.get('v1')
        v2 = request.args.get('v2')
        
        if not v1 or not v2:
            return jsonify({'error': 'Both v1 and v2 required'}), 400
        
        registry = ModelRegistry(config.registry_path, config.active_path)
        comparison = registry.compare_versions(v1, v2)
        
        return jsonify(comparison)
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Comparison failed: {e}")
        return jsonify({'error': str(e)}), 500


@ml_bp.route('/models/<version>/rollback', methods=['POST'])
@require_bank_auth
def rollback_model(version):
    """Rollback to a previous model version."""
    try:
        from ml_ops.registry.model_registry import ModelRegistry
        from ml_ops.config import config
        
        registry = ModelRegistry(config.registry_path, config.active_path)
        registry.rollback(version)
        
        return jsonify({
            'status': 'success',
            'message': f'Rolled back to model {version}',
            'active_version': version
        })
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        return jsonify({'error': str(e)}), 500


@ml_bp.route('/datasets', methods=['GET'])
def list_datasets():
    """List all versioned datasets."""
    try:
        from ml_ops.data.versioning import DatasetVersioner
        from ml_ops.config import config
        
        versioner = DatasetVersioner(config.data_path)
        versions = versioner.list_versions()
        
        return jsonify({
            'count': len(versions),
            'versions': versions
        })
        
    except Exception as e:
        logger.error(f"Error listing datasets: {e}")
        return jsonify({'error': str(e)}), 500


@ml_bp.route('/baseline/create', methods=['POST'])
@require_bank_auth
def create_baseline():
    """
    Create drift detection baseline from a dataset.
    
    Request body:
    {
        "dataset_version": "latest"  # or "v1", etc.
    }
    """
    try:
        from ml_ops.monitoring.drift_detector import DriftDetector
        from ml_ops.config import config
        
        data = request.get_json() or {}
        dataset_version = data.get('dataset_version', 'latest')
        
        detector = DriftDetector(config.baseline_path)
        detector.create_baseline_from_dataset(dataset_version)
        
        return jsonify({
            'status': 'success',
            'message': f'Baseline created from dataset {dataset_version}',
            'features': list(detector.baseline.keys()) if detector.baseline else []
        })
        
    except Exception as e:
        logger.error(f"Baseline creation failed: {e}")
        return jsonify({'error': str(e)}), 500
