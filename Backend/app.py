from flask import Flask, request, jsonify
from flask_cors import CORS
from models import db, Subject, Task, Schedule, UserStats
from datetime import datetime, timedelta, date
import math

app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///focusflow.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()

# --- Subjects ---
@app.route('/api/subjects', methods=['GET', 'POST'])
def handle_subjects():
    if request.method == 'GET':
        subjects = Subject.query.all()
        return jsonify([{'id': s.id, 'name': s.name, 'color': s.color} for s in subjects])
    
    data = request.json
    new_subject = Subject(name=data['name'], color=data.get('color', '#4F46E5'))
    db.session.add(new_subject)
    db.session.commit()
    return jsonify({'id': new_subject.id, 'name': new_subject.name, 'color': new_subject.color}), 201

@app.route('/api/subjects/<int:id>', methods=['DELETE'])
def delete_subject(id):
    subject = Subject.query.get_or_404(id)
    db.session.delete(subject)
    db.session.commit()
    return '', 204

# --- Tasks ---
@app.route('/api/tasks', methods=['GET', 'POST'])
def handle_tasks():
    if request.method == 'GET':
        tasks = Task.query.all()
        return jsonify([{
            'id': t.id,
            'subject_id': t.subject_id,
            'subject_name': t.subject.name,
            'subject_color': t.subject.color,
            'title': t.title,
            'deadline': t.deadline.isoformat(),
            'difficulty': t.difficulty,
            'estimated_hours': t.estimated_hours,
            'status': t.status
        } for t in tasks])
    
    data = request.json
    new_task = Task(
        subject_id=data['subject_id'],
        title=data['title'],
        deadline=datetime.fromisoformat(data['deadline'].replace('Z', '')),
        difficulty=data.get('difficulty', 3),
        estimated_hours=data.get('estimated_hours', 1.0)
    )
    db.session.add(new_task)
    db.session.commit()
    return jsonify({'id': new_task.id, 'title': new_task.title}), 201

@app.route('/api/tasks/<int:id>', methods=['PUT', 'DELETE'])
def update_task(id):
    task = Task.query.get_or_404(id)
    if request.method == 'DELETE':
        db.session.delete(task)
        db.session.commit()
        return '', 204
    
    data = request.json
    if 'status' in data:
        task.status = data['status']
        if task.status == 'completed':
            # Update stats
            today = date.today()
            stat = UserStats.query.filter_by(date=today).first()
            if not stat:
                # Simple streak logic: check yesterday
                yesterday = today - timedelta(days=1)
                prev_stat = UserStats.query.filter_by(date=yesterday).first()
                new_streak = (prev_stat.streak + 1) if prev_stat else 1
                stat = UserStats(date=today, tasks_completed=1, study_hours=task.estimated_hours, streak=new_streak)
                db.session.add(stat)
            else:
                stat.tasks_completed += 1
                stat.study_hours += task.estimated_hours
    
    db.session.commit()
    return jsonify({'id': task.id, 'status': task.status})

# --- Scheduling Algorithm ---
@app.route('/api/schedule/generate', methods=['POST'])
def generate_schedule():
    # Clear existing schedules for future
    today = date.today()
    Schedule.query.filter(Schedule.date >= today).delete()
    
    # User preferences (could be passed in request)
    daily_capacity_hours = request.json.get('daily_hours', 4)
    
    pending_tasks = Task.query.filter_by(status='pending').all()
    
    # Calculate priority scores
    task_priorities = []
    for task in pending_tasks:
        days_left = (task.deadline.date() - today).days
        if days_left < 0: days_left = 0
        # Priority = Difficulty / (Days Left + 1)
        priority = task.difficulty / (days_left + 1)
        task_priorities.append({'task': task, 'priority': priority})
    
    # Sort by priority descending
    task_priorities.sort(key=lambda x: x['priority'], reverse=True)
    
    # Allocation
    current_date = today
    allocated_hours = {current_date: 0.0}
    
    for item in task_priorities:
        task = item['task']
        remaining_hours = task.estimated_hours
        
        # Try to fit in current and future days
        search_date = today
        while remaining_hours > 0:
            if search_date not in allocated_hours:
                allocated_hours[search_date] = 0.0
            
            available_today = daily_capacity_hours - allocated_hours[search_date]
            if available_today > 0:
                hours_to_assign = min(available_today, remaining_hours)
                
                new_sched = Schedule(
                    task_id=task.id,
                    date=search_date,
                    duration_minutes=int(hours_to_assign * 60)
                )
                db.session.add(new_sched)
                
                allocated_hours[search_date] += hours_to_assign
                remaining_hours -= hours_to_assign
            
            search_date += timedelta(days=1)
            # Safety break
            if (search_date - today).days > 60:
                break
                
    db.session.commit()
    return jsonify({'message': 'Schedule generated successfully'})

@app.route('/api/schedule', methods=['GET'])
def get_schedule():
    schedules = Schedule.query.all()
    return jsonify([{
        'id': s.id,
        'task_id': s.task_id,
        'task_title': s.task.title,
        'subject_color': s.task.subject.color,
        'date': s.date.isoformat(),
        'duration_minutes': s.duration_minutes
    } for s in schedules])

@app.route('/api/stats', methods=['GET'])
def get_stats():
    stats = UserStats.query.order_by(UserStats.date.desc()).limit(30).all()
    pending_count = Task.query.filter_by(status='pending').count()
    completed_count = Task.query.filter_by(status='completed').count()
    
    current_streak = 0
    today_stat = UserStats.query.filter_by(date=date.today()).first()
    if today_stat:
        current_streak = today_stat.streak
    else:
        yesterday_stat = UserStats.query.filter_by(date=date.today() - timedelta(days=1)).first()
        if yesterday_stat:
            current_streak = yesterday_stat.streak

    return jsonify({
        'history': [{'date': s.date.isoformat(), 'completed': s.tasks_completed, 'hours': s.study_hours} for s in reversed(stats)],
        'pending_tasks': pending_count,
        'completed_tasks': completed_count,
        'current_streak': current_streak
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
