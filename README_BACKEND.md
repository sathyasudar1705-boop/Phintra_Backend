# Backend Setup & Execution

Follow these step-by-step commands to set up and run the FastAPI backend:

1. `cd backend`
2. `venv\Scripts\activate` (or `source venv/bin/activate` on Unix/macOS)
3. `pip install -r requirements.txt`
4. `python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload`
5. Access API documentation at: http://127.0.0.1:8001/docs
