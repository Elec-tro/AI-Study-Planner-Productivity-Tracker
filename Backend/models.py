from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    color = db.Column(db.String(20), default="#4F46E5")
    tasks = db.relationship('Task', backref='subject', lazy=True, cascade="all, delete-orphan")

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    deadline = db.Column(db.DateTime, nullable=False)
    difficulty = db.Column(db.Integer, default=3) # 1-5
    estimated_hours = db.Column(db.Float, default=1.0)
    status = db.Column(db.String(20), default="pending") # pending, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    schedules = db.relationship('Schedule', backref='task', lazy=True, cascade="all, delete-orphan")

class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(10), nullable=True) # e.g. "09:00"
    duration_minutes = db.Column(db.Integer, nullable=False)

class UserStats(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)
    tasks_completed = db.Column(db.Integer, default=0)
    study_hours = db.Column(db.Float, default=0.0)
    streak = db.Column(db.Integer, default=0)
