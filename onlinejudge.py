from app import app
from app import app, db
from app.models import User, Problem, Announcement, SampleCase, Contest, Registration, Submission

@app.shell_context_processor
def make_shell_context():
    return {
        "db": db, 
        "User": User, 
        "Problem": Problem,
        "Announcement": Announcement,
        "SampleCase": SampleCase,
        "Contest": Contest,
        "Registration": Registration,
        "Submission": Submission
        }