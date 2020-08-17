#!/bin/sh

source venv/bin/activate
flask db init
flask db upgrade
exec gunicorn -b :5000 onlinejudge:app