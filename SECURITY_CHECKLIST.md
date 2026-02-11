# 🔐 CreditBridge Security Checklist

## Critical Security Tasks

This checklist ensures your CreditBridge application is secure before production deployment.

---

## ✅ Phase 1: Immediate Security (DO NOW)

### 🔴 Priority 1: Credentials & Secrets

- [ ] **Change ALL default passwords**
  ```python
  # Remove these from seed_employees():
  'password': 'pass123'  # ❌ NEVER use this
  
  # Use strong passwords:
  import secrets
  password = secrets.token_urlsafe(16)
  ```

- [ ] **Generate secure SECRET_KEY**
  ```bash
  python -c "import secrets; print(secrets.token_hex(32))"
  # Add to .env:
  # SECRET_KEY=generated-key-here
  ```

- [ ] **Protect .env file**
  ```bash
  # Verify .gitignore includes .env
  grep ".env" .gitignore
  
  # Set proper permissions
  chmod 600 .env  # Only owner can read/write
  ```

- [ ] **Remove sensitive data from git**
  ```bash
  # Check git history
  git log --all --full-history --source -- .env
  
  # If found, clean history
  git filter-branch --force --index-filter \
    "git rm --cached --ignore-unmatch .env" \
    --prune-empty --tag-name-filter cat -- --all
  ```

---

### 🔴 Priority 2: CSRF Protection

- [ ] **Install Flask-WTF**
  ```bash
  pip install Flask-WTF
  ```

- [ ] **Enable CSRF globally**
  ```python
  # In app.py
  from flask_wtf.csrf import CSRFProtect
  
  csrf = CSRFProtect(app)
  ```

- [ ] **Add CSRF to all forms**
  ```html
  <!-- In all template forms -->
  <form method="POST">
      {{ csrf_token() }}
      <!-- form fields -->
  </form>
  ```

- [ ] **Add to AJAX requests**
  ```javascript
  // In JavaScript
  fetch('/api/endpoint', {
      method: 'POST',
      headers: {
          'X-CSRFToken': document.querySelector('[name=csrf_token]').value
      },
      body: JSON.stringify(data)
  })
  ```

---

### 🔴 Priority 3: Session Security

- [ ] **Configure secure sessions**
  ```python
  # In config.py (production)
  SESSION_COOKIE_SECURE = True     # HTTPS only
  SESSION_COOKIE_HTTPONLY = True   # No JavaScript access
  SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF protection
  PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
  ```

- [ ] **Add session timeout**
  ```python
  # In app.py
  @app.before_request
  def check_session_timeout():
      session.permanent = True
      session.modified = True
  ```

- [ ] **Implement logout everywhere**
  ```python
  @app.route('/logout-all')
  def logout_all():
      # Invalidate all user sessions
      session.clear()
      # Log security event
      log_security_event('LOGOUT_ALL', {'user_id': user_id})
  ```

---

### 🔴 Priority 4: Input Validation

- [ ] **Use validators on ALL inputs**
  ```python
  from validators import validate_assessment_data, ValidationError
  
  @app.route('/assessment/new', methods=['POST'])
  def create_assessment():
      try:
          data = validate_assessment_data(request.form)
      except ValidationError as e:
          app.logger.warning(f"Validation failed: {e}")
          flash(str(e), 'error')
          return render_template('form.html')
  ```

- [ ] **Validate file uploads**
  ```python
  from validators import validate_file_upload
  
  file = request.files['document']
  try:
      validate_file_upload(file)
  except ValidationError as e:
      return jsonify({'error': str(e)}), 400
  ```

- [ ] **Sanitize all user inputs**
  ```python
  from validators import sanitize_filename
  
  filename = sanitize_filename(file.filename)
  ```

---

## ✅ Phase 2: Authentication & Authorization

### 🟠 Priority 5: Password Security

- [ ] **Enforce password complexity**
  ```python
  from validators import validate_password_strength
  
  def register_employee():
      password = request.form.get('password')
      try:
          validate_password_strength(password)
      except ValidationError as e:
          flash(str(e), 'error')
          return redirect(url_for('register'))
  ```

- [ ] **Implement rate limiting on login**
  ```python
  from flask_limiter import Limiter
  
  limiter = Limiter(app=app, key_func=get_remote_address)
  
  @app.route('/bank/login', methods=['POST'])
  @limiter.limit("5 per minute")
  def bank_login():
      ...
  ```

- [ ] **Add account lockout**
  ```python
  # Track failed attempts
  failed_attempts = {}
  
  @app.route('/bank/login', methods=['POST'])
  def bank_login():
      username = request.form.get('username')
      
      if failed_attempts.get(username, 0) >= 5:
          log_security_event('ACCOUNT_LOCKED', {'username': username})
          flash('Account locked. Contact administrator.', 'error')
          return render_template('login.html')
  ```

- [ ] **Log all authentication events**
  ```python
  from logging_config import log_security_event
  
  # Success
  log_security_event('LOGIN_SUCCESS', {
      'username': username,
      'ip': request.remote_addr
  })
  
  # Failure
  log_security_event('LOGIN_FAILED', {
      'username': username,
      'ip': request.remote_addr,
      'reason': 'Invalid password'
  }, severity='WARNING')
  ```

---

### 🟠 Priority 6: Authorization

- [ ] **Verify permissions on ALL protected routes**
  ```python
  @app.route('/bank/assessment/<int:id>/approve', methods=['POST'])
  @login_required_bank
  @permission_required('APPROVE_ASSESSMENTS')
  def approve_assessment(id):
      ...
  ```

- [ ] **Check ownership before access**
  ```python
  assessment = CreditAssessment.query.get_or_404(id)
  
  if not assessment.can_be_viewed_by(current_employee):
      log_security_event('UNAUTHORIZED_ACCESS', {
          'employee_id': current_employee.id,
          'assessment_id': id
      })
      abort(403)
  ```

- [ ] **Implement audit logging**
  ```python
  AuditLog.log(
      employee_id=employee.id,
      action='VIEW',
      entity_type='assessment',
      entity_id=assessment.id,
      ip=request.remote_addr,
      user_agent=request.user_agent.string
  )
  ```

---

## ✅ Phase 3: Data Protection

### 🟡 Priority 7: Database Security

- [ ] **Use parameterized queries**
  ```python
  # ✅ GOOD - Using ORM
  users = User.query.filter_by(email=email).all()
  
  # ❌ BAD - Never do this
  users = db.engine.execute(f"SELECT * FROM users WHERE email='{email}'")
  ```

- [ ] **Encrypt sensitive data**
  ```python
  from cryptography.fernet import Fernet
  
  # Generate key (once, store in .env)
  key = Fernet.generate_key()
  
  # Encrypt
  cipher = Fernet(key)
  encrypted = cipher.encrypt(pan_card.encode())
  
  # Store encrypted data
  user.pan_card_encrypted = encrypted
  ```

- [ ] **Regular database backups**
  ```bash
  # Create backup script
  #!/bin/bash
  DATE=$(date +%Y%m%d_%H%M%S)
  pg_dump creditbridge > backups/db_$DATE.sql
  
  # Cron job (daily at 3 AM)
  0 3 * * * /path/to/backup.sh
  ```

---

### 🟡 Priority 8: File Security

- [ ] **Validate file types**
  ```python
  ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}
  
  def allowed_file(filename):
      return '.' in filename and \
             filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
  ```

- [ ] **Scan uploaded files**
  ```python
  # Optional: Integrate with ClamAV
  import pyclamd
  
  cd = pyclamd.ClamdUnixSocket()
  result = cd.scan_file(file_path)
  
  if result:
      log_security_event('MALWARE_DETECTED', {'file': file_path})
      os.remove(file_path)
  ```

- [ ] **Set proper file permissions**
  ```python
  import os
  
  # After saving file
  os.chmod(file_path, 0o640)  # Owner read/write, group read
  ```

---

## ✅ Phase 4: Network & Infrastructure

### 🟡 Priority 9: HTTPS/SSL

- [ ] **Enable HTTPS in production**
  ```nginx
  # Nginx config
  server {
      listen 443 ssl http2;
      ssl_certificate /path/to/cert.pem;
      ssl_certificate_key /path/to/key.pem;
      
      # Modern SSL configuration
      ssl_protocols TLSv1.2 TLSv1.3;
      ssl_ciphers HIGH:!aNULL:!MD5;
  }
  ```

- [ ] **Force HTTPS redirect**
  ```nginx
  server {
      listen 80;
      return 301 https://$server_name$request_uri;
  }
  ```

- [ ] **Add HSTS header**
  ```python
  @app.after_request
  def add_security_headers(response):
      response.headers['Strict-Transport-Security'] = \
          'max-age=31536000; includeSubDomains'
      return response
  ```

---

### 🟡 Priority 10: Headers & CORS

- [ ] **Add security headers**
  ```python
  @app.after_request
  def security_headers(response):
      response.headers['X-Content-Type-Options'] = 'nosniff'
      response.headers['X-Frame-Options'] = 'SAMEORIGIN'
      response.headers['X-XSS-Protection'] = '1; mode=block'
      response.headers['Content-Security-Policy'] = \
          "default-src 'self'; script-src 'self' 'unsafe-inline'"
      return response
  ```

- [ ] **Configure CORS properly**
  ```python
  from flask_cors import CORS
  
  CORS(app, resources={
      r"/api/*": {
          "origins": ["https://yourdomain.com"],
          "methods": ["GET", "POST"],
          "allow_headers": ["Content-Type", "Authorization"]
      }
  })
  ```

---

## ✅ Phase 5: Monitoring & Response

### 🟢 Priority 11: Logging & Monitoring

- [ ] **Enable security logging**
  ```python
  from logging_config import log_security_event
  
  # Log all security-relevant events
  log_security_event('PERMISSION_DENIED', {
      'user': employee.id,
      'resource': assessment.id,
      'ip': request.remote_addr
  })
  ```

- [ ] **Monitor failed login attempts**
  ```python
  # Alert after 5 failed attempts
  if failed_count >= 5:
      send_security_alert(
          f"Multiple failed login attempts for {username}",
          details={'ip': request.remote_addr, 'count': failed_count}
      )
  ```

- [ ] **Set up log alerts**
  ```bash
  # Monitor logs for security events
  tail -f logs/security.log | grep -i "UNAUTHORIZED\|FAILED\|MALWARE"
  ```

---

### 🟢 Priority 12: Incident Response

- [ ] **Create incident response plan**
  ```markdown
  # Security Incident Response
  
  1. **Detect**: Monitor logs, alerts
  2. **Contain**: Disable affected accounts, block IPs
  3. **Investigate**: Review logs, identify scope
  4. **Remediate**: Fix vulnerability, restore service
  5. **Document**: Record incident details
  6. **Review**: Post-mortem, improve procedures
  ```

- [ ] **Implement IP blocking**
  ```python
  BLOCKED_IPS = set()
  
  @app.before_request
  def check_ip():
      if request.remote_addr in BLOCKED_IPS:
          log_security_event('BLOCKED_IP_ATTEMPT', {
              'ip': request.remote_addr
          })
          abort(403)
  ```

---

## 📋 Security Audit Checklist

Run this checklist before production:

### Configuration
- [ ] DEBUG=False in production
- [ ] Strong SECRET_KEY set
- [ ] SESSION_COOKIE_SECURE=True
- [ ] HTTPS enabled
- [ ] Database password strong
- [ ] API keys in environment variables

### Authentication
- [ ] Default passwords changed
- [ ] Password complexity enforced
- [ ] Account lockout implemented
- [ ] Rate limiting on login
- [ ] Session timeout configured
- [ ] Logout clears session

### Authorization
- [ ] All routes have auth checks
- [ ] Permissions verified
- [ ] Ownership verified
- [ ] Audit logging enabled

### Input Validation
- [ ] All inputs validated
- [ ] File uploads validated
- [ ] SQL injection prevented
- [ ] XSS prevented
- [ ] CSRF protected

### Data Protection
- [ ] Sensitive data encrypted
- [ ] Database backups configured
- [ ] File permissions set
- [ ] Logs don't contain secrets

### Infrastructure
- [ ] HTTPS configured
- [ ] Security headers added
- [ ] CORS configured
- [ ] Firewall rules set

### Monitoring
- [ ] Security logging enabled
- [ ] Log rotation configured
- [ ] Alerts configured
- [ ] Incident response plan

---

## 🚨 Emergency Response

If you discover a security issue:

1. **Immediate Actions**
   ```bash
   # Block suspicious IP
   iptables -A INPUT -s SUSPICIOUS_IP -j DROP
   
   # Disable affected accounts
   # Check logs
   grep "SUSPICIOUS_ACTIVITY" logs/security.log
   ```

2. **Containment**
   - Change all passwords
   - Rotate API keys
   - Review access logs
   - Identify scope

3. **Notification**
   - Notify affected users
   - Report if required
   - Document incident

---

## 🔍 Security Testing

Regular security tests:

```bash
# 1. Check for exposed secrets
git secrets --scan

# 2. Dependency vulnerabilities
pip audit

# 3. SQL injection test
sqlmap -u "http://localhost:5000/login" --data="username=admin&password=test"

# 4. XSS test
# Try injecting: <script>alert('XSS')</script>

# 5. CSRF test
# Try submitting form without CSRF token
```

---

## 📚 Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Flask Security Best Practices](https://flask.palletsprojects.com/en/2.3.x/security/)
- [Python Security Guide](https://python.readthedocs.io/en/latest/library/security_warnings.html)

---

**Last Updated**: January 17, 2026
**Status**: Comprehensive Security Guide
**Priority**: 🔴 CRITICAL - Complete before production

---

✅ = Completed
⏳ = In Progress
❌ = Not Started

**Your Security Score**: ___ / 100 tasks
