# Phintra FastAPI Backend

Production-ready modular REST API backend for the Phintra security training and awareness platform.

## Technology Stack
- **FastAPI** as the API framework
- **SQLAlchemy** as the database ORM with UUID primary keys
- **Pydantic** for schemas validation
- **JWT** for stateless session management with bcrypt hashing
- **PostgreSQL** database

---

## Folder Structure

```
backend/
  app/
    main.py           # Entry point / FastAPI instantiation
    database.py       # DB engine and session configuration
    config.py         # App environment configuration
    models/           # SQLAlchemy database tables
    schemas/          # Pydantic schemas validation
    routes/           # FastAPI controller endpoints
    services/         # Business logic layer
    utils/            # Hashing and authentication helpers
  .env                # Local secrets configuration
  requirements.txt    # Package dependencies
  README.md           # Documentation
  seed.py             # Database seed script
```

---

## Setup Instructions

### 1. Configure Python Environment
Create a virtual environment and install the required package dependencies:

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment (Windows)
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Set Up Environment Variables
Copy `.env.example` to `.env` and fill in the values (especially database connection string and secure secret key credentials):

```bash
cp .env.example .env
```

Ensure your `DATABASE_URL` matches your local PostgreSQL connection credentials, for example:
`DATABASE_URL=postgresql://postgres:postgres@localhost:5432/phintra`

### 3. Provision the Database and Run Seeding
Run the seed script to automatically provision the database tables and populate the default demo records:

```bash
python seed.py
```

This will automatically:
- Create all database schemas (users, departments, employees, campaigns, templates, modules, quizzes, etc.)
- Populate three default login accounts:
  - **Admin**: `admin@phintra.com` / `admin123`
  - **Manager**: `manager@phintra.com` / `manager123`
  - **Employee**: `employee@phintra.com` / `employee123`
- Insert 5 core departments
- Setup 3 educational course modules and sample simulation drills

### 4. Running the API Server
Start the Uvicorn live server:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open your browser at `http://127.0.0.1:8000/docs` to access the interactive Swagger Documentation for the backend.

---

## Gmail SMTP App Password Instructions

To use a Gmail address with the Phintra platform to send emails, you must configure a Google App Password rather than using your main password directly:

1. **Enable 2-Step Verification**:
   - Go to your [Google Account Dashboard](https://myaccount.google.com/).
   - Select **Security** on the left navigation panel.
   - Under the "How you sign in to Google" section, verify that **2-Step Verification** is turned ON. If not, follow the prompts to enable it.

2. **Generate App Password**:
   - Go to [Security -> 2-Step Verification](https://myaccount.google.com/signinoptions/two-step-verification) and scroll to the bottom to find **App passwords**.
   - Enter a name for the application (e.g., "Phintra Security Awareness").
   - Click **Create**.
   - Google will display a 16-character code (e.g., `abcd efgh ijkl mnop`).

3. **Configure Environment Variables**:
   - Copy the 16-character code (without spaces).
   - In your `backend/.env` file, populate the variables:
     ```env
     SMTP_HOST=smtp.gmail.com
     SMTP_PORT=587
     SMTP_USER=your_gmail_address@gmail.com
     SMTP_PASSWORD=sixteencharacterapppasswordhere
     SMTP_FROM_EMAIL=your_gmail_address@gmail.com
     ```
   - Restart the FastAPI server so the configuration loads.

