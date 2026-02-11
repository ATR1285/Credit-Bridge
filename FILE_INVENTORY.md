# 📋 CreditBridge - Complete File Inventory

## 📂 Core Project Structure

### Active Root Files
- **`app.py`**: The main Flask application entry point. Handles routing, authentication, and core workflows.
- **`creditbridge.db`**: Local SQLite database (Active).
- **`config.py`**: Centralized configuration management.
- **`document_analyzer.py`**: AI-powered document verification logic using Google Gemini.
- **`ml_model.py`**: Core credit scoring and behavioral analysis logic.
- **`pdf_generator.py`**: Active PDF assessment report generator.
- **`permissions.py`**: 5-role hierarchy and granular permission system.
- **`requirements.txt`**: Project dependencies.
- **`.env`**: Environment variables (Database URL, API Keys).

### Essential Folders
- **`models/`**: Contains trained ML models (`xgboost_model.pkl`, scalars).
- **`templates/`**: HTML views for Bank and Public portals.
- **`static/`**: CSS, JS, and image assets.
- **`uploads/`**: Temporary storage for user documents.
- **`reports/`**: Generated PDF credit reports.
- **`migrations/`**: Database schema versions and history.

---

## 🗃️ Archive Folder (`/archive`)
Contains utility scripts, one-time fixes, and legacy generators that are no longer part of the active runtime but kept for reference:

- **PDF/Analysis Reference**: `bank_grade_pdf_generator.py`, `simple_pdf_generator.py`, `analysis_calculator.py`.
- **Initialization Scripts**: `db_setup.py`, `init_migrations.py`, `seed_cloud_db.py`.
- **Fix & Patch Scripts**: `fix_hierarchy.py`, `fix_usernames.py`, `migrate_permissions.py`, `cleanup_all_permission.py`, `reset_employees.py`.
- **Debug & Testing**: `debug_check.py`, `debug_full.py`, `test_login.py`, `test_suite.py`.
- **Requirements Backup**: `requirements_new.txt`.

---

## 🛠️ Verification & Maintenance
- **Cleanup**: `cleanup_tasks.py` handles periodic deletion of old reports/uploads.
- **Logging**: `logging_config.py` manages application journals.
- **Environment**: `.env.example` provides the template for new installations.

**Last Updated**: January 20, 2026 (Post-Cleanup)
