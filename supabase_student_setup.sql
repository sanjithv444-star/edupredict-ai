-- ============================================================
-- EduPredict AI — Supabase PostgreSQL Database Setup
-- Project: sanjithv444-star
-- ============================================================
-- Run this ENTIRE script in your Supabase SQL Editor:
-- (Dashboard → SQL Editor → New Query → Paste → Run)
-- ============================================================

-- 1. Create Users Table
-- ============================================
CREATE TABLE IF NOT EXISTS public.users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'teacher', 'student'))
);

-- 2. Create Student Profiles Table (extends users table for students)
-- ============================================
CREATE TABLE IF NOT EXISTS public.student_profiles (
    student_id INTEGER PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
    attendance_rate FLOAT DEFAULT 90.0 CHECK (attendance_rate BETWEEN 0.0 AND 100.0),
    study_hours_per_week FLOAT DEFAULT 10.0 CHECK (study_hours_per_week >= 0.0),
    past_score FLOAT DEFAULT 75.0 CHECK (past_score BETWEEN 0.0 AND 100.0),
    parental_support_level VARCHAR(20) DEFAULT 'Medium' CHECK (parental_support_level IN ('Low', 'Medium', 'High')),
    predicted_risk VARCHAR(20) DEFAULT 'Safe' CHECK (predicted_risk IN ('Safe', 'Medium Risk', 'High Risk')),
    predicted_grade VARCHAR(5) DEFAULT 'B' CHECK (predicted_grade IN ('A', 'B', 'C', 'D', 'F'))
);

-- 3. Create Assessments Table
-- ============================================
CREATE TABLE IF NOT EXISTS public.assessments (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    subject VARCHAR(100) NOT NULL,
    score FLOAT NOT NULL,
    total_questions INTEGER NOT NULL,
    date_taken TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Create Recommendations Table
-- ============================================
CREATE TABLE IF NOT EXISTS public.recommendations (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    resource_title VARCHAR(200) NOT NULL,
    resource_url VARCHAR(255) NOT NULL,
    status VARCHAR(20) DEFAULT 'recommended' CHECK (status IN ('recommended', 'completed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 5. Indexes (for maximum performance)
-- ============================================
CREATE INDEX IF NOT EXISTS idx_users_role ON public.users(role);
CREATE INDEX IF NOT EXISTS idx_student_profiles_predicted_risk ON public.student_profiles(predicted_risk);
CREATE INDEX IF NOT EXISTS idx_assessments_student ON public.assessments(student_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_student ON public.recommendations(student_id);

-- ============================================
-- Schema verification message
-- ============================================
-- Your Supabase PostgreSQL database tables are ready!
-- Ready for seeding and predictions.
-- ============================================
