# 🏦 CreditBridge - AI-Powered Credit Assessment Platform

**Version 3.0** | Professional Bank-Grade Credit Scoring System

CreditBridge is a comprehensive credit assessment platform that uses machine learning and AI to evaluate creditworthiness based on behavioral analysis, transaction patterns, and document verification.

---

## ✨ Key Features

### 🤖 AI-Powered Assessment
- **XGBoost ML Model** with 94.2% accuracy
- Behavioral analysis of 6 key financial metrics
- Real-time transaction pattern recognition
- Predictive default risk modeling

### 📊 Dual Portal System
- **Public Portal**: Self-service credit assessment for individuals
- **Bank Portal**: Multi-branch management system for financial institutions

### 📄 Bank-Grade PDF Reports
- **Professional 10-page reports** with charts and visualizations
- Score gauge, radar charts, bell curves, and projections
- Security features: watermarks, QR codes, SHA-256 hashes
- Print-ready quality (300 DPI)
- **NO document points system** - authenticity verification only

### 🔍 Document Verification
- **Google Gemini AI** powered document analysis
- Authenticity scoring for Aadhaar, PAN, Bank Statements, Salary Slips
- OCR and pattern recognition
- Fraud detection algorithms

### 🏢 Multi-Branch Banking
- Role-based access control (8 roles)
- Branch-specific dashboards
- Team management and audit logs
- Workflow automation

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Google Gemini API key
- Modern web browser

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd Creditbridge
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Set up environment variables**
Create a `.env` file:
```env
GEMINI_API_KEY=your_gemini_api_key_here
SECRET_KEY=your_secret_key_here
```

4. **Run the application**
```bash
python app.py
```

5. **Access the application**
- Public Portal: http://localhost:5000
- Bank Portal: http://localhost:5000/bank/login

---

## 👥 Default Login Credentials

### Bank Portal Users
All passwords: `pass123`

| Username | Role | Branch |
|----------|------|--------|
| `admin` | Head of Bank | All Branches |
| `manager1` | Branch Manager | Mumbai |
| `manager2` | Branch Manager | Andheri |
| `credit` | Credit Manager | Mumbai |
| `loan1` | Loan Officer | Mumbai |
| `loan2` | Loan Officer | Andheri |
| `analyst1` | Credit Analyst | Mumbai |
| `analyst2` | Credit Analyst | Andheri |

---

## 📊 Credit Scoring System

### Score Range: 300-900

| Score | Risk Category | Description |
|-------|---------------|-------------|
| 750-900 | Low Risk | Excellent creditworthiness |
| 650-749 | Low-Medium Risk | Good credit profile |
| 550-649 | Medium Risk | Fair credit standing |
| 300-549 | High Risk | Needs improvement |

### Behavioral Metrics (6 Key Factors)

1. **Income Stability** (25%)
   - Consistency of income over time
   - Volatility analysis
   - Growth trends

2. **Expense Control** (20%)
   - Expense-to-income ratio
   - Discretionary spending patterns
   - Budget discipline

3. **Payment Consistency** (20%)
   - On-time payment history
   - Regular bill payments
   - Auto-pay usage

4. **Digital Activity** (15%)
   - Digital banking adoption
   - UPI transaction frequency
   - Modern payment methods

5. **Savings Discipline** (10%)
   - Savings rate
   - Emergency fund building
   - Investment activity

6. **Cashflow Health** (10%)
   - Income vs expenses balance
   - Cash reserves
   - Financial buffer

### Score Composition
- **Behavioral Analysis**: 75%
- **Document Authenticity**: 15%
- **Transaction Patterns**: 10%

---

## 📄 PDF Report Features

### 10-Page Professional Report

**Page 1: Cover Page**
- Credit score with circular gauge
- Risk category badge
- Report metadata and validity

**Page 2: Executive Dashboard**
- Key metrics at a glance
- Applicant profile
- Assessment workflow

**Page 3: Behavioral Analysis**
- Radar chart of 6 metrics
- Score breakdown table
- Methodology explanation

**Page 4: Strengths & Improvements**
- Identified strengths
- Areas for improvement
- Actionable recommendations

**Page 5: Improvement Roadmap**
- 12-month projection graph
- 3-phase improvement plan
- Score targets and actions

**Page 6: Loan Recommendations**
- Personalized loan options
- Interest rates and EMI
- Eligibility assessment

**Page 7: Peer Comparison**
- Bell curve distribution
- Percentile ranking
- Metric-by-metric comparison

**Page 8: AI Insights**
- Income pattern analysis
- Spending behavior
- Fraud risk assessment
- Predictive analytics

**Page 9: Document Verification**
- Authenticity scores
- Verification status
- **NO points system** - documents verified for authenticity only

**Page 10: Disclaimers & Compliance**
- Legal disclaimers
- QR code for verification
- SHA-256 report hash

### Security Features
- ✅ Watermarks on all pages
- ✅ QR code verification
- ✅ SHA-256 tamper detection
- ✅ Headers and footers
- ✅ 30-day validity period

---

## 🏗️ Architecture

### Technology Stack

**Backend:**
- Flask 3.0.3
- SQLAlchemy (ORM)
- SQLite database

**Machine Learning:**
- XGBoost
- Scikit-learn
- NumPy, Pandas

**AI & Document Processing:**
- Google Gemini AI
- Pillow (image processing)

**PDF Generation:**
- ReportLab (professional reports)
- Matplotlib (charts)
- QRCode (verification)

**Frontend:**
- HTML5, CSS3, JavaScript
- Bootstrap 5
- Chart.js

### Project Structure
```
Creditbridge/
├── app.py                          # Main Flask application
├── ml_model.py                     # XGBoost credit scoring model
├── document_analyzer.py            # Gemini AI document verification
├── bank_grade_pdf_generator.py     # Professional PDF reports
├── pdf_generator.py                # Legacy PDF generator
├── simple_pdf_generator.py         # Simple PDF fallback
├── templates/                      # HTML templates
│   ├── public/                     # Public portal templates
│   └── bank/                       # Bank portal templates
├── static/                         # CSS, JS, images
├── models/                         # Trained ML models
├── uploads/                        # Document uploads
└── reports/                        # Generated PDF reports
```

---

## 🔐 Security & Privacy

### Data Protection
- 256-bit encryption for sensitive data
- Secure password hashing (Werkzeug)
- Session management with secure cookies
- CORS protection

### Document Security
- Temporary file cleanup after processing
- Automatic deletion after 90 days
- No third-party data sharing
- GDPR compliant

### Access Control
- Role-based permissions
- Branch-level data isolation
- Session timeout protection
- Audit logging

---

## 📈 Usage Guide

### Public Portal Flow

1. **Register/Login**
   - Create account or use Google OAuth
   - Provide basic information

2. **Start Assessment**
   - Answer financial behavior questions
   - Upload documents (optional)
   - Submit for AI analysis

3. **View Results**
   - Credit score and risk category
   - Detailed behavioral breakdown
   - Improvement recommendations

4. **Download Report**
   - Professional 10-page PDF
   - Shareable with lenders
   - Valid for 30 days

### Bank Portal Flow

1. **Login**
   - Use bank employee credentials
   - Access role-specific dashboard

2. **Create Assessment**
   - Enter customer details
   - Upload documents
   - Process through AI

3. **Review & Approve**
   - Verify AI analysis
   - Add manual notes
   - Approve or reject

4. **Generate Report**
   - Bank-grade PDF report
   - Include loan recommendations
   - Share with customer

---

## 🎯 API Endpoints

### Public Portal
- `GET /` - Home page
- `POST /register` - User registration
- `POST /login` - User login
- `GET /public/dashboard` - User dashboard
- `POST /public/start-assessment` - Begin assessment
- `GET /public/result/<id>` - View results
- `GET /public/download-report/<id>` - Download PDF

### Bank Portal
- `POST /bank/login` - Bank employee login
- `GET /bank/dashboard` - Role-specific dashboard
- `POST /bank/create-assessment` - Create new assessment
- `GET /bank/assessment/<id>` - View assessment details
- `GET /bank/assessment/<id>/download_pdf` - Download PDF
- `GET /bank/applications` - View all applications
- `GET /bank/team` - Team management
- `GET /bank/audit-logs` - Audit trail

---

## 🧪 Testing

### Sample Test Cases

**Test Credit Scores:**
- High Score (810): Anita Desai
- Medium Score (650): Raj Kumar
- Low Score (450): Test User

**Test Documents:**
- Upload Aadhaar, PAN, Bank Statement
- Verify AI authenticity scoring
- Check fraud detection

**Test PDF Generation:**
- Download from public portal
- Download from bank portal
- Verify all 10 pages render
- Check charts display correctly

---

## 🐛 Troubleshooting

### Common Issues

**PDF Generation Fails:**
```
Error: "tempfile not defined"
Solution: Ensure tempfile is imported in app.py
```

**Gemini API Error:**
```
Error: "API key not found"
Solution: Set GEMINI_API_KEY in .env file
```

**Database Error:**
```
Error: "Table not found"
Solution: Delete creditbridge.db and restart app.py
```

**Chart Generation Error:**
```
Error: "scipy not installed"
Solution: pip install scipy qrcode[pil]
```

---

## 📦 Dependencies

### Core Dependencies
```
Flask==3.0.3
Flask-SQLAlchemy==3.1.1
Flask-CORS==4.0.0
Werkzeug==3.0.3
```

### ML & AI
```
xgboost==2.0.3
scikit-learn==1.4.2
numpy==1.26.4
pandas==2.2.2
google-generativeai==0.3.2
```

### PDF & Charts
```
reportlab==4.1.0
matplotlib==3.8.4
scipy==1.13.0
qrcode[pil]==7.4.2
Pillow==10.3.0
```

### Authentication
```
authlib==1.3.0
python-dotenv==1.0.1
```

---

## 🔄 Updates & Changelog

### Version 3.0 (Current)
- ✅ Bank-grade 10-page PDF reports
- ✅ 5 professional charts (gauge, radar, line, bell, bar)
- ✅ Security features (watermark, QR, hash)
- ✅ NO document points system
- ✅ Improved UI/UX
- ✅ Multi-branch support

### Version 2.0
- XGBoost ML model integration
- Google Gemini AI document verification
- Dual portal system
- Role-based access control

### Version 1.0
- Basic credit assessment
- Simple PDF reports
- Single user system

---

## 📞 Support

### Contact
- **Email**: support@creditbridge.in
- **Documentation**: docs@creditbridge.in
- **Technical Support**: help@creditbridge.in

### Response Time
- Critical issues: 24 hours
- General queries: 48 hours
- Feature requests: 1 week

---

## 📜 License

Copyright © 2026 CreditBridge. All rights reserved.

This is proprietary software. Unauthorized distribution or reproduction is prohibited.

---

## 🙏 Acknowledgments

- **Google Gemini AI** for document verification
- **XGBoost** for machine learning framework
- **ReportLab** for professional PDF generation
- **Flask** community for excellent framework

---

## 🚀 Future Roadmap

### Planned Features
- [ ] Mobile app (iOS/Android)
- [ ] Real-time credit monitoring
- [ ] Integration with credit bureaus
- [ ] Blockchain verification
- [ ] Multi-language support
- [ ] Advanced fraud detection
- [ ] API for third-party integration
- [ ] White-label solutions

---

**Built with ❤️ for the future of credit assessment**

*CreditBridge v3.0 | AI-Powered Credit Assessment Platform*
