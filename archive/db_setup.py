"""
Database initialization and migration utilities.
Run this file to set up the database or perform migrations.
"""
import os
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, init, migrate, upgrade
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import app and db from main application
from app import app, db

# Initialize Flask-Migrate
migrate_instance = Migrate(app, db)


def init_db():
    """Initialize the database with all tables."""
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("✓ Database tables created successfully!")


def init_migrations():
    """Initialize migrations directory."""
    with app.app_context():
        print("Initializing migrations...")
        try:
            from flask_migrate import init as flask_migrate_init
            flask_migrate_init()
            print("✓ Migrations initialized!")
            print("\nNext steps:")
            print("1. python db_setup.py create_migration 'Initial migration'")
            print("2. python db_setup.py upgrade")
        except Exception as e:
            print(f"Error: {e}")
            print("\nMigrations directory may already exist.")


def create_migration(message="Auto migration"):
    """Create a new migration."""
    with app.app_context():
        print(f"Creating migration: {message}")
        try:
            from flask_migrate import migrate as flask_migrate_create
            flask_migrate_create(message=message)
            print("✓ Migration created!")
            print("\nNext step:")
            print("python db_setup.py upgrade")
        except Exception as e:
            print(f"Error creating migration: {e}")


def upgrade_db():
    """Apply pending migrations."""
    with app.app_context():
        print("Applying migrations...")
        try:
            from flask_migrate import upgrade as flask_migrate_upgrade
            flask_migrate_upgrade()
            print("✓ Database upgraded successfully!")
        except Exception as e:
            print(f"Error upgrading database: {e}")


def downgrade_db(revision="-1"):
    """Rollback migrations."""
    with app.app_context():
        print(f"Rolling back to revision: {revision}")
        try:
            from flask_migrate import downgrade as flask_migrate_downgrade
            flask_migrate_downgrade(revision=revision)
            print("✓ Database downgraded successfully!")
        except Exception as e:
            print(f"Error downgrading database: {e}")


def reset_db():
    """Drop all tables and recreate them. WARNING: This deletes all data!"""
    response = input("⚠️  This will DELETE ALL DATA. Are you sure? (yes/no): ")
    if response.lower() != 'yes':
        print("Operation cancelled.")
        return
    
    with app.app_context():
        print("Dropping all tables...")
        db.drop_all()
        print("Creating all tables...")
        db.create_all()
        print("✓ Database reset complete!")
        
        # Seed initial data
        print("\nSeeding initial data...")
        from app import seed_branches, seed_employees
        seed_branches()
        seed_employees()
        print("✓ Initial data seeded!")


def backup_db():
    """Create a backup of the database."""
    import shutil
    from datetime import datetime
    
    db_path = 'creditbridge.db'
    if not os.path.exists(db_path):
        print("Error: Database file not found!")
        return
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f'backups/creditbridge_backup_{timestamp}.db'
    
    os.makedirs('backups', exist_ok=True)
    shutil.copy2(db_path, backup_path)
    print(f"✓ Database backed up to: {backup_path}")


def show_help():
    """Display help information."""
    help_text = """
CreditBridge Database Management

Usage: python db_setup.py [command] [options]

Commands:
  init              - Create database tables (first-time setup)
  init_migrations   - Initialize Flask-Migrate (for version control)
  create_migration  - Create a new migration (after model changes)
                      Usage: python db_setup.py create_migration "Description"
  upgrade           - Apply pending migrations
  downgrade         - Rollback last migration
  reset             - Drop and recreate all tables (⚠️  DELETES ALL DATA)
  backup            - Create a database backup
  help              - Show this help message

Recommended Workflow:
  1. First time setup:
     python db_setup.py init
     
  2. For production with migrations:
     python db_setup.py init_migrations
     python db_setup.py create_migration "Initial schema"
     python db_setup.py upgrade
     
  3. After model changes:
     python db_setup.py create_migration "Added new field"
     python db_setup.py upgrade
     
  4. Before major changes:
     python db_setup.py backup

Examples:
  python db_setup.py init
  python db_setup.py create_migration "Added employee status field"
  python db_setup.py upgrade
  python db_setup.py backup
"""
    print(help_text)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        show_help()
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    commands = {
        'init': init_db,
        'init_migrations': init_migrations,
        'upgrade': upgrade_db,
        'downgrade': downgrade_db,
        'reset': reset_db,
        'backup': backup_db,
        'help': show_help
    }
    
    if command == 'create_migration':
        message = sys.argv[2] if len(sys.argv) > 2 else "Auto migration"
        create_migration(message)
    elif command in commands:
        commands[command]()
    else:
        print(f"Unknown command: {command}")
        print("Run 'python db_setup.py help' for usage information.")
        sys.exit(1)
