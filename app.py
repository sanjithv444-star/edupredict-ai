import os
import csv
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename

# Load .env file for local development (silently skipped if not present or not installed)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from config import Config
from models import db, User, StudentProfile, Assessment, Recommendation
from ml_engine import predict_student_status, train_model, encode_parental_support

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# Allowed file extensions for admin CSV upload
ALLOWED_EXTENSIONS = {'csv'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ----------------------------------------------------
# Role-based Authorization Decorators
# ----------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('login'))
            if session.get('role') not in roles:
                flash('Access Denied. You do not have permission to view this resource.', 'danger')
                # Redirect user back to their respective homepage
                role = session.get('role')
                if role == 'admin':
                    return redirect(url_for('admin_dashboard'))
                elif role == 'teacher':
                    return redirect(url_for('teacher_dashboard'))
                elif role == 'student':
                    return redirect(url_for('student_dashboard'))
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ----------------------------------------------------
# Auto-Recommendation Logic
# ----------------------------------------------------
def generate_recommendations_for_student(student_id):
    """
    Populates the Recommendations table based on a student's risk profile 
    and specific assessment weaknesses.
    """
    profile = StudentProfile.query.filter_by(student_id=student_id).first()
    if not profile:
        return
        
    assessments = Assessment.query.filter_by(student_id=student_id).all()
    
    # Predefined learning resources mapping
    remedial_resources = {
        'Mathematics': {
            'title': 'Mathematics: Algebra & Equations Mastery',
            'url': 'https://www.khanacademy.org/math/algebra'
        },
        'Science': {
            'title': 'Science: Physics & Molecular Biology Bootcamp',
            'url': 'https://www.khanacademy.org/science/biology'
        },
        'English': {
            'title': 'English: Reading Comprehension & Writing Skills',
            'url': 'https://www.khanacademy.org/humanities/grammar'
        }
    }
    
    general_remedial = {
        'title': 'Effective Study Techniques & Time Management Course',
        'url': 'https://www.coursera.org/learn/learning-how-to-learn'
    }
    
    advanced_resource = {
        'title': 'Advanced Algorithms & Creative Thinking Masterclass',
        'url': 'https://www.geeksforgeeks.org/data-structures/'
    }

    # Fetch existing recommendations titles to avoid duplicates
    existing_titles = [r.resource_title for r in Recommendation.query.filter_by(student_id=student_id).all()]
    
    # 1. Handle At-Risk and low scores
    is_at_risk = profile.predicted_risk in ['High Risk', 'Medium Risk']
    
    added_any = False
    
    # Check course-specific weaknesses
    for a in assessments:
        if a.score < 70:
            res = remedial_resources.get(a.subject)
            if res and res['title'] not in existing_titles:
                new_rec = Recommendation(
                    student_id=student_id,
                    resource_title=res['title'],
                    resource_url=res['url'],
                    status='recommended'
                )
                db.session.add(new_rec)
                existing_titles.append(res['title'])
                added_any = True

    # Check overall profile stats
    if is_at_risk or profile.past_score < 70:
        if general_remedial['title'] not in existing_titles:
            new_rec = Recommendation(
                student_id=student_id,
                resource_title=general_remedial['title'],
                resource_url=general_remedial['url'],
                status='recommended'
            )
            db.session.add(new_rec)
            existing_titles.append(general_remedial['title'])
            added_any = True
            
    # 2. Handle outstanding students (Safe and scores are high)
    if profile.predicted_risk == 'Safe' and profile.past_score >= 85:
        if advanced_resource['title'] not in existing_titles:
            new_rec = Recommendation(
                student_id=student_id,
                resource_title=advanced_resource['title'],
                resource_url=advanced_resource['url'],
                status='recommended'
            )
            db.session.add(new_rec)
            added_any = True
            
    # Save recommendations
    db.session.commit()

# ----------------------------------------------------
# Prediction helper
# ----------------------------------------------------
def run_and_save_prediction(student_id):
    """Fetches student parameters, runs ML prediction, saves outputs, triggers recommendations."""
    profile = StudentProfile.query.filter_by(student_id=student_id).first()
    if not profile:
        return False
        
    risk, grade = predict_student_status(
        attendance_rate=profile.attendance_rate,
        study_hours_per_week=profile.study_hours_per_week,
        past_score=profile.past_score,
        parental_support_level=profile.parental_support_level
    )
    
    profile.predicted_risk = risk
    profile.predicted_grade = grade
    db.session.commit()
    
    # Auto-generate recommendations based on new stats
    generate_recommendations_for_student(student_id)
    return True

# ----------------------------------------------------
# Main Routes & Auth
# ----------------------------------------------------
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    role = session.get('role')
    if role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif role == 'teacher':
        return redirect(url_for('teacher_dashboard'))
    elif role == 'student':
        return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email').strip().lower()
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['name'] = user.name
            session['role'] = user.role
            flash(f"Welcome back, {user.name}!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid email or password.", "danger")
            
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        name = request.form.get('name').strip()
        email = request.form.get('email').strip().lower()
        password = request.form.get('password')
        role = request.form.get('role')
        
        if not name or not email or not password or not role:
            flash("All fields are required.", "danger")
            return render_template('signup.html')
            
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("An account with that email already exists.", "danger")
            return render_template('signup.html')
            
        new_user = User.query(name=name, email=email, role=role)
        # SQLAlchemy models init is clean but let's initialize User explicitly
        new_user = User(name=name, email=email, role=role)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        
        # If user is a student, create a blank/default student profile
        if role == 'student':
            profile = StudentProfile(
                student_id=new_user.id,
                attendance_rate=85.0,
                study_hours_per_week=10.0,
                past_score=75.0,
                parental_support_level='Medium'
            )
            db.session.add(profile)
            db.session.commit()
            # Run prediction and build initial recommendations
            run_and_save_prediction(new_user.id)
            
        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))
        
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))

# ----------------------------------------------------
# Student Dashboard & Features
# ----------------------------------------------------
@app.route('/student/dashboard')
@role_required('student')
def student_dashboard():
    student_id = session['user_id']
    profile = StudentProfile.query.filter_by(student_id=student_id).first()
    assessments = Assessment.query.filter_by(student_id=student_id).order_by(Assessment.date_taken.asc()).all()
    recommendations = Recommendation.query.filter_by(student_id=student_id).all()
    
    # Format assessments data for Chart.js
    chart_labels = [a.date_taken.strftime('%b %d') for a in assessments]
    chart_scores = [a.score for a in assessments]
    chart_subjects = [a.subject for a in assessments]
    
    return render_template(
        'student_dashboard.html',
        profile=profile,
        assessments=assessments,
        recommendations=recommendations,
        chart_labels=chart_labels,
        chart_scores=chart_scores,
        chart_subjects=chart_subjects
    )

@app.route('/student/take_quiz', methods=['POST'])
@role_required('student')
def take_quiz():
    """Handles submission of student self-assessments."""
    student_id = session['user_id']
    subject = request.form.get('subject')
    score = float(request.form.get('score', 0))
    total_questions = int(request.form.get('total_questions', 10))
    
    # Record assessment in database
    new_assessment = Assessment(
        student_id=student_id,
        subject=subject,
        score=score,
        total_questions=total_questions
    )
    db.session.add(new_assessment)
    
    # Update profile past_score to be the average of all assessment scores
    all_assessments = Assessment.query.filter_by(student_id=student_id).all()
    if all_assessments:
        avg_score = sum([a.score for a in all_assessments]) / len(all_assessments)
        profile = StudentProfile.query.filter_by(student_id=student_id).first()
        profile.past_score = round(avg_score, 1)
        
    db.session.commit()
    
    # Re-run ML predictions with updated stats
    run_and_save_prediction(student_id)
    
    flash(f"Assessment quiz submitted! Scored {score:.1f}%. Performance metrics recalculated.", "success")
    return redirect(url_for('student_dashboard'))

@app.route('/student/complete_recommendation/<int:rec_id>', methods=['POST'])
@role_required('student')
def complete_recommendation(rec_id):
    rec = Recommendation.query.filter_by(id=rec_id, student_id=session['user_id']).first()
    if rec:
        rec.status = 'completed'
        db.session.commit()
        flash("Congratulations on completing this recommendation!", "success")
    return redirect(url_for('student_dashboard'))

@app.route('/student/update_profile', methods=['POST'])
@role_required('student')
def update_student_profile():
    student_id = session['user_id']
    profile = StudentProfile.query.filter_by(student_id=student_id).first()
    if profile:
        profile.attendance_rate = float(request.form.get('attendance_rate', 85.0))
        profile.study_hours_per_week = float(request.form.get('study_hours_per_week', 10.0))
        profile.parental_support_level = request.form.get('parental_support_level', 'Medium')
        db.session.commit()
        
        # Run ML predictions with updated stats
        run_and_save_prediction(student_id)
        flash("Academic and study metrics updated successfully! AI predictions refreshed.", "success")
    else:
        flash("Failed to find student profile.", "danger")
        
    return redirect(url_for('student_dashboard'))

# ----------------------------------------------------
# Teacher Dashboard & Features
# ----------------------------------------------------
@app.route('/teacher/dashboard')
@role_required('teacher')
def teacher_dashboard():
    # Fetch all students and their profiles
    students = User.query.filter_by(role='student').all()
    
    # Calculate stats
    total_students = len(students)
    at_risk_count = 0
    total_scores = 0
    scores_count = 0
    
    student_list = []
    for s in students:
        profile = s.profile
        if not profile:
            continue
        
        if profile.predicted_risk in ['High Risk', 'Medium Risk']:
            at_risk_count += 1
            
        total_scores += profile.past_score
        scores_count += 1
        
        student_list.append({
            'id': s.id,
            'name': s.name,
            'email': s.email,
            'attendance_rate': profile.attendance_rate,
            'study_hours_per_week': profile.study_hours_per_week,
            'past_score': profile.past_score,
            'predicted_risk': profile.predicted_risk,
            'predicted_grade': profile.predicted_grade,
            'parental_support': profile.parental_support_level
        })
        
    avg_score = round(total_scores / scores_count, 1) if scores_count > 0 else 0.0
    
    return render_template(
        'teacher_dashboard.html',
        students=student_list,
        total_students=total_students,
        at_risk_count=at_risk_count,
        avg_score=avg_score
    )

@app.route('/teacher/assign_task', methods=['POST'])
@role_required('teacher')
def assign_task():
    student_id = int(request.form.get('student_id'))
    resource_title = request.form.get('resource_title')
    resource_url = request.form.get('resource_url')
    
    if not resource_title or not resource_url:
        flash("Task assignment failed. Invalid details.", "danger")
        return redirect(url_for('teacher_dashboard'))
        
    new_rec = Recommendation(
        student_id=student_id,
        resource_title=resource_title,
        resource_url=resource_url,
        status='recommended'
    )
    db.session.add(new_rec)
    db.session.commit()
    
    flash(f"Personalized task assigned to student successfully.", "success")
    return redirect(url_for('teacher_dashboard'))

# ----------------------------------------------------
# Admin Dashboard & Features
# ----------------------------------------------------
@app.route('/admin/dashboard')
@role_required('admin')
def admin_dashboard():
    # Admin metrics
    users = User.query.all()
    total_users = len(users)
    admins_count = sum(1 for u in users if u.role == 'admin')
    teachers_count = sum(1 for u in users if u.role == 'teacher')
    students_count = sum(1 for u in users if u.role == 'student')
    
    # Retrieve models status
    model_trained = os.path.exists(os.path.join(os.path.dirname(__file__), "student_risk_model.joblib"))
    
    return render_template(
        'admin_dashboard.html',
        users=users,
        total_users=total_users,
        admins_count=admins_count,
        teachers_count=teachers_count,
        students_count=students_count,
        model_trained=model_trained
    )

@app.route('/admin/retrain', methods=['POST'])
@role_required('admin')
def retrain_model_route():
    # Get all student profiles in the database
    db_students = StudentProfile.query.all()
    
    # Train ML models
    result = train_model(db_students)
    
    if result["status"] == "success":
        # Recalculate predictions for all students in the database with the newly fitted model
        for student_prof in db_students:
            run_and_save_prediction(student_prof.student_id)
            
        flash(f"ML Model Retraining Successful! Trained on {result['samples_trained']} samples. Accuracy: Risk {result['risk_accuracy']}%, Grade {result['grade_accuracy']}%", "success")
    else:
        flash("ML Model Retraining Failed.", "danger")
        
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@role_required('admin')
def delete_user(user_id):
    if user_id == session['user_id']:
        flash("You cannot delete your own account.", "danger")
        return redirect(url_for('admin_dashboard'))
        
    user = User.query.get(user_id)
    if user:
        name = user.name
        db.session.delete(user)
        db.session.commit()
        flash(f"User {name} has been deleted.", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/upload_csv', methods=['POST'])
@role_required('admin')
def upload_csv():
    if 'csv_file' not in request.files:
        flash("No file part in request.", "danger")
        return redirect(url_for('admin_dashboard'))
        
    file = request.files['csv_file']
    if file.filename == '':
        flash("No file selected.", "danger")
        return redirect(url_for('admin_dashboard'))
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Parse CSV
        stream = file.stream.read().decode("utf-8").splitlines()
        reader = csv.DictReader(stream)
        
        imported_count = 0
        skipped_count = 0
        
        for row in reader:
            try:
                name = row.get('name')
                email = row.get('email').strip().lower()
                attendance = float(row.get('attendance_rate', 85.0))
                study_hours = float(row.get('study_hours_per_week', 10.0))
                past_score = float(row.get('past_score', 75.0))
                parental_support = row.get('parental_support_level', 'Medium')
                
                # Check duplication
                existing = User.query.filter_by(email=email).first()
                if existing:
                    skipped_count += 1
                    continue
                    
                # Create user
                u = User(name=name, email=email, role='student')
                u.set_password('student123') # default password
                db.session.add(u)
                db.session.commit()
                
                # Create student profile
                prof = StudentProfile(
                    student_id=u.id,
                    attendance_rate=attendance,
                    study_hours_per_week=study_hours,
                    past_score=past_score,
                    parental_support_level=parental_support
                )
                db.session.add(prof)
                db.session.commit()
                
                # Run prediction
                run_and_save_prediction(u.id)
                imported_count += 1
            except Exception as e:
                db.session.rollback()
                skipped_count += 1
                
        flash(f"CSV Import Completed: {imported_count} students successfully imported. {skipped_count} skipped/duplicates.", "success")
        return redirect(url_for('admin_dashboard'))
        
    flash("Invalid file format. Only CSV files are allowed.", "danger")
    return redirect(url_for('admin_dashboard'))

# ----------------------------------------------------
# Flask /predict endpoint requested by user
# ----------------------------------------------------
@app.route('/predict', methods=['POST'])
@login_required
def predict_endpoint():
    """
    JSON Endpoint to run prediction and return results.
    Takes JSON payload: { "student_id": X } or form parameters.
    """
    if request.is_json:
        data = request.get_json()
        student_id = data.get('student_id')
    else:
        student_id = request.form.get('student_id')
        
    if not student_id:
        return jsonify({"status": "error", "message": "Missing student_id"}), 400
        
    success = run_and_save_prediction(student_id)
    if success:
        profile = StudentProfile.query.filter_by(student_id=student_id).first()
        return jsonify({
            "status": "success",
            "student_id": student_id,
            "predicted_risk": profile.predicted_risk,
            "predicted_grade": profile.predicted_grade
        })
    else:
        return jsonify({"status": "error", "message": "Student profile not found"}), 404

# ----------------------------------------------------
# Mock Seeding Data Function
# ----------------------------------------------------
def seed_mock_data():
    """Seeds the database with 20 students, assessments, and standard admin/teachers."""
    if User.query.first() is not None:
        return  # already seeded
        
    print("Seeding database with default records...")
    
    # 1. Create Admin
    admin = User(name="System Administrator", email="admin@learning.com", role="admin")
    admin.set_password("admin123")
    db.session.add(admin)
    
    # 2. Create Teacher
    teacher = User(name="Dr. Sarah Jenkins", email="teacher@learning.com", role="teacher")
    teacher.set_password("teacher123")
    db.session.add(teacher)
    
    db.session.commit()
    
    # 3. Create 20 students with diverse stats
    mock_students = [
        ("Alice Cooper", "alice@learning.com", 95.0, 18.0, 92.0, "High"),
        ("Bob Marley", "bob@learning.com", 58.0, 4.0, 50.0, "Low"),
        ("Charlie Chaplin", "charlie@learning.com", 85.0, 12.0, 78.0, "Medium"),
        ("Diana Prince", "diana@learning.com", 98.0, 22.0, 95.0, "High"),
        ("Ethan Hunt", "ethan@learning.com", 72.0, 6.0, 62.0, "Low"),
        ("Fiona Gallagher", "fiona@learning.com", 61.0, 5.0, 48.0, "Medium"),
        ("George Clooney", "george@learning.com", 88.0, 14.0, 83.0, "High"),
        ("Hannah Baker", "hannah@learning.com", 52.0, 3.0, 45.0, "Low"),
        ("Ian Somerhalder", "ian@learning.com", 79.0, 9.0, 71.0, "Medium"),
        ("Jessica Alba", "jessica@learning.com", 92.0, 16.0, 88.0, "High"),
        ("Kevin Hart", "kevin@learning.com", 67.0, 7.0, 58.0, "Medium"),
        ("Lara Croft", "lara@learning.com", 94.0, 20.0, 91.0, "High"),
        ("Michael Jordan", "michael@learning.com", 89.0, 15.0, 85.0, "Medium"),
        ("Natalie Portman", "natalie@learning.com", 97.0, 24.0, 96.0, "High"),
        ("Oliver Queen", "oliver@learning.com", 55.0, 5.0, 52.0, "Low"),
        ("Penelope Cruz", "penelope@learning.com", 83.0, 11.0, 76.0, "Medium"),
        ("Quentin Tarantino", "quentin@learning.com", 76.0, 8.0, 69.0, "Medium"),
        ("Rihanna Fenty", "rihanna@learning.com", 91.0, 13.0, 82.0, "High"),
        ("Steve Rogers", "steve@learning.com", 99.0, 25.0, 98.0, "High"),
        ("Tony Stark", "tony@learning.com", 96.0, 30.0, 99.0, "High")
    ]
    
    subjects = ["Mathematics", "Science", "English"]
    
    for idx, (name, email, attendance, study_hours, past_score, parental_support) in enumerate(mock_students):
        # Create student user
        student = User(name=name, email=email, role="student")
        student.set_password("student123")
        db.session.add(student)
        db.session.commit()
        
        # Create profile
        profile = StudentProfile(
            student_id=student.id,
            attendance_rate=attendance,
            study_hours_per_week=study_hours,
            past_score=past_score,
            parental_support_level=parental_support
        )
        db.session.add(profile)
        db.session.commit()
        
        # Create 3 mock historical assessments for Chart.js progress tracking
        # We vary scores slightly based on their base past score
        scores = [
            max(20.0, min(100.0, past_score - 8.0)),
            max(20.0, min(100.0, past_score + 2.0)),
            max(20.0, min(100.0, past_score - 3.0))
        ]
        
        for s_idx, subject in enumerate(subjects):
            assessment = Assessment(
                student_id=student.id,
                subject=subject,
                score=scores[s_idx],
                total_questions=10,
                # Set sequential past dates so chart shows proper progress
                date_taken=datetime(2026, 5, 10 + s_idx * 4)
            )
            db.session.add(assessment)
            
        db.session.commit()
        
        # Calculate past score average from assessments
        avg_score = sum(scores) / len(scores)
        profile.past_score = round(avg_score, 1)
        db.session.commit()
        
        # Predict initially
        run_and_save_prediction(student.id)
        
    print("Database seeding completed successfully.")

# Initialize DB structure and Seed
with app.app_context():
    db.create_all()
    # Initial seeding of default dataset
    seed_mock_data()
    # Initial ML engine model training
    train_model(StudentProfile.query.all())

if __name__ == '__main__':
    # Render binds dynamically to the PORT environment variable, defaulting to 5000 locally
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
