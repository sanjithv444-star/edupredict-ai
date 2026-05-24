import os
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib

# Paths for saved models
MODEL_DIR = os.path.dirname(os.path.abspath(__file__))
RISK_MODEL_PATH = os.path.join(MODEL_DIR, "student_risk_model.joblib")
GRADE_MODEL_PATH = os.path.join(MODEL_DIR, "student_grade_model.joblib")

def encode_parental_support(level):
    """Maps parental support level string to numeric value."""
    mapping = {'Low': 1, 'Medium': 2, 'High': 3}
    return mapping.get(level, 2)

def generate_synthetic_data(num_samples=250):
    """Generates a statistically realistic synthetic dataset for robust model training."""
    np.random.seed(42)
    attendance = np.random.uniform(50, 100, num_samples)
    study_hours = np.random.uniform(2, 35, num_samples)
    past_score = np.random.uniform(40, 100, num_samples)
    parental_support = np.random.choice([1, 2, 3], size=num_samples, p=[0.25, 0.5, 0.25])
    
    # Calculate a composite score that determines the risk and grade
    # Scale variables to 0-100 impact
    norm_study = np.clip(study_hours * 3.0, 0, 100)
    norm_parent = parental_support * 33.3
    
    composite = (0.35 * attendance + 
                 0.25 * norm_study + 
                 0.30 * past_score + 
                 0.10 * norm_parent)
    
    # Add some noise to simulate real-world variance
    noise = np.random.normal(0, 4, num_samples)
    composite = np.clip(composite + noise, 0, 100)
    
    risks = []
    grades = []
    
    for c in composite:
        if c >= 85:
            grades.append('A')
            risks.append('Safe')
        elif c >= 70:
            grades.append('B')
            risks.append('Safe')
        elif c >= 55:
            grades.append('C')
            risks.append('Medium Risk')
        elif c >= 40:
            grades.append('D')
            risks.append('High Risk')
        else:
            grades.append('F')
            risks.append('High Risk')
            
    df = pd.DataFrame({
        'attendance_rate': attendance,
        'study_hours_per_week': study_hours,
        'past_score': past_score,
        'parental_support_level': parental_support,
        'risk': risks,
        'grade': grades
    })
    return df

def train_model(database_students=None):
    """
    Trains/retrains the random forest classifier.
    Combines real database records (if any) with synthetic data for class balance.
    """
    # 1. Start with synthetic data
    df = generate_synthetic_data(300)
    
    # 2. Append database students if available
    if database_students and len(database_students) > 0:
        db_records = []
        for s in database_students:
            # We only train if student profile and some evaluation label is set
            db_records.append({
                'attendance_rate': s.attendance_rate,
                'study_hours_per_week': s.study_hours_per_week,
                'past_score': s.past_score,
                'parental_support_level': encode_parental_support(s.parental_support_level),
                'risk': s.predicted_risk,
                'grade': s.predicted_grade
            })
        db_df = pd.DataFrame(db_records)
        df = pd.concat([df, db_df], ignore_index=True)
        
    # Features and Targets
    X = df[['attendance_rate', 'study_hours_per_week', 'past_score', 'parental_support_level']]
    y_risk = df['risk']
    y_grade = df['grade']
    
    # Train classifiers
    risk_model = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=8)
    grade_model = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=8)
    
    risk_model.fit(X, y_risk)
    grade_model.fit(X, y_grade)
    
    # Save the models
    joblib.dump(risk_model, RISK_MODEL_PATH)
    joblib.dump(grade_model, GRADE_MODEL_PATH)
    
    # Compute accuracy for reporting
    risk_acc = risk_model.score(X, y_risk)
    grade_acc = grade_model.score(X, y_grade)
    
    return {
        "status": "success",
        "risk_accuracy": round(risk_acc * 100, 2),
        "grade_accuracy": round(grade_acc * 100, 2),
        "samples_trained": len(df)
    }

def predict_student_status(attendance_rate, study_hours_per_week, past_score, parental_support_level):
    """
    Predicts the risk level and grade of a student based on input parameters.
    Automatically trains model files if they do not exist yet.
    """
    # Auto-train if models don't exist
    if not os.path.exists(RISK_MODEL_PATH) or not os.path.exists(GRADE_MODEL_PATH):
        train_model()
        
    try:
        risk_model = joblib.load(RISK_MODEL_PATH)
        grade_model = joblib.load(GRADE_MODEL_PATH)
    except Exception as e:
        # Fallback to rules-based mechanism if loading fails
        print(f"Error loading model: {e}. Falling back to rule-based engine.")
        return predict_fallback(attendance_rate, study_hours_per_week, past_score, parental_support_level)
        
    # Prepare input feature vector
    encoded_parent = encode_parental_support(parental_support_level)
    features = pd.DataFrame([[attendance_rate, study_hours_per_week, past_score, encoded_parent]],
                            columns=['attendance_rate', 'study_hours_per_week', 'past_score', 'parental_support_level'])
    
    # Run predictions
    risk_prediction = risk_model.predict(features)[0]
    grade_prediction = grade_model.predict(features)[0]
    
    return risk_prediction, grade_prediction

def predict_fallback(attendance, study_hours, past_score, parental_support_level):
    """Rule-based fallback if ML model is unavailable."""
    encoded_parent = encode_parental_support(parental_support_level)
    norm_study = min(study_hours * 3.0, 100)
    norm_parent = encoded_parent * 33.3
    
    composite = (0.35 * attendance + 
                 0.25 * norm_study + 
                 0.30 * past_score + 
                 0.10 * norm_parent)
    
    if composite >= 85:
        return 'Safe', 'A'
    elif composite >= 70:
        return 'Safe', 'B'
    elif composite >= 55:
        return 'Medium Risk', 'C'
    elif composite >= 40:
        return 'High Risk', 'D'
    else:
        return 'High Risk', 'F'
