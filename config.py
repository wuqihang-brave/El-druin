import os

# Environment Variables
DATABASE_URL = os.getenv('DATABASE_URL')

# LLM Configuration
LLM_TYPE = os.getenv('LLM_TYPE')  # e.g., 'gpt-3', 'gpt-neo'
LLM_PARAMETERS = {
    'temperature': float(os.getenv('LLM_TEMPERATURE', '0.7')),
    'top_p': float(os.getenv('LLM_TOP_P', '1.0')),
    'max_tokens': int(os.getenv('LLM_MAX_TOKENS', '150')),
}

# Database Settings
DB_SETTINGS = {
    'HOST': os.getenv('DB_HOST', 'localhost'),
    'PORT': int(os.getenv('DB_PORT', '5432')),
    'USER': os.getenv('DB_USER'),
    'PASSWORD': os.getenv('DB_PASSWORD'),
    'NAME': os.getenv('DB_NAME'),
}