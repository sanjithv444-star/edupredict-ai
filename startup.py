#!/usr/bin/env python3
"""
startup.py - Production initialization script for EduPredict AI.
Run automatically by Render before gunicorn starts (or use as a build step).
Handles database table creation and initial data seeding on fresh PostgreSQL/Supabase instances.
"""

import os
import sys

# Load .env locally (ignored safely in production where env vars are set via Render dashboard)
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("[startup] .env loaded for local development.")
except ImportError:
    pass  # python-dotenv not installed; env vars are injected by Render

from app import app, db
from ml_engine import train_model
from models import StudentProfile

def initialize():
    print("[startup] Initializing EduPredict AI production environment...")
    
    with app.app_context():
        print("[startup] Creating database tables...")
        db.create_all()
        print("[startup] Tables ready.")

        print("[startup] Checking if seed data is needed...")
        from models import User
        if User.query.first() is None:
            print("[startup] No users found. Running seed script...")
            from app import seed_mock_data
            seed_mock_data()
            print("[startup] Seed complete.")
        else:
            print("[startup] Existing data found — skipping seed.")

        print("[startup] Training/loading ML models...")
        profiles = StudentProfile.query.all()
        result = train_model(profiles)
        print(f"[startup] ML models ready. Risk Accuracy: {result['risk_accuracy']}%, "
              f"Grade Accuracy: {result['grade_accuracy']}%, "
              f"Trained on {result['samples_trained']} samples.")

    print("[startup] EduPredict AI is ready for production!")

if __name__ == "__main__":
    initialize()
