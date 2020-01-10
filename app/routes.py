from flask import render_template, flash, redirect, url_for, request, jsonify
from flask_login import current_user, login_user, logout_user, login_required
from werkzeug.urls import url_parse

from app import app, db
from app.models import User, Submission, Problem, Announcement, Contest, Registration
from app.forms import LoginForm, SubmissionForm, RegistrationForm, ContestForm
from datetime import datetime

from redis import Redis
import json
import sys

def get_kwargs():
    return {"login_form": LoginForm(), "registration_form": RegistrationForm(), "current_time": datetime.utcnow()}

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

    return render_template("contest.html", contest=c, form=form, registration=registration, **get_kwargs())


@app.route('/problem/<int:id>', methods = ["GET", "POST"])
def problem(id):
    p = Problem.query.get(id)

    if (p.contest and p.contest.start_time >= datetime.utcnow()) and (not current_user.is_authenticated or current_user.is_admin):
        flash("This question cannot be accessed before the contest starts!")
        return redirect(url_for("index"))

    form = SubmissionForm()

    submission = None
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to be logged in to perform this action.")
        if form.code.data == "":
            flash("The source code must not be empty.")
        elif sys.getsizeof(form.code.data) > 512000:
            flash("File size limit exceeded. The source code must be at most 512 kb.")
        else:
            submission = Submission(        
                author = current_user,
                problem = Problem.query.get(id),
                code = form.code.data,
                language = form.language.data
            )

            db.session.add(submission)
            db.session.commit()

            submission.launch_task()        

    return render_template("problem.html", problem=p, form=form, submission=submission, **get_kwargs())

@app.route("/submission/<int:id>", methods = ["GET"])
def submission(id):
    s = Submission.query.get(id)

    if datetime.utcnow() <= s.problem.contest.end_time and current_user != s.author:
        flash("You can only view this submission when the contest ends!")
        return redirect(url_for("index"))

    try:
        testcases = json.loads(s.testcases)
    except:
        testcases = None

    return render_template("submission.html", submission=s, testcases=testcases, **get_kwargs())

@app.route("/contest/<int:id>/leaderboard")
def leaderboard(id):
    registrations = Registration.query.filter_by(contest_id=id).order_by(Registration.score.desc(), Registration.last_submission)
    contest = Contest.query.get(id)

    problems = []

    for problem in contest.problems:
        data = {
            "id": problem.id,
            "score": problem.points,
            "users": {}
        }

        for registration in registrations:
            submission = Submission.query.filter_by(status=0, author=registration.contestant, problem_id=problem.id).order_by(Submission.timestamp).first()

            if submission and contest.start_time <= submission.timestamp <= contest.end_time:
                data["users"][registration.user_id] = submission

        problems.append(data)

    problems.sort(key=lambda x: x["score"])

    return render_template("leaderboard.html", problems=problems, registrations=registrations, contest=contest, **get_kwargs())


@app.route("/problems", methods = ["GET"])
def problem_list():
    problems = Problem.query.all()

    return render_template("problem_list.html", problems=problems, **get_kwargs())

@app.route("/contests", methods = ["GET"])
def contest_list():
    contests = Contest.query.all()

    return render_template("contest_list.html", contests=contests, **get_kwargs())

@app.route("/submissions", methods = ["GET"])
def submission_list():
    contest_id = request.args.get("contest")
    page = request.args.get("page", 1, type=int)


    if contest_id:
        contest = Contest.query.get(contest_id)
        submissions = Submission.query.filter(Submission.problem.has(contest=contest)).order_by(Submission.timestamp.desc())
    else:
        submissions = Submission.query.order_by(Submission.timestamp.desc())

    return render_template("submission_list.html", submissions=submissions.paginate(page, 20).items, **get_kwargs())

@app.route('/api/submission/<int:id>')
def get_submission(id):
    submission = current_user.submissions.filter_by(id=id).first()

    return jsonify({
        "progress": submission.get_progress(),
        "status": submission.status
    })

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))