# Database Connection

## What it does?

This module (`database.py`) sets up the database connection and manages database sessions for the FastAPI application. It provides the foundation for interacting with a PostgreSQL database using SQLAlchemy ORM.

## Why is it needed?

In a FastAPI application, you need a reliable way to:

- Connect to your database
- Create database sessions for each request
- Ensure proper cleanup of database connections
- Share database sessions across different parts of your application

This module centralizes all database connection logic, making it reusable throughout your app.

## Code Explanation

### Imports

```python
from sqlalchemy.orm.session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from json import load
import os
from dotenv import load_dotenv
```

- **SQLAlchemy imports**: Tools for creating database connections, sessions, and model base classes
- **os**: For accessing environment variables
- **load_dotenv**: Loads environment variables from a `.env` file

### Loading Environment Variables

```python
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
```

- `load_dotenv()`: Loads environment variables from your `.env` file
- Gets the database connection string from environment variables (keeps sensitive info out of your code)

### Engine Creation

```python
engine = create_engine(DATABASE_URL)
```

- Creates the core SQLAlchemy engine
- The engine manages the connection pool and handles actual database operations

### Session Factory

```python
SessionLocal = sessionmaker[Session](autocommit=False, autoflush=False, bind=engine)
```

- Creates a factory for database sessions
- **autocommit=False**: Prevents automatic committing of transactions
- **autoflush=False**: Prevents automatic flushing of pending changes
- Each session is bound to the engine

### Base Model Class

```python
Base = declarative_base()
```

- Creates a base class for all database models
- All your table models will inherit from this class

### Database Session Dependency

```python
def get_db():
    db = SessionLocal
    try:
        yield db
    except:
        db.close()
```

- **get_db()**: A generator function used as a FastAPI dependency
- **yield db**: Provides a database session to the request
- **try/except**: Ensures the database connection is properly closed even if an error occurs
- This is used in your API routes via `Depends(get_db)` to inject a database session

## Usage in API Routes

You'll use this in your API routes like this:

```python
@app.get("/users")
def get_notes(db: Session = Depends(get_db)):
    # Your code here
    return {"users": []}
```

The `Depends(get_db)` automatically:

1. Opens a database connection
2. Provides it to your function
3. Closes it when done (even if an error occurs)
