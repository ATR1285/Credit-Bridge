import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, accuracy_score
import xgboost as xgb
import joblib
import os
from faker import Faker
import random
from datetime import datetime, timedelta

fake = Faker('en_IN')

class CreditMLModel:
    """Enhanced ML model with document-based feature integration"""
    
    def __init__(self):
        self.model = None
        self.scaler = None
        
        # Original behavioral features
        self.behavioral_features = [
            'income_stability_index',
            'expense_control_ratio', 
            'payment_consistency_score',
            'digital_activity_score',
            'savings_discipline_ratio',
            'cashflow_health_score'
        ]
        
        # Document-derived features
        self.document_features = [
            'doc_income_verification_score',
            'doc_expense_ratio_verified',
            'doc_identity_score',
            'doc_financial_health_score',
            'doc_cross_verification_score'
        ]
        
        # Combined feature names
        self.feature_names = self.behavioral_features + self.document_features
        
        self.model_path = 'models/xgboost_model_v2.pkl'
        self.scaler_path = 'models/scaler_v2.pkl'
        
    def calculate_behavioral_features(self, monthly_income, monthly_expenses, income_std_dev=0,
                                    upi_transactions=0, bill_payment_streak=0, 
                                    digital_months=0, savings_amount=0, 
                                    business_revenue=0, business_expenses=0):
        """Calculate the 6 behavioral metrics from form input"""
        
        # 1. Income Stability Index (ISI)
        if monthly_income > 0:
            isi = max(0.0, min(1.0, 1 - (income_std_dev / monthly_income)))
        else:
            isi = 0.0
            
        # 2. Expense Control Ratio (ECR)
        if monthly_income > 0:
            ecr = max(0.0, min(1.0, (monthly_income - monthly_expenses) / monthly_income))
        else:
            ecr = 0.0
            
        # 3. Payment Consistency Score (PCS)
        pcs = max(0.0, min(1.0, bill_payment_streak / 12))
        
        # 4. Digital Activity Score (DAS)
        upi_score = min(upi_transactions / 30, 1)
        digital_score = min(digital_months / 6, 1)
        das = upi_score * digital_score
        
        # 5. Savings Discipline Ratio (SDR)
        if monthly_income > 0:
            sdr = max(0.0, min(1.0, savings_amount / (monthly_income * 3)))
        else:
            sdr = 0.0
            
        # 6. Cashflow Health Score (CHS)
        if business_revenue > 0:
            chs_raw = (business_revenue - business_expenses) / business_revenue
            chs = (chs_raw + 1) / 2
            chs = max(0.0, min(1.0, chs))
        else:
            chs = 0.5
            
        return {
            'income_stability_index': isi,
            'expense_control_ratio': ecr,
            'payment_consistency_score': pcs,
            'digital_activity_score': das,
            'savings_discipline_ratio': sdr,
            'cashflow_health_score': chs
        }
    
    def calculate_document_features(self, doc_features, form_income=0, form_expenses=0):
        """Calculate document-derived features for ML model"""
        features = {
            'doc_income_verification_score': 0.5,
            'doc_expense_ratio_verified': 0.5,
            'doc_identity_score': 0.5,
            'doc_financial_health_score': 0.5,
            'doc_cross_verification_score': 0.5
        }
        
        if not doc_features:
            return features
        
        # 1. Income Verification Score
        doc_income = doc_features.get('doc_monthly_income', 0)
        doc_salary = doc_features.get('doc_verified_salary', 0)
        
        if doc_income > 0 or doc_salary > 0:
            verified_income = max(doc_income, doc_salary)
            if form_income > 0:
                # Compare form income with document income
                ratio = min(verified_income, form_income) / max(verified_income, form_income)
                features['doc_income_verification_score'] = ratio
            else:
                features['doc_income_verification_score'] = 0.7  # Documents provide income
        
        # 2. Expense Ratio Verified
        doc_expenses = doc_features.get('doc_monthly_expenses', 0)
        if doc_income > 0 and doc_expenses > 0:
            expense_ratio = doc_expenses / doc_income
            # Lower expense ratio is better
            features['doc_expense_ratio_verified'] = max(0, min(1, 1 - expense_ratio + 0.3))
        
        # 3. Identity Score
        if doc_features.get('doc_identity_verified', False):
            authenticity = doc_features.get('doc_avg_authenticity', 50)
            features['doc_identity_score'] = authenticity / 100
        
        # 4. Financial Health Score (from bank statement analysis)
        overdrafts = doc_features.get('doc_overdraft_count', 0)
        bounces = doc_features.get('doc_bounce_count', 0)
        upi_freq = doc_features.get('doc_upi_frequency', 0)
        salary_detected = doc_features.get('doc_salary_detected', False)
        
        health_score = 0.5
        # Negative factors
        health_score -= min(0.3, overdrafts * 0.1)
        health_score -= min(0.3, bounces * 0.15)
        # Positive factors
        health_score += min(0.2, upi_freq * 0.01)
        if salary_detected:
            health_score += 0.15
        
        features['doc_financial_health_score'] = max(0, min(1, health_score))
        
        # 5. Cross-Verification Score (from analyzer)
        # This would come from cross_verification results
        doc_count = doc_features.get('doc_count', 0)
        if doc_count >= 3:
            features['doc_cross_verification_score'] = 0.8
        elif doc_count >= 2:
            features['doc_cross_verification_score'] = 0.6
        elif doc_count >= 1:
            features['doc_cross_verification_score'] = 0.4
        
        return features
    
    def calculate_credit_score(self, features_dict, include_documents=True):
        """Calculate credit score with configurable document weighting"""
        
        behavioral_weights = {
            'income_stability_index': 0.18,
            'expense_control_ratio': 0.15,
            'payment_consistency_score': 0.15,
            'digital_activity_score': 0.10,
            'savings_discipline_ratio': 0.12,
            'cashflow_health_score': 0.05
        }
        
        document_weights = {
            'doc_income_verification_score': 0.08,
            'doc_expense_ratio_verified': 0.05,
            'doc_identity_score': 0.04,
            'doc_financial_health_score': 0.05,
            'doc_cross_verification_score': 0.03
        }
        
        # Calculate behavioral score
        behavioral_score = 0
        for feature, weight in behavioral_weights.items():
            behavioral_score += features_dict.get(feature, 0.5) * weight
        
        # Calculate document score
        document_score = 0
        if include_documents:
            for feature, weight in document_weights.items():
                document_score += features_dict.get(feature, 0.5) * weight
        else:
            # If no documents, redistribute weight to behavioral
            document_score = 0.25 * 0.5  # Default middle score
        
        total_score = behavioral_score + document_score
        
        # Normalize to 0-1 range (weights sum to 1.0)
        normalized_score = total_score
        
        # Convert to credit score (300-900 range)
        credit_score = 300 + (normalized_score * 600)
        
        return max(300, min(900, int(credit_score)))
    
    def calculate_confidence_level(self, features_dict, doc_results=None):
        """Calculate confidence level based on data completeness"""
        confidence = 0.5  # Base confidence
        
        # Form data completeness
        behavioral_filled = sum(1 for f in self.behavioral_features if features_dict.get(f, 0) > 0)
        confidence += (behavioral_filled / len(self.behavioral_features)) * 0.2
        
        # Document verification
        if doc_results:
            if doc_results.get('all_mandatory_uploaded', False):
                confidence += 0.15
            
            verified_ratio = doc_results.get('verified_documents', 0) / max(1, doc_results.get('total_documents', 1))
            confidence += verified_ratio * 0.1
            
            # Cross-verification boost
            cross_ver = doc_results.get('cross_verification', {})
            if cross_ver.get('overall_score', 0) > 70:
                confidence += 0.05
        
        return min(1.0, confidence)
    
    def get_risk_category(self, credit_score):
        """Determine risk category from credit score"""
        if credit_score >= 750:
            return "Low Risk"
        elif credit_score >= 600:
            return "Medium Risk"
        else:
            return "High Risk"
    
    def generate_training_data(self, n_samples=5000):
        """Generate synthetic training data including document features"""
        print(f"Generating {n_samples} training samples with document features...")
        
        data = []
        for _ in range(n_samples):
            monthly_income = fake.random_int(min=10000, max=150000)
            expense_ratio = fake.random.uniform(0.6, 0.95)
            monthly_expenses = monthly_income * expense_ratio
            income_std_dev = monthly_income * fake.random.uniform(0, 0.3)
            upi_transactions = fake.random_int(min=0, max=50)
            bill_payment_streak = fake.random_int(min=0, max=12)
            digital_months = fake.random_int(min=0, max=12)
            savings_amount = monthly_income * fake.random.uniform(0, 6)
            
            if fake.boolean(chance_of_getting_true=45):
                business_revenue = fake.random_int(min=15000, max=300000)
                business_expense_ratio = fake.random.uniform(0.5, 0.9)
                business_expenses = business_revenue * business_expense_ratio
            else:
                business_revenue = 0
                business_expenses = 0
            
            # Calculate behavioral features
            behavioral = self.calculate_behavioral_features(
                monthly_income, monthly_expenses, income_std_dev,
                upi_transactions, bill_payment_streak, digital_months,
                savings_amount, business_revenue, business_expenses
            )
            
            # Generate simulated document features
            doc_features = {
                'doc_monthly_income': monthly_income * fake.random.uniform(0.8, 1.2),
                'doc_monthly_expenses': monthly_expenses * fake.random.uniform(0.8, 1.2),
                'doc_verified_salary': monthly_income if fake.boolean(60) else 0,
                'doc_identity_verified': fake.boolean(80),
                'doc_avg_authenticity': fake.random_int(50, 95),
                'doc_overdraft_count': fake.random_int(0, 3),
                'doc_bounce_count': fake.random_int(0, 2),
                'doc_upi_frequency': upi_transactions,
                'doc_salary_detected': fake.boolean(70),
                'doc_count': fake.random_int(2, 6)
            }
            
            document = self.calculate_document_features(doc_features, monthly_income, monthly_expenses)
            
            # Combine all features
            all_features = {**behavioral, **document}
            
            # Calculate score and risk
            credit_score = self.calculate_credit_score(all_features)
            risk_category = self.get_risk_category(credit_score)
            risk_mapping = {"Low Risk": 0, "Medium Risk": 1, "High Risk": 2}
            target = risk_mapping[risk_category]
            
            row = {
                'monthly_income': monthly_income,
                'monthly_expenses': monthly_expenses,
                'credit_score': credit_score,
                'risk_category': risk_category,
                'target': target
            }
            row.update(all_features)
            data.append(row)
        
        df = pd.DataFrame(data)
        print(f"Generated dataset shape: {df.shape}")
        print(f"Risk distribution:\n{df['risk_category'].value_counts()}")
        return df
    
    def train_model(self, n_samples=5000):
        """Train XGBoost model with enhanced features"""
        print("Starting enhanced model training...")
        
        df = self.generate_training_data(n_samples)
        
        X = df[self.feature_names].values
        y = df['target'].values
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        print("Training XGBoost classifier with document features...")
        self.model = xgb.XGBClassifier(
            n_estimators=250,
            max_depth=6,
            learning_rate=0.08,
            subsample=0.9,
            colsample_bytree=0.85,
            objective='multi:softprob',
            num_class=3,
            reg_lambda=1.5,
            eval_metric='mlogloss',
            random_state=42
        )
        
        self.model.fit(X_train_scaled, y_train)
        
        y_pred = self.model.predict(X_test_scaled)
        accuracy = accuracy_score(y_test, y_pred)
        print(f"Model accuracy: {accuracy:.4f}")
        print("\nClassification Report:")
        print(classification_report(y_test, y_pred, 
                                  target_names=['Low Risk', 'Medium Risk', 'High Risk']))
        
        self.save_model()
        print("Enhanced model training completed!")
        
        return accuracy
    
    def save_model(self):
        """Save trained model and scaler"""
        os.makedirs('models', exist_ok=True)
        if self.model is not None and self.scaler is not None:
            joblib.dump(self.model, self.model_path)
            joblib.dump(self.scaler, self.scaler_path)
            print(f"Model saved to {self.model_path}")
    
    def load_model(self):
        """Load existing model and scaler"""
        if os.path.exists(self.model_path) and os.path.exists(self.scaler_path):
            self.model = joblib.load(self.model_path)
            self.scaler = joblib.load(self.scaler_path)
            print("Enhanced model loaded successfully!")
            return True
        else:
            print("Model files not found. Need to train first.")
            return False
    
    def predict(self, features_dict, doc_results=None):
        """Make prediction with document integration"""
        if self.model is None or self.scaler is None:
            # Fall back to rule-based scoring
            credit_score = self.calculate_credit_score(features_dict)
            risk_category = self.get_risk_category(credit_score)
            confidence = self.calculate_confidence_level(features_dict, doc_results)
            
            return {
                'credit_score': credit_score,
                'risk_category': risk_category,
                'repayment_probability': 0.5 + (credit_score - 600) / 600,
                'confidence_level': confidence,
                'model_used': 'Rule-Based (ML model not loaded)',
                'risk_probabilities': {
                    'Low Risk': 0.33 if credit_score >= 750 else 0.2,
                    'Medium Risk': 0.34,
                    'High Risk': 0.33 if credit_score < 600 else 0.2
                }
            }
        
        # Prepare features array
        features_array = np.array([[features_dict.get(f, 0.5) for f in self.feature_names]])
        features_scaled = self.scaler.transform(features_array)
        
        # Predict
        probabilities = self.model.predict_proba(features_scaled)[0]
        predicted_class = self.model.predict(features_scaled)[0]
        
        risk_mapping = {0: "Low Risk", 1: "Medium Risk", 2: "High Risk"}
        predicted_risk = risk_mapping[predicted_class]
        
        # Calculate credit score
        credit_score = self.calculate_credit_score(features_dict)
        
        # Repayment probability
        repayment_probability = 1.0 - probabilities[2]
        
        # Confidence level
        confidence = self.calculate_confidence_level(features_dict, doc_results)
        
        return {
            'credit_score': credit_score,
            'risk_category': predicted_risk,
            'repayment_probability': repayment_probability,
            'confidence_level': confidence,
            'model_used': 'XGBoost with Document Features',
            'risk_probabilities': {
                'Low Risk': probabilities[0],
                'Medium Risk': probabilities[1], 
                'High Risk': probabilities[2]
            }
        }
    
    def get_feature_importance(self):
        """Get feature importance from trained model"""
        if self.model is None:
            return {}
        
        importance = self.model.feature_importances_
        return dict(zip(self.feature_names, importance))



def initialize_model():
    """Initialize and train model if needed"""
    model = CreditMLModel()
    
    if not model.load_model():
        print("Training new enhanced model...")
        model.train_model()
    
    return model