from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, teacher, student
    
    # Relationships
    profile = db.relationship('StudentProfile', backref='user', uselist=False, cascade="all, delete-orphan")
    assessments = db.relationship('Assessment', backref='user', cascade="all, delete-orphan")
    recommendations = db.relationship('Recommendation', backref='user', cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class StudentProfile(db.Model):
    __tablename__ = 'student_profiles'
    
    student_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    attendance_rate = db.Column(db.Float, default=90.0)      # Percentage (0-100)
    study_hours_per_week = db.Column(db.Float, default=10.0)  # Hours per week
    past_score = db.Column(db.Float, default=75.0)            # Score (0-100)
    parental_support_level = db.Column(db.String(20), default='Medium') # Low, Medium, High
    
    # ML Prediction outputs
    predicted_risk = db.Column(db.String(20), default='Safe') # Safe, Medium Risk, High Risk
    predicted_grade = db.Column(db.String(5), default='B')     # A, B, C, D, F

class Assessment(db.Model):
    __tablename__ = 'assessments'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    score = db.Column(db.Float, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    date_taken = db.Column(db.DateTime, default=datetime.utcnow)

class Recommendation(db.Model):
    __tablename__ = 'recommendations'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    resource_title = db.Column(db.String(200), nullable=False)
    resource_url = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='recommended')  # recommended, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
