# 🏦 CreditBridge - Production Setup Guide

This guide covers setting up CreditBridge for production deployment with all security and performance improvements.

## 🚀 Quick Start (Development)

### 1. Clone and Setup

```bash
# Clone repository
git clone <repository-url>
cd Creditbridge

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements_new.txt
```

### 2. Environment Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env and fill in your values
# REQUIRED:
# - SECRET_KEY (generate with: python -c "import secrets; print(secrets.token_hex(32))")
# - GEMINI_API_KEY (get from https://makersuite.google.com/app/apikey)

# OPTIONAL but recommended:
# - GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET (for OAuth)
# - MAIL_USERNAME and MAIL_PASSWORD (for email notifications)
```

### 3. Initialize Database

```bash
# Initialize Flask-Migrate
python init_migrations.py

# This will:
# - Create migrations folder
# - Generate initial migration
# - Apply migration to database
```

### 4. Run Application

```bash
# Development mode
python app.py

# Or using Flask CLI
flask run --debug
```

Access the application at: http://localhost:5000

---

## 🔐 Security Improvements Implemented

### 1. CSRF Protection
- All forms protected with CSRF tokens
- Added Flask-WTF integration

### 2. Password Security
- Strong password requirements (8+ chars, uppercase, lowercase, numbers, special chars)
- Password hashing with Werkzeug
- No hardcoded passwords in production

### 3. Session Security
- Secure cookie settings
- Configurable session timeout
- HTTPOnly and SameSite flags

### 4. Input Validation
- Comprehensive validation for all inputs
- SQL injection prevention through ORM
- File upload validation

### 5. Rate Limiting
- Flask-Limiter integration
- Configurable rate limits per endpoint
- Protection against brute force attacks

---

## 📊 Database Management

### Migrations

```bash
# Create a new migration after model changes
flask db migrate -m "Description of changes"

# Review the generated migration file in migrations/versions/

# Apply migration
flask db upgrade

# Rollback migration
flask db downgrade

# View migration history
flask db history
```

### Backup

```bash
# Backup SQLite database
cp creditbridge.db creditbridge_backup_$(date +%Y%m%d).db

# For PostgreSQL
pg_dump creditbridge > backup_$(date +%Y%m%d).sql
```

---

## 🧹 File Cleanup

Automatic cleanup is configured via APScheduler:

- **Uploaded documents**: Deleted after 90 days (configurable)
- **Generated reports**: Deleted after 90 days
- **Temporary files**: Deleted after 24 hours

Schedule:
- Document cleanup: Daily at 2 AM
- Report cleanup: Daily at 3 AM
- Temp cleanup: Every 6 hours

Manual cleanup:
```python
from cleanup_tasks import manual_cleanup
manual_cleanup(app, db, DocumentUpload)
```

---

## 📧 Email Notifications

Configure email in `.env`:

```env
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
```

**For Gmail**: Generate app password at https://myaccount.google.com/apppasswords

Notifications sent for:
- Assessment assignments
- Approval/rejection
- Password resets
- Daily summaries

---

## 📝 Logging

Logs are stored in `logs/` directory:

- `creditbridge.log` - General application logs
- `errors.log` - Error and critical events
- `security.log` - Authentication and authorization events
- `access.log` - HTTP request logs

Configuration in `.env`:
```env
LOG_LEVEL=INFO
LOG_FILE=logs/creditbridge.log
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5
```

---

## 🧪 Testing

### Run Tests

```bash
# Install test dependencies
pip install pytest pytest-cov pytest-flask

# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Create Tests

Example test file:
```python
# tests/test_models.py
import pytest
from app import app, db
from models import Employee

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.drop_all()

def test_employee_creation(client):
    emp = Employee(
        username='test_user',
        full_name='Test User',
        role='loan_officer'
    )
    db.session.add(emp)
    db.session.commit()
    assert emp.id is not None
```

---

## 🚀 Production Deployment

### 1. Environment Setup

```bash
# Set production environment
export FLASK_ENV=production

# Update .env for production
SESSION_COOKIE_SECURE=True
DEBUG=False
LOG_LEVEL=WARNING
```

### 2. Database Migration

```bash
# Use PostgreSQL in production
DATABASE_URL=postgresql://user:pass@localhost/creditbridge

# Run migrations
flask db upgrade
```

### 3. WSGI Server (Gunicorn)

```bash
# Install Gunicorn
pip install gunicorn

# Run with Gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 app:app

# With config file
gunicorn -c gunicorn_config.py app:app
```

Create `gunicorn_config.py`:
```python
bind = "0.0.0.0:8000"
workers = 4
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2
errorlog = "logs/gunicorn_error.log"
accesslog = "logs/gunicorn_access.log"
loglevel = "info"
```

### 4. Nginx Configuration

```nginx
server {
    listen 80;
    server_name creditbridge.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /static {
        alias /path/to/creditbridge/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### 5. SSL/HTTPS (Let's Encrypt)

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d creditbridge.com

# Auto-renewal
sudo certbot renew --dry-run
```

### 6. Systemd Service

Create `/etc/systemd/system/creditbridge.service`:
```ini
[Unit]
Description=CreditBridge Application
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/creditbridge
Environment="PATH=/path/to/creditbridge/venv/bin"
ExecStart=/path/to/creditbridge/venv/bin/gunicorn -c gunicorn_config.py app:app

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable creditbridge
sudo systemctl start creditbridge
sudo systemctl status creditbridge
```

---

## 📊 Monitoring

### Application Monitoring

```bash
# View logs in real-time
tail -f logs/creditbridge.log

# Search for errors
grep ERROR logs/creditbridge.log

# Monitor with Supervisor
sudo apt install supervisor
```

### Database Monitoring

```bash
# PostgreSQL connections
SELECT * FROM pg_stat_activity;

# Table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

## 🔧 Troubleshooting

### Common Issues

**1. Database migration fails**
```bash
# Reset migrations
rm -rf migrations/
python init_migrations.py
```

**2. File upload fails**
```bash
# Check permissions
chmod 755 uploads/
chmod 755 reports/
```

**3. Email not sending**
```bash
# Test SMTP connection
python -c "import smtplib; smtplib.SMTP('smtp.gmail.com', 587).starttls()"
```

**4. High memory usage**
```bash
# Reduce worker count
# In gunicorn_config.py: workers = 2
```

**5. Slow queries**
```bash
# Add database indexes
# Check migrations for index creation
```

---

## 📚 Additional Resources

- [Flask Documentation](https://flask.palletsprojects.com/)
- [SQLAlchemy ORM](https://docs.sqlalchemy.org/)
- [Flask-Migrate Guide](https://flask-migrate.readthedocs.io/)
- [Gunicorn Deployment](https://docs.gunicorn.org/)
- [Nginx Configuration](https://nginx.org/en/docs/)

---

## 🆘 Support

For issues or questions:
1. Check the logs in `logs/` directory
2. Review error messages carefully
3. Check environment configuration in `.env`
4. Ensure all dependencies are installed
5. Verify database connectivity

---

## 📋 Checklist for Production

- [ ] Strong SECRET_KEY generated
- [ ] Database backed up
- [ ] HTTPS/SSL configured
- [ ] SESSION_COOKIE_SECURE=True
- [ ] DEBUG=False
- [ ] Email notifications configured
- [ ] Rate limiting enabled
- [ ] Log rotation configured
- [ ] File cleanup scheduled
- [ ] Monitoring set up
- [ ] Firewall configured
- [ ] Regular backups scheduled
- [ ] Error alerting configured

---

**Last Updated**: January 2026
**Version**: 3.0.1
