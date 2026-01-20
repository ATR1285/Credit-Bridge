"""
Test suite for CreditBridge application.
Run with: python -m pytest tests/ -v
"""
import unittest
import os
import sys
import tempfile
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db
from app import Employee, User, CreditAssessment, FinancialProfile, Branch
from security import (
    validate_password_strength, generate_secure_password,
    validate_email, validate_phone_number, validate_pan_card,
    sanitize_input, sanitize_filename
)
from utils import format_currency, get_file_size_display, calculate_percentage


class TestConfig:
    """Test configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test-secret-key'


class BaseTestCase(unittest.TestCase):
    """Base test case with database setup"""
    
    def setUp(self):
        """Set up test fixtures"""
        app.config.from_object(TestConfig)
        self.app = app
        self.client = app.test_client()
        
        with app.app_context():
            db.create_all()
            self._seed_test_data()
    
    def tearDown(self):
        """Clean up after tests"""
        with app.app_context():
            db.session.remove()
            db.drop_all()
    
    def _seed_test_data(self):
        """Seed minimal test data"""
        from werkzeug.security import generate_password_hash
        import json
        
        # Create test branch
        branch = Branch(
            branch_code='TEST001',
            branch_name='Test Branch',
            city='Mumbai',
            state='Maharashtra'
        )
        db.session.add(branch)
        db.session.flush()
        
        # Create test employee
        permissions = ['ALL']
        employee = Employee(
            username='test_admin',
            password_hash=generate_password_hash('Test@123'),
            full_name='Test Admin',
            email='admin@test.com',
            employee_code='EMP001',
            role='branch_manager',
            branch_id=branch.id,
            permissions=json.dumps(permissions),
            status='ACTIVE'
        )
        db.session.add(employee)
        db.session.commit()


class TestSecurityUtils(unittest.TestCase):
    """Test security utilities"""
    
    def test_password_validation_success(self):
        """Test valid password"""
        valid, msg = validate_password_strength('SecurePass123!')
        self.assertTrue(valid)
        self.assertIsNone(msg)
    
    def test_password_validation_too_short(self):
        """Test password too short"""
        valid, msg = validate_password_strength('Short1!')
        self.assertFalse(valid)
        self.assertIn('8 characters', msg)
    
    def test_password_validation_no_uppercase(self):
        """Test password without uppercase"""
        valid, msg = validate_password_strength('lowercase123!')
        self.assertFalse(valid)
        self.assertIn('uppercase', msg.lower())
    
    def test_password_validation_no_lowercase(self):
        """Test password without lowercase"""
        valid, msg = validate_password_strength('UPPERCASE123!')
        self.assertFalse(valid)
        self.assertIn('lowercase', msg.lower())
    
    def test_password_validation_no_digit(self):
        """Test password without digit"""
        valid, msg = validate_password_strength('NoDigitsHere!')
        self.assertFalse(valid)
        self.assertIn('digit', msg.lower())
    
    def test_password_validation_no_special(self):
        """Test password without special character"""
        valid, msg = validate_password_strength('NoSpecial123')
        self.assertFalse(valid)
        self.assertIn('special', msg.lower())
    
    def test_generate_secure_password(self):
        """Test secure password generation"""
        password = generate_secure_password(16)
        self.assertEqual(len(password), 16)
        
        # Verify it meets requirements
        valid, msg = validate_password_strength(password)
        self.assertTrue(valid)
    
    def test_email_validation(self):
        """Test email validation"""
        self.assertTrue(validate_email('test@example.com'))
        self.assertTrue(validate_email('user.name@domain.co.in'))
        self.assertFalse(validate_email('invalid.email'))
        self.assertFalse(validate_email('@example.com'))
        self.assertFalse(validate_email('test@'))
        self.assertFalse(validate_email(''))
    
    def test_phone_validation(self):
        """Test phone number validation"""
        self.assertTrue(validate_phone_number('9876543210'))
        self.assertTrue(validate_phone_number('8765432109'))
        self.assertFalse(validate_phone_number('1234567890'))  # Starts with 1
        self.assertFalse(validate_phone_number('98765'))  # Too short
        self.assertFalse(validate_phone_number(''))
    
    def test_pan_validation(self):
        """Test PAN card validation"""
        self.assertTrue(validate_pan_card('ABCDE1234F'))
        self.assertTrue(validate_pan_card('XYZAB9876C'))
        self.assertFalse(validate_pan_card('ABC123'))  # Too short
        self.assertFalse(validate_pan_card('12345ABCDE'))  # Wrong format
        self.assertFalse(validate_pan_card(''))
    
    def test_sanitize_input(self):
        """Test input sanitization"""
        self.assertEqual(sanitize_input('  Normal text  '), 'Normal text')
        self.assertEqual(sanitize_input('Text\x00with\x00nulls'), 'Textwithnulls')
        self.assertEqual(sanitize_input('a' * 100, max_length=50), 'a' * 50)
    
    def test_sanitize_filename(self):
        """Test filename sanitization"""
        self.assertEqual(sanitize_filename('normal_file.pdf'), 'normal_file.pdf')
        self.assertEqual(sanitize_filename('../../../etc/passwd'), '..........etcpasswd')
        self.assertEqual(sanitize_filename('file<>name.txt'), 'filename.txt')


class TestUtilities(unittest.TestCase):
    """Test utility functions"""
    
    def test_format_currency(self):
        """Test currency formatting"""
        self.assertEqual(format_currency(1000), '₹1,000.00')
        self.assertEqual(format_currency(100000), '₹1,00,000.00')
        self.assertEqual(format_currency(1000000), '₹10,00,000.00')
        self.assertEqual(format_currency(0), '₹0.00')
    
    def test_file_size_display(self):
        """Test file size formatting"""
        self.assertEqual(get_file_size_display(0), '0 B')
        self.assertEqual(get_file_size_display(1024), '1.00 KB')
        self.assertEqual(get_file_size_display(1048576), '1.00 MB')
        self.assertEqual(get_file_size_display(1073741824), '1.00 GB')
    
    def test_calculate_percentage(self):
        """Test percentage calculation"""
        self.assertEqual(calculate_percentage(25, 100), 25.0)
        self.assertEqual(calculate_percentage(50, 200), 25.0)
        self.assertEqual(calculate_percentage(0, 100), 0.0)
        self.assertEqual(calculate_percentage(10, 0), 0.0)  # Safe division


class TestModels(BaseTestCase):
    """Test database models"""
    
    def test_create_employee(self):
        """Test employee creation"""
        with self.app.app_context():
            from werkzeug.security import generate_password_hash
            import json
            
            branch = Branch.query.first()
            employee = Employee(
                username='test_user',
                password_hash=generate_password_hash('Test@123'),
                full_name='Test User',
                email='test@example.com',
                employee_code='EMP002',
                role='loan_officer',
                branch_id=branch.id,
                permissions=json.dumps(['CREATE_ASSESSMENT']),
                status='ACTIVE'
            )
            db.session.add(employee)
            db.session.commit()
            
            self.assertIsNotNone(employee.id)
            self.assertEqual(employee.username, 'test_user')
            self.assertEqual(employee.role, 'loan_officer')
    
    def test_create_user(self):
        """Test user (applicant) creation"""
        with self.app.app_context():
            user = User(
                name='John Doe',
                phone='9876543210',
                email='john@example.com',
                pan_card='ABCDE1234F'
            )
            db.session.add(user)
            db.session.commit()
            
            self.assertIsNotNone(user.id)
            self.assertEqual(user.name, 'John Doe')
    
    def test_create_assessment(self):
        """Test assessment creation"""
        with self.app.app_context():
            # Create user
            user = User(
                name='Test User',
                phone='9876543210',
                email='test@test.com'
            )
            db.session.add(user)
            db.session.flush()
            
            # Create profile
            profile = FinancialProfile(
                user_id=user.id,
                monthly_income=50000,
                monthly_expenses=30000
            )
            db.session.add(profile)
            db.session.flush()
            
            # Create assessment
            import json
            assessment = CreditAssessment(
                user_id=user.id,
                profile_id=profile.id,
                credit_score=750,
                risk_category='Low',
                repayment_probability=0.85,
                features_json=json.dumps({'test': 'data'}),
                status='approved'
            )
            db.session.add(assessment)
            db.session.commit()
            
            self.assertIsNotNone(assessment.id)
            self.assertEqual(assessment.credit_score, 750)
            self.assertEqual(assessment.risk_category, 'Low')


class TestRoutes(BaseTestCase):
    """Test application routes"""
    
    def test_landing_page(self):
        """Test landing page loads"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
    
    def test_bank_login_page(self):
        """Test bank login page loads"""
        response = self.client.get('/bank/login')
        self.assertEqual(response.status_code, 200)
    
    def test_bank_login_success(self):
        """Test successful bank login"""
        response = self.client.post('/bank/login', data={
            'username': 'test_admin',
            'password': 'Test@123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
    
    def test_bank_login_failure(self):
        """Test failed bank login"""
        response = self.client.post('/bank/login', data={
            'username': 'test_admin',
            'password': 'WrongPassword'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        # Should remain on login page
    
    def test_unauthorized_access(self):
        """Test accessing protected route without login"""
        response = self.client.get('/bank/dashboard')
        self.assertEqual(response.status_code, 302)  # Redirect to login


class TestMLModel(BaseTestCase):
    """Test ML model functionality"""
    
    def test_calculate_behavioral_features(self):
        """Test behavioral feature calculation"""
        from ml_model import CreditMLModel
        
        model = CreditMLModel()
        features = model.calculate_behavioral_features(
            monthly_income=50000,
            monthly_expenses=30000,
            income_std_dev=5000,
            upi_transactions=50,
            bill_payment_streak=12,
            digital_months=24,
            savings_amount=100000
        )
        
        self.assertIsInstance(features, dict)
        self.assertIn('income_stability_index', features)
        self.assertIn('expense_control_ratio', features)
        self.assertIn('payment_consistency_score', features)
        
        # Check value ranges (0-1)
        for key, value in features.items():
            self.assertGreaterEqual(value, 0)
            self.assertLessEqual(value, 1)


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestSecurityUtils))
    suite.addTests(loader.loadTestsFromTestCase(TestUtilities))
    suite.addTests(loader.loadTestsFromTestCase(TestModels))
    suite.addTests(loader.loadTestsFromTestCase(TestRoutes))
    suite.addTests(loader.loadTestsFromTestCase(TestMLModel))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
