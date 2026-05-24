import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_key_student_prediction_system_129847')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Check for MySQL environment variables
    DB_USER = os.environ.get('DB_USER')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_NAME = os.environ.get('DB_NAME')
    
    # 1. First priority: Check for standard DATABASE_URL (Supabase/PostgreSQL)
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if DATABASE_URL:
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    # 2. Second priority: Check for MySQL credentials
    elif DB_USER and DB_PASSWORD and DB_NAME:
        SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"
    # 3. Third priority: Fallback to local SQLite database
    else:
        base_dir = os.path.abspath(os.path.dirname(__file__))
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(base_dir, 'student_system.db')}"
