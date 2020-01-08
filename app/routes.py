from flask import render_template, flash, redirect, url_for, request, jsonify
from flask_login import current_user, login_user, logout_user, login_required
from werkzeug.urls import url_parse

from app import app, db
from app.models import User, Submission, Problem, Announcement, Contest, Registration
from app.forms import LoginForm, SubmissionForm, RegistrationForm, ContestForm
from datetime import datetime

from redis import Redis
import json

def get_kwargs():
    return {"login_form": LoginForm(), "registration_form": RegistrationForm()}

@app.route('/')
@app.route('/index')
def index():
    posts = Announcement.query.order_by(Announcement.timestamp.desc()).all()
    return render_template("index.html", posts=posts, **get_kwargs())

@app.route('/register', methods=['POST'])
def register():
    form = RegistrationForm()

    if form.validate_on_submit():
        user = User(username=form.username.data.lower(), email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        flash("Congratulations! You have succesfully registered.")
    
    return redirect(url_for('index'))

@app.route('/login', methods=['POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.lower()).first()

        if user is None or not user.check_password(form.password.data):
            flash("Invalid username or password!!")
        else:
            login_user(user, remember=form.remember_me.data)
            flash(f"Welcome back {form.username.data.lower().capitalize()}!")

    return redirect(url_for("index"))

# TODO: Add ongoing option
@app.route("/contest/<int:id>", methods = ["GET", "POST"])
def contest(id):
    c = Contest.query.get(id)
    form = ContestForm()

    registration = None
    if current_user.is_authenticated:
        registration = Registration.query.filter_by(user_id=current_user.id, contest_id=id).first()

        if form.validate_on_submit() and datetime.utcnow() <= c.start_time:
            if registration:
                db.session.delete(registration)
                registration = None
                flash("You are now unregistered for this contest.")
            else:
                registration = Registration(contestant=current_user, contest=c)
                db.session.add(registration)
                flash("You are now registered for this contest.")
        
        db.session.commit()

    return render_template("contest.html", contest=c, form=form, registration=registration, current_time=datetime.utcnow(), **get_kwargs())


@app.route('/problem/<int:id>', methods = ["GET", "POST"])
def problem(id):
    p = Problem.query.get(id)

    if p.contest and p.contest.start_time >= datetime.utcnow():
        return redirect(url_for("index"))

    form = SubmissionForm()

    # TODO: Error handling when the user is not authenticated
    submission = None
    if form.validate_on_submit() and current_user.is_authenticated:
        submission = Submission(        
            author = current_user,
            problem = Problem.query.filter_by(id=id).first(),
            code = form.code.data,
            language = form.language.data
        )

        # TODO: Check that code isn't too big

        db.session.add(submission)
        db.session.commit()

        submission.launch_task()
        # TODO: Prompt user with notification showing the status of the task

    return render_template("problem.html", problem=p, form=form, submission=submission, **get_kwargs())

@app.route("/submission/<int:id>", methods = ["GET"])
def submission(id):
    s = Submission.query.get(id)

    try:
        testcases = json.loads(s.testcases)
    except:
        testcases = None

    return render_template("submission.html", submission=s, testcases=testcases, **get_kwargs())

@app.route("/problems", methods = ["GET"])
def problem_list():
    problems = Problem.query.all()

    return render_template("problem_list.html", problems=problems, **get_kwargs())

@app.route("/contests", methods = ["GET"])
def contest_list():
    contests = Contest.query.all()

    return render_template("contest_list.html", current_time=datetime.utcnow(), contests=contests, **get_kwargs())

@app.route("/submissions", methods = ["GET"])
def submission_list():
    submissions = Submission.query.order_by(Submission.timestamp.desc()).all()

    return render_template("submission_list.html", submissions=submissions, **get_kwargs())

@app.route('/api/submission/<int:id>')
def get_submission(id):
    if current_user.is_authenticated:
        submission = current_user.submissions.filter_by(id=id).first()

        return jsonify({
            "progress": submission.get_progress(),
            "status": submission.status
        })

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))