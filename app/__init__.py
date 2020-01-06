from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from config import Config
import rq
from redis import Redis

from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView

from flask_ckeditor import CKEditor, CKEditorField


app = Flask(__name__)
app.config.from_object(Config)

app.redis = Redis.from_url(app.config["REDIS_URL"])
app.task_queue = rq.Queue("evaluation-tasks", connection=app.redis)

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login = LoginManager(app)
login.login_view = "login"

# Admin stuff
ckeditor = CKEditor(app)
admin = Admin(app, template_mode='bootstrap3')

class RichView(ModelView):
    form_overrides = dict(body=CKEditorField)
    create_template = 'edit.html'
    edit_template = 'edit.html'

from app.models import User, Problem, Contest, Registration, Submission, Announcement, SampleCase

admin.add_view(RichView(Announcement, db.session))
admin.add_view(ModelView(User, db.session))
admin.add_view(RichView(Problem, db.session))
admin.add_view(ModelView(Contest, db.session))
admin.add_view(ModelView(Registration, db.session))
admin.add_view(ModelView(Submission, db.session))
admin.add_view(RichView(SampleCase, db.session))

from app import routes, models