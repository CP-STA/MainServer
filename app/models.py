from app import db, login
from datetime import datetime
from flask_login import UserMixin
from flask import current_app
import redis
import rq

from werkzeug.security import generate_password_hash, check_password_hash

class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(64))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    body = db.Column(db.Text)
    contest_id = db.Column(db.Integer, default = -1)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(128), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)

    github_link = db.Column(db.String(128))
    registration_time = db.Column(db.DateTime, default=datetime.utcnow)

    submissions = db.relationship('Submission', backref='author', lazy='dynamic')
    contests = db.relationship('Registration', backref='contestant', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login.user_loader
def load_user(id):
    return User.query.get(int(id))

class Problem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contest_id = db.Column(db.Integer, db.ForeignKey("contest.id"))

    title = db.Column(db.String(64))
    body = db.Column(db.Text)

    points = db.Column(db.Integer, index=True)
    difficulty = db.Column(db.String(16), index=True)

    time_limit = db.Column(db.Integer)
    memory_limit = db.Column(db.Integer)

    submissions = db.relationship('Submission', backref='problem', lazy='dynamic')
    sample_cases = db.relationship("SampleCase", backref="problem", lazy="dynamic")

class SampleCase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    problem_id = db.Column(db.Integer, db.ForeignKey("problem.id"))

    title = db.Column(db.String(64))
    input_text = db.Column(db.Text)
    output_text = db.Column(db.Text)

    body = db.Column(db.Text)

class Contest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(64))
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)

    # NOTE: Not sure whether text or link to pdf
    editorial = db.Column(db.String(5000))

    registrations = db.relationship("Registration", backref="contest", lazy="dynamic")
    problems = db.relationship("Problem", backref="contest", lazy="dynamic")

class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    contest_id = db.Column(db.Integer, db.ForeignKey("contest.id"))

    score = db.Column(db.Integer, default=0, index=True)
    last_submission = db.Column(db.DateTime, index=True)

class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    problem_id = db.Column(db.Integer, db.ForeignKey("problem.id"))

    # Not that important
    task_id = db.Column(db.String(64))

    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    code = db.Column(db.Text)
    language = db.Column(db.String(16))

    status = db.Column(db.Integer, default = -2)
    testcases = db.Column(db.Text)

    # Final progress isn't recorded until the end. 
    progress = db.Column(db.String(16), default = "0/0")

    # NOTE: This is to launch the task on the Redis Server
    
    # TODO: Submissions page should use pagination and show only about 10 at a time
    # TODO: Admin page should have restrictions to admin users only
    # TODO: Rate limiting

    def launch_task(self):
        contest = self.problem.contest

        registration = Registration.query.filter_by(contest_id = contest.id, user_id = self.user_id).first()
        first_submission = not Submission.query.filter_by(user_id = self.user_id, problem_id = self.problem_id, status = 0).first()

        registration_id = None

        # Also need to check that the user haven't solved this question before.
        if registration and self.timestamp <= contest.end_time and first_submission:
            registration_id = registration.id

        rq_job = current_app.task_queue.enqueue('server.evaluate_submission', self.id, self.language, self.code,
        self.problem.memory_limit * 1024 ** 2, self.problem.time_limit, 
        self.problem.id, registration_id, self.problem.points)

        self.task_id = rq_job.get_id()
        db.session.commit()
        
        return self.task_id

    def get_rq_job(self):
        try:
            rq_job = rq.job.Job.fetch(self.task_id, connection=current_app.redis)
        except (redis.exceptions.RedisError, rq.exceptions.NoSuchJobError):
            return None

        return rq_job
    
    def get_progress(self):
        job = self.get_rq_job()
        return job.meta.get("progress", "0/0") if job else self.progress
