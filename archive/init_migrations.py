"""
Database migration setup script.
Run this to initialize Flask-Migrate for the project.

Usage:
    python init_migrations.py
"""

import os
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, init, migrate, upgrade

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import get_config

# Create Flask app
app = Flask(__name__)
app.config.from_object(get_config())

# Initialize database
db = SQLAlchemy(app)

# Initialize Flask-Migrate
migrate_obj = Migrate(app, db)

def initialize_migrations():
    """Initialize Flask-Migrate for the project."""
    
    print("=" * 60)
    print("CREDITBRIDGE - DATABASE MIGRATION INITIALIZATION")
    print("=" * 60)
    
    migrations_dir = 'migrations'
    
    # Check if migrations folder already exists
    if os.path.exists(migrations_dir):
        print(f"\n⚠️  Migrations folder already exists at: {migrations_dir}")
        response = input("Do you want to reinitialize? This will delete existing migrations. (y/N): ")
        
        if response.lower() != 'y':
            print("Initialization cancelled.")
            return
        
        # Backup existing migrations
        import shutil
        backup_dir = f"{migrations_dir}_backup_{int(os.time.time())}"
        shutil.move(migrations_dir, backup_dir)
        print(f"✓ Backed up existing migrations to: {backup_dir}")
    
    try:
        # Initialize migrations
        print("\n📁 Initializing Flask-Migrate...")
        os.system('flask db init')
        print("✓ Migrations folder created")
        
        # Create initial migration
        print("\n📝 Creating initial migration...")
        os.system('flask db migrate -m "Initial migration"')
        print("✓ Initial migration created")
        
        # Apply migration
        print("\n⚙️  Applying migration to database...")
        os.system('flask db upgrade')
        print("✓ Database schema updated")
        
        print("\n" + "=" * 60)
        print("✅ MIGRATION SETUP COMPLETE")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Review the migration file in migrations/versions/")
        print("2. Make any manual adjustments if needed")
        print("3. Use 'flask db migrate' for future schema changes")
        print("4. Use 'flask db upgrade' to apply migrations")
        print("5. Use 'flask db downgrade' to rollback if needed")
        
    except Exception as e:
        print(f"\n❌ Error during initialization: {str(e)}")
        print("\nTroubleshooting:")
        print("1. Ensure Flask-Migrate is installed: pip install Flask-Migrate")
        print("2. Check that your database is accessible")
        print("3. Verify your .env file has correct DATABASE_URL")
        sys.exit(1)


if __name__ == '__main__':
    initialize_migrations()
