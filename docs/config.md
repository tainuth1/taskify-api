# Application Configuration

## What it does?

This module (`config.py`) defines and manages all application settings for your NoteApp API. It uses Pydantic settings to handle configuration with environment variable support.

## Why is it needed?

Configuration management is essential for:

- **Centralizing settings**: All app configuration in one place
- **Environment-based config**: Different settings for development, staging, and production
- **Type safety**: Pydantic validates configuration values
- **Security**: Keeps sensitive information like database URLs and secrets out of your code

## Code Explanation

### Imports

```python
from pydantic_settings import BaseSettings
```

- **BaseSettings**: A Pydantic class that helps manage application settings
- Automatically loads from environment variables
- Provides validation and default values

### Settings Class

```python
class Settings(BaseSettings):
```

- Defines a configuration class that inherits from `BaseSettings`
- All configuration variables are defined as class attributes

### Project Information

```python
PROJECT_NAME: str = "NoteApp API"
VERSION: str = "1.0.0"
API_V1_STR: str = "/api"
```

- **PROJECT_NAME**: Display name of your application (used in docs/title)
- **VERSION**: Current version of your API
- **API_V1_STR**: The URL prefix for all API endpoints (`/api`)

### Database Configuration

```python
DATABASE_URL: str = "postgresql://username:password@localhost:5432/noteapp"
```

- **DATABASE_URL**: PostgreSQL connection string
- Format: `postgresql://username:password@host:port/database_name`
- This value should be overridden in your `.env` file in production

### JWT (JSON Web Token) Configuration

```python
SECRET_KEY: str = "3Nrv72TBq2PBz1cDxG5zzxZE1sx-0No9RdBm-_SNyFo"
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
```

- **SECRET_KEY**: Secret key for signing JWTs (should be changed in production!)
- **ALGORITHM**: The algorithm used to sign the token (HS256 is common)
- **ACCESS_TOKEN_EXPIRE_MINUTES**: How long tokens remain valid (30 minutes)

### Configuration Class

```python
class Config:
    env_file = ".env"
```

- Tells Pydantic to load settings from a `.env` file
- Environment variables from `.env` will override default values

### Settings Instance

```python
settings = Settings()
```

- Creates a single instance of the Settings class
- Import this instance in other files to access configuration
- Automatically loads from `.env` file if it exists

## Usage in Your Application

You can use this configuration anywhere in your app:

```python
from app.core.config import settings

# Access configuration
print(settings.PROJECT_NAME)  # "NoteApp API"
print(settings.DATABASE_URL)  # Your database URL
print(settings.SECRET_KEY)    # Your secret key
```

## Environment Variables

Create a `.env` file in your project root to override defaults:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/noteapp

# Security
SECRET_KEY=your-actual-secret-key-here

# Optional: Override other settings
PROJECT_NAME=My Note App
VERSION=2.0.0
```

## Best Practices

1. **Never commit `.env` to version control** - Add it to `.gitignore`
2. **Use strong SECRET_KEY** - Generate a secure random key for production
3. **Keep defaults for development** - The defaults help with local development
4. **Use different settings per environment** - Dev, staging, and production should have different values
