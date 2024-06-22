from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    TELEGRAM_TOKEN: str
    OPENAI_API_KEY: str
    DATABASE_URL: str
    AMPLITUDE_API_KEY: str
    REDIS_URL: str
    REDIS_PORT: int
    ASSISTANT_ID: str
    
    class Config:
        env_file = '.env'

settings = Settings()
