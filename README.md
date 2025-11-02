# Taskify

A simple and modern task management system built with FastAPI, featuring user authentication, profile management, and secure password reset functionality.

## 📋 Project Overview

Taskify is a RESTful API application designed for task management, built with FastAPI and PostgreSQL. It provides a robust authentication system with JWT tokens, OTP-based password reset, and user profile management with image upload capabilities via Cloudinary.

### Key Features (Authentication)

- **User Authentication**: Sign up, sign in, and sign out with JWT-based authentication
- **Token Management**: Access and refresh token support with secure cookie handling
- **OTP Verification**: Email-based OTP for password reset using Brevo
- **Profile Management**: Update user profiles with image upload support (Cloudinary)
- **Password Reset**: Secure password reset flow with token-based verification
- **PostgreSQL Database**: Robust database integration with SQLAlchemy ORM
- **FastAPI**: High-performance async API framework with automatic documentation

## 🛠️ Tech Stack

- **Framework**: FastAPI 0.104.1
- **Database**: PostgreSQL with SQLAlchemy 2.0.23
- **Authentication**: JWT (python-jose) with bcrypt for password hashing
- **Email Service**: Brevo (Sendinblue API)
- **File Storage**: Cloudinary for profile image uploads
- **Server**: Uvicorn ASGI server
- **Environment**: python-dotenv for configuration management

## 📁 Project Structure

```
Taskify/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── database.py             # Database connection and session management
│   ├── api/
│   │   ├── __init__.py
│   │   ├── route.py            # API router configuration
│   │   └── endpoints/
│   │       ├── __init__.py
│   │       └── auth.py         # Authentication endpoints
│   ├── controllers/
│   │   └── auth_controller.py  # Business logic for authentication
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py           # Application settings and configuration
│   │   ├── security.py         # JWT and password hashing utilities
│   │   └── email.py            # Email service integration (Brevo)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py             # User database model
│   │   └── otp.py              # OTP database model
│   └── schemas/
│       ├── __init__.py
│       ├── user.py             # User Pydantic schemas
│       └── otp.py              # OTP Pydantic schemas
├── docs/
│   ├── config.md               # Configuration documentation
│   └── database-connection.md  # Database setup guide
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## 🚀 Installation Instructions

### Prerequisites

- Python 3.12 or higher
- PostgreSQL database
- Cloudinary account (for image uploads)
- Brevo account (for email services)

### Step 1: Clone the Repository

```bash
git clone <your-repository-url>
cd Taskify
```

### Step 2: Create a Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Set Up Environment Variables

Create a `.env` file in the root directory with the following variables:

```env
# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/taskify_db

# JWT Configuration
SECRET_KEY=your-secret-key-here  # Generate a strong secret key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Cookie Configuration
ACCESS_TOKEN_COOKIE_NAME=access_token
REFRESH_TOKEN_COOKIE_NAME=refresh_token
COOKIE_DOMAIN=
COOKIE_SECURE=False  # Set to True in production with HTTPS
COOKIE_SAMESITE=lax

# Cloudinary Configuration
CLOUDINARY_CLOUD_NAME=your-cloudinary-cloud-name
CLOUDINARY_API_KEY=your-cloudinary-api-key
CLOUDINARY_API_SECRET=your-cloudinary-api-secret

# Brevo Email Configuration
BREVO_API_KEY=your-brevo-api-key
BREVO_SENDER_EMAIL=your-email@example.com
BREVO_SENDER_NAME=Taskify
OTP_EXPIRE_MINUTES=5
RESET_PASSWORD_TOKEN_EXPIRE_MINUTES=5
```

### Step 5: Set Up PostgreSQL Database

1. Install PostgreSQL if you haven't already
2. Create a new database:

```sql
CREATE DATABASE taskify_db;
```

3. The application will automatically create tables on startup via SQLAlchemy's `Base.metadata.create_all()`

Alternatively, you can use Alembic for database migrations (already included in dependencies).

### Step 6: Run the Application

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://127.0.0.1:8000`

### Step 7: Access API Documentation

- **Swagger UI**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc

## 🔧 Configuration

### Database Connection

The application uses SQLAlchemy with PostgreSQL. The database connection string should follow this format:

```
postgresql://username:password@host:port/database_name
```

For local development:

```
postgresql://postgres:password@localhost:5432/taskify_db
```

### CORS Configuration

CORS is configured in `app/main.py`. Update the `allow_origins` list to include your frontend URL in production:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000"],  # Add your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 📚 API Endpoints

### Authentication Endpoints

| Method | Endpoint                    | Description                              |
| ------ | --------------------------- | ---------------------------------------- |
| POST   | `/api/auth/signup`          | Create a new user account                |
| POST   | `/api/auth/signin`          | Sign in with email/username and password |
| POST   | `/api/auth/signout`         | Sign out and clear tokens                |
| GET    | `/api/auth/me`              | Get current user profile                 |
| PATCH  | `/api/auth/update`          | Update user profile                      |
| POST   | `/api/auth/refresh`         | Refresh access token                     |
| POST   | `/api/auth/forgot-password` | Request OTP for password reset           |
| POST   | `/api/auth/verify-otp`      | Verify OTP and get reset token           |
| POST   | `/api/auth/reset-password`  | Reset password with reset token          |

### Health Check Endpoints

| Method | Endpoint     | Description                      |
| ------ | ------------ | -------------------------------- |
| GET    | `/`          | Welcome message                  |
| GET    | `/health/db` | Check database connection status |

## 🔐 Authentication Flow

1. **Sign Up**: User registers with email, username, and password
2. **Sign In**: User authenticates and receives JWT tokens (stored in HTTP-only cookies)
3. **Access Protected Routes**: Access token is sent via cookie automatically
4. **Token Refresh**: Refresh token is used to obtain a new access token
5. **Password Reset**:
   - User requests OTP via email
   - User verifies OTP and receives reset token
   - User resets password using reset token

## 🧪 Development

### Running in Development Mode

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The `--reload` flag enables auto-reload on code changes.

### Database Migrations

If you need to manage database migrations, you can use Alembic:

```bash
# Initialize Alembic (if not already done)
alembic init alembic

# Create a migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head
```

## 📝 Environment Variables Reference

| Variable                              | Required | Description                           |
| ------------------------------------- | -------- | ------------------------------------- |
| `DATABASE_URL`                        | Yes      | PostgreSQL connection string          |
| `SECRET_KEY`                          | Yes      | Secret key for JWT token signing      |
| `CLOUDINARY_CLOUD_NAME`               | Yes      | Cloudinary cloud name                 |
| `CLOUDINARY_API_KEY`                  | Yes      | Cloudinary API key                    |
| `CLOUDINARY_API_SECRET`               | Yes      | Cloudinary API secret                 |
| `BREVO_API_KEY`                       | Yes      | Brevo API key for email service       |
| `BREVO_SENDER_EMAIL`                  | Yes      | Email address for sending emails      |
| `BREVO_SENDER_NAME`                   | No       | Sender name (default: Taskify)        |
| `OTP_EXPIRE_MINUTES`                  | No       | OTP expiration time (default: 5)      |
| `RESET_PASSWORD_TOKEN_EXPIRE_MINUTES` | No       | Reset token expiration (default: 5)   |
| `ACCESS_TOKEN_EXPIRE_MINUTES`         | No       | Access token expiration (default: 15) |
| `REFRESH_TOKEN_EXPIRE_DAYS`           | No       | Refresh token expiration (default: 7) |

## 🚀 Production Deployment

### Security Considerations

1. Set `COOKIE_SECURE=True` when deploying with HTTPS
2. Use a strong `SECRET_KEY` (generate with: `openssl rand -hex 32`)
3. Update CORS `allow_origins` to your production frontend URL
4. Use environment variables for all sensitive configuration
5. Enable PostgreSQL SSL connections in production
6. Set up proper logging and monitoring

### Example Production Command

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 📖 Additional Documentation

- [Database Connection Guide](docs/database-connection.md)
- [Configuration Guide](docs/config.md)

Contributions are welcome! Please feel free to submit a Pull Request.

## 👤 Author

Tai Nuth

## 🙏 Acknowledgments

- FastAPI for the amazing framework
- SQLAlchemy for robust ORM support
- Cloudinary for file storage
- Brevo for email services
