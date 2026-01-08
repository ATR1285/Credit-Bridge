import os
import re
import json
import uuid
import tempfile
from datetime import datetime
import pdfplumber
from PIL import Image
import cv2
import numpy as np
import pytesseract
import google.generativeai as genai
from werkzeug.utils import secure_filename

class DocumentAnalyzer:
    """Enhanced document analyzer with content-based extraction for ML scoring"""
    
    def __init__(self, gemini_api_key=None):
        self.allowed_extensions = {'pdf', 'jpg', 'jpeg', 'png'}
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        
        # Document categories
        self.mandatory_docs = ['aadhaar', 'pan', 'bank_statement']
        self.optional_docs = [
            'salary_slip', 'itr', 'utility_bill', 'gst', 'property',
            'rent', 'investment', 'loan', 'business', 'employment'
        ]
        
        # Initialize Gemini AI if API key provided
        if gemini_api_key:
            try:
                genai.configure(api_key=gemini_api_key)
                # Use gemini-1.5-flash for both text and vision
                self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
                self.gemini_available = True
                print("Gemini AI initialized successfully")
            except Exception as e:
                print(f"Gemini AI initialization failed: {e}")
                self.gemini_available = False
        else:
            self.gemini_available = False
            print("Gemini API key not provided - using heuristic analysis only")
    
    def validate_file(self, file):
        """Validate uploaded file"""
        if not file:
            return False, "No file provided"
        
        if file.filename == '':
            return False, "No file selected"
        
        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        if file_ext not in self.allowed_extensions:
            return False, f"File type not allowed. Use: {', '.join(self.allowed_extensions)}"
        
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > self.max_file_size:
            return False, f"File too large. Maximum size: {self.max_file_size // (1024*1024)}MB"
        
        return True, "Valid file"
    
    def save_file(self, file, upload_folder):
        """Save file with secure filename"""
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
        file_path = os.path.join(upload_folder, unique_filename)
        os.makedirs(upload_folder, exist_ok=True)
        file.save(file_path)
        return file_path, os.path.getsize(file_path)
    
    def extract_text_from_pdf(self, file_path):
        """Extract text from PDF using pdfplumber"""
        try:
            text = ""
            with pdfplumber.open(file_path) as pdf:
                pages_to_process = min(10, len(pdf.pages))
                for i in range(pages_to_process):
                    page = pdf.pages[i]
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text.strip()
        except Exception as e:
            print(f"PDF text extraction error: {e}")
            return ""
    
    def extract_text_from_image(self, file_path):
        """Extract text from image using OCR"""
        try:
            image = cv2.imread(file_path)
            if image is None:
                return ""
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            denoised = cv2.fastNlMeansDenoising(gray)
            _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            text = pytesseract.image_to_string(thresh, config='--psm 6')
            return text.strip()
        except Exception as e:
            print(f"OCR text extraction error: {e}")
            return ""
    
    def analyze_bank_statement(self, text):
        """Extract financial features from bank statement"""
        features = {
            'avg_monthly_balance': 0,
            'income_consistency': 0.5,
            'expense_ratio': 0.7,
            'overdraft_count': 0,
            'bounce_count': 0,
            'upi_frequency': 0,
            'emi_payments_detected': False,
            'salary_credit_detected': False,
            'transaction_count': 0
        }
        
        if not text:
            return features
        
        text_lower = text.lower()
        
        # Extract amounts (INR format)
        amount_pattern = r'(?:₹|rs\.?|inr)\s*[\d,]+(?:\.\d{2})?|\b\d{2,},?\d{3,}(?:\.\d{2})?\b'
        amounts = re.findall(amount_pattern, text_lower)
        
        amount_values = []
        for amount_str in amounts:
            clean_amount = re.sub(r'[^\\d.]', '', amount_str)
            try:
                val = float(clean_amount)
                if val > 100:  # Filter out small numbers
                    amount_values.append(val)
            except:
                continue
        
        if amount_values:
            features['avg_monthly_balance'] = np.mean(amount_values)
            features['transaction_count'] = len(amount_values)
            
            # Calculate income consistency (lower std dev = more consistent)
            if len(amount_values) > 3:
                std_dev = np.std(amount_values)
                mean_val = np.mean(amount_values)
                if mean_val > 0:
                    cv = std_dev / mean_val  # Coefficient of variation
                    features['income_consistency'] = max(0, min(1, 1 - cv))
        
        # Salary indicators
        salary_keywords = ['salary', 'payroll', 'sal cr', 'sal credit', 'wages', 'neft sal']
        features['salary_credit_detected'] = any(kw in text_lower for kw in salary_keywords)
        
        # Negative indicators
        overdraft_keywords = ['od ', 'overdraft', 'od int']
        features['overdraft_count'] = sum(1 for kw in overdraft_keywords if kw in text_lower)
        
        bounce_keywords = ['bounced', 'returned', 'insufficient', 'reversal', 'chargeback']
        features['bounce_count'] = sum(1 for kw in bounce_keywords if kw in text_lower)
        
        # UPI frequency
        upi_keywords = ['upi', 'imps', 'paytm', 'phonepe', 'gpay']
        features['upi_frequency'] = sum(text_lower.count(kw) for kw in upi_keywords)
        
        # EMI detection
        emi_keywords = ['emi', 'loan emi', 'auto debit', 'nach']
        features['emi_payments_detected'] = any(kw in text_lower for kw in emi_keywords)
        
        return features
    
    def analyze_salary_slip(self, text):
        """Extract salary information from salary slip"""
        features = {
            'monthly_salary': 0,
            'employer_detected': False,
            'deductions_ratio': 0,
            'verified': False
        }
        
        if not text:
            return features
        
        text_lower = text.lower()
        
        # Salary amount extraction
        salary_patterns = [
            r'(?:net\s*(?:pay|salary)|take\s*home|gross\s*salary)[:\s]*(?:₹|rs\.?|inr)?\s*([\d,]+)',
            r'(?:₹|rs\.?|inr)\s*([\d,]+)\s*(?:net|gross|total)',
        ]
        
        for pattern in salary_patterns:
            matches = re.findall(pattern, text_lower)
            if matches:
                try:
                    salary = float(matches[0].replace(',', ''))
                    if salary > 5000:  # Reasonable salary threshold
                        features['monthly_salary'] = salary
                        features['verified'] = True
                        break
                except:
                    continue
        
        # Employer detection
        employer_keywords = ['company', 'employer', 'organisation', 'organization', 'pvt ltd', 'limited']
        features['employer_detected'] = any(kw in text_lower for kw in employer_keywords)
        
        return features
    
    def analyze_identity_document(self, text, doc_type):
        """Verify identity documents (Aadhaar/PAN)"""
        features = {
            'name_extracted': None,
            'dob_extracted': None,
            'document_number': None,
            'authenticity_score': 50,
            'tampering_risk': 'Unknown'
        }
        
        if not text:
            return features
        
        text_upper = text.upper()
        
        if doc_type == 'aadhaar':
            # Aadhaar pattern
            aadhaar_pattern = r'\d{4}\s*\d{4}\s*\d{4}'
            matches = re.findall(aadhaar_pattern, text)
            if matches:
                features['document_number'] = matches[0].replace(' ', '')[-4:]  # Last 4 digits only
                features['authenticity_score'] = 70
                features['tampering_risk'] = 'Low'
            
        elif doc_type == 'pan':
            # PAN pattern
            pan_pattern = r'[A-Z]{5}\d{4}[A-Z]'
            matches = re.findall(pan_pattern, text_upper)
            if matches:
                features['document_number'] = matches[0]
                features['authenticity_score'] = 70
                features['tampering_risk'] = 'Low'
        
        # Name extraction
        name_pattern = r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+'
        names = re.findall(name_pattern, text)
        if names:
            features['name_extracted'] = names[0]
        
        # DOB extraction
        dob_pattern = r'\d{1,2}[/-]\d{1,2}[/-]\d{4}'
        dobs = re.findall(dob_pattern, text)
        if dobs:
            features['dob_extracted'] = dobs[0]
        
        return features
    
    def analyze_with_gemini(self, file_path, document_type, extracted_text=""):
        """Enhanced Gemini analysis for document content extraction"""
        if not self.gemini_available:
            return self._get_fallback_analysis(document_type, extracted_text)
        
        try:
            # Customize prompt based on document type
            if document_type == 'bank_statement':
                prompt = f"""
                Analyze this bank statement and extract the following in JSON format:
                {{
                    "avg_monthly_balance": <estimated average balance in INR>,
                    "monthly_credits": <estimated monthly income/credits in INR>,
                    "monthly_debits": <estimated monthly expenses/debits in INR>,
                    "transaction_count": <approximate number of transactions>,
                    "salary_detected": <true/false>,
                    "overdraft_instances": <count>,
                    "bounce_instances": <count>,
                    "emi_payments": <count>,
                    "upi_transactions": <count>,
                    "financial_health": "Good" | "Average" | "Poor",
                    "authenticity_score": <0-100>,
                    "notes": "<brief analysis>"
                }}
                
                Text content: {extracted_text[:4000]}
                """
            elif document_type in ['aadhaar', 'pan']:
                prompt = f"""
                Analyze this {document_type.upper()} card image/document and verify:
                {{
                    "document_type": "{document_type}",
                    "name": "<extracted name or null>",
                    "document_number_last4": "<last 4 digits only>",
                    "dob": "<date of birth if visible>",
                    "authenticity_score": <0-100>,
                    "tampering_detected": <true/false>,
                    "quality_issues": ["list of issues"],
                    "notes": "<brief verification notes>"
                }}
                
                Text content: {extracted_text[:2000]}
                """
            elif document_type == 'salary_slip':
                prompt = f"""
                Analyze this salary slip and extract:
                {{
                    "gross_salary": <amount in INR>,
                    "net_salary": <amount in INR>,
                    "employer_name": "<name or null>",
                    "employee_name": "<name or null>",
                    "deductions": <total deductions in INR>,
                    "month_year": "<month and year>",
                    "authenticity_score": <0-100>,
                    "notes": "<brief analysis>"
                }}
                
                Text content: {extracted_text[:2000]}
                """
            else:
                prompt = f"""
                Analyze this {document_type} document and extract key financial information in JSON:
                {{
                    "document_type": "{document_type}",
                    "key_amount": <primary amount if any>,
                    "authenticity_score": <0-100>,
                    "relevant_data": {{}},
                    "notes": "<brief analysis>"
                }}
                
                Text content: {extracted_text[:2000]}
                """
            
            # Check if file is image or PDF
            file_ext = file_path.lower().split('.')[-1]
            
            if file_ext in ['jpg', 'jpeg', 'png']:
                # Use vision capability
                image = Image.open(file_path)
                response = self.gemini_model.generate_content([prompt, image])
            else:
                response = self.gemini_model.generate_content(prompt)
            
            response_text = response.text.strip()
            
            # Extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                analysis = json.loads(json_str)
                return analysis
            else:
                return self._get_fallback_analysis(document_type, extracted_text)
                
        except Exception as e:
            print(f"Gemini analysis error: {e}")
            return self._get_fallback_analysis(document_type, extracted_text)
    
    def _get_fallback_analysis(self, document_type, extracted_text):
        """Fallback analysis when Gemini is unavailable"""
        if document_type == 'bank_statement':
            features = self.analyze_bank_statement(extracted_text)
            return {
                'avg_monthly_balance': features['avg_monthly_balance'],
                'monthly_credits': features['avg_monthly_balance'] * 0.4,
                'monthly_debits': features['avg_monthly_balance'] * 0.6,
                'transaction_count': features['transaction_count'],
                'salary_detected': features['salary_credit_detected'],
                'overdraft_instances': features['overdraft_count'],
                'bounce_instances': features['bounce_count'],
                'emi_payments': 1 if features['emi_payments_detected'] else 0,
                'upi_transactions': features['upi_frequency'],
                'financial_health': 'Average',
                'authenticity_score': 65,
                'notes': 'Heuristic analysis only - Gemini AI unavailable'
            }
        elif document_type in ['aadhaar', 'pan']:
            features = self.analyze_identity_document(extracted_text, document_type)
            return {
                'document_type': document_type,
                'name': features['name_extracted'],
                'document_number_last4': features['document_number'],
                'dob': features['dob_extracted'],
                'authenticity_score': features['authenticity_score'],
                'tampering_detected': features['tampering_risk'] == 'High',
                'quality_issues': [],
                'notes': 'Heuristic analysis only'
            }
        elif document_type == 'salary_slip':
            features = self.analyze_salary_slip(extracted_text)
            return {
                'gross_salary': features['monthly_salary'],
                'net_salary': features['monthly_salary'] * 0.85,
                'employer_name': None,
                'employee_name': None,
                'deductions': features['monthly_salary'] * 0.15,
                'month_year': None,
                'authenticity_score': 60 if features['verified'] else 40,
                'notes': 'Heuristic analysis only'
            }
        else:
            return {
                'document_type': document_type,
                'key_amount': 0,
                'authenticity_score': 50,
                'relevant_data': {},
                'notes': 'Minimal analysis - document type not fully supported'
            }
    
    def cross_verify_documents(self, document_analyses):
        """Cross-verify data across multiple documents"""
        verification = {
            'name_consistency': 0,
            'income_consistency': 0,
            'overall_score': 50,
            'discrepancies': []
        }
        
        names = []
        incomes = []
        
        for doc_type, analysis in document_analyses.items():
            # Collect names
            if isinstance(analysis, dict):
                if 'name' in analysis and analysis['name']:
                    names.append(analysis['name'].lower().strip())
                if 'employee_name' in analysis and analysis['employee_name']:
                    names.append(analysis['employee_name'].lower().strip())
                
                # Collect income data
                if 'monthly_credits' in analysis:
                    incomes.append(analysis['monthly_credits'])
                if 'net_salary' in analysis:
                    incomes.append(analysis['net_salary'])
        
        # Check name consistency
        if len(names) >= 2:
            # Simple check - first word of each name should match
            first_names = [n.split()[0] if n else '' for n in names]
            if len(set(first_names)) == 1:
                verification['name_consistency'] = 100
            else:
                verification['name_consistency'] = 50
                verification['discrepancies'].append('Name mismatch across documents')
        
        # Check income consistency
        if len(incomes) >= 2:
            mean_income = np.mean(incomes)
            std_income = np.std(incomes)
            if mean_income > 0:
                cv = std_income / mean_income
                if cv < 0.2:
                    verification['income_consistency'] = 100
                elif cv < 0.5:
                    verification['income_consistency'] = 70
                else:
                    verification['income_consistency'] = 40
                    verification['discrepancies'].append('Significant income discrepancy across documents')
        
        # Calculate overall score
        scores = [verification['name_consistency'], verification['income_consistency']]
        verification['overall_score'] = np.mean([s for s in scores if s > 0]) if scores else 50
        
        return verification
    
    def analyze_document(self, file, document_type, upload_folder):
        """Complete document analysis pipeline with content extraction"""
        is_valid, message = self.validate_file(file)
        if not is_valid:
            return {
                'success': False,
                'error': message
            }
        
        try:
            file_path, file_size = self.save_file(file, upload_folder)
            
            # Extract text
            file_ext = file.filename.rsplit('.', 1)[1].lower()
            if file_ext == 'pdf':
                extracted_text = self.extract_text_from_pdf(file_path)
            else:
                extracted_text = self.extract_text_from_image(file_path)
            
            # Get AI analysis with extracted features
            ai_analysis = self.analyze_with_gemini(file_path, document_type, extracted_text)
            
            # Determine verification status
            authenticity_score = ai_analysis.get('authenticity_score', 50)
            if authenticity_score >= 70:
                verified_status = 'verified'
            elif authenticity_score >= 40:
                verified_status = 'pending'
            else:
                verified_status = 'rejected'
            
            return {
                'success': True,
                'file_path': file_path,
                'file_size': file_size,
                'document_type': document_type,
                'verified_status': verified_status,
                'authenticity_score': authenticity_score,
                'extracted_features': ai_analysis,
                'extracted_text_length': len(extracted_text),
                'processing_timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            print(f"Document analysis error: {e}")
            return {
                'success': False,
                'error': f'Analysis failed: {str(e)}'
            }
    
    def analyze_all_documents(self, files_dict, upload_folder):
        """Analyze all uploaded documents and combine results"""
        results = {
            'mandatory': {},
            'optional': {},
            'all_mandatory_uploaded': False,
            'total_documents': 0,
            'verified_documents': 0,
            'combined_features': {},
            'cross_verification': {}
        }
        
        all_analyses = {}
        
        # Process each document
        for field_name, file in files_dict.items():
            if file and file.filename:
                # Determine document type from field name
                doc_type = field_name.replace('doc_', '')
                
                analysis = self.analyze_document(file, doc_type, upload_folder)
                
                if analysis['success']:
                    if doc_type in self.mandatory_docs:
                        results['mandatory'][doc_type] = analysis
                    else:
                        results['optional'][doc_type] = analysis
                    
                    all_analyses[doc_type] = analysis.get('extracted_features', {})
                    results['total_documents'] += 1
                    
                    if analysis['verified_status'] == 'verified':
                        results['verified_documents'] += 1
        
        # Check if all mandatory documents are uploaded
        results['all_mandatory_uploaded'] = all(
            doc in results['mandatory'] for doc in self.mandatory_docs
        )
        
        # Perform cross-verification
        if len(all_analyses) >= 2:
            results['cross_verification'] = self.cross_verify_documents(all_analyses)
        
        # Combine extracted features for ML
        results['combined_features'] = self._combine_features(all_analyses)
        
        return results
    
    def _combine_features(self, all_analyses):
        """Combine extracted features from all documents for ML input"""
        features = {
            # Bank statement features
            'doc_avg_balance': 0,
            'doc_monthly_income': 0,
            'doc_monthly_expenses': 0,
            'doc_transaction_count': 0,
            'doc_overdraft_count': 0,
            'doc_bounce_count': 0,
            'doc_upi_frequency': 0,
            'doc_salary_detected': False,
            'doc_emi_payments': 0,
            'doc_income_consistency': 0.5,
            
            # Salary features  
            'doc_verified_salary': 0,
            
            # Verification features
            'doc_identity_verified': False,
            'doc_avg_authenticity': 50,
            
            # Overall
            'doc_count': len(all_analyses)
        }
        
        authenticity_scores = []
        
        for doc_type, analysis in all_analyses.items():
            if not isinstance(analysis, dict):
                continue
                
            if doc_type == 'bank_statement':
                features['doc_avg_balance'] = analysis.get('avg_monthly_balance', 0)
                features['doc_monthly_income'] = analysis.get('monthly_credits', 0)
                features['doc_monthly_expenses'] = analysis.get('monthly_debits', 0)
                features['doc_transaction_count'] = analysis.get('transaction_count', 0)
                features['doc_overdraft_count'] = analysis.get('overdraft_instances', 0)
                features['doc_bounce_count'] = analysis.get('bounce_instances', 0)
                features['doc_upi_frequency'] = analysis.get('upi_transactions', 0)
                features['doc_salary_detected'] = analysis.get('salary_detected', False)
                features['doc_emi_payments'] = analysis.get('emi_payments', 0)
                
                # Calculate income consistency from income/expense data
                monthly_income = analysis.get('monthly_credits', 0)
                monthly_expenses = analysis.get('monthly_debits', 0)
                if monthly_income > 0:
                    expense_ratio = monthly_expenses / monthly_income if monthly_income else 1
                    # Lower expense ratio = better income consistency
                    features['doc_income_consistency'] = max(0, min(1, 1 - (expense_ratio * 0.5)))
            
            elif doc_type == 'salary_slip':
                features['doc_verified_salary'] = analysis.get('net_salary', 0)
            
            elif doc_type in ['aadhaar', 'pan']:
                if analysis.get('authenticity_score', 0) >= 60:
                    features['doc_identity_verified'] = True
            
            if 'authenticity_score' in analysis:
                authenticity_scores.append(analysis['authenticity_score'])
        
        if authenticity_scores:
            features['doc_avg_authenticity'] = np.mean(authenticity_scores)
        
        return features