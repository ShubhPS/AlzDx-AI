import os
from datetime import timedelta

class Config:
    # Basic Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    
    # Database configuration
    DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')
    
    # Upload configuration
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    
    # Model configuration
    MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models', 'alzheimer_model.h5')
    IMAGE_SIZE = (224, 224)  # Input size for the model
    
    # Admin configuration
    ADMIN_USERNAME = 'admin'
    ADMIN_EMAIL = 'admin@neuroscan.ai'
    ADMIN_PASSWORD = 'admin123'  # Change this in production
    
    # Initialize required directories
    @staticmethod
    def init_app(app):
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(os.path.dirname(Config.MODEL_PATH), exist_ok=True)
        
class DevelopmentConfig(Config):
    DEBUG = True
    
class ProductionConfig(Config):
    DEBUG = False
    # In production, set SECRET_KEY from environment variable
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(24)
    
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
} 