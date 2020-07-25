FROM python:3.8-alpine

RUN adduser -D onlinejudge

WORKDIR /home/mainserver

COPY requirements.txt requirements.txt
RUN python -m venv venv
RUN venv/bin/pip install -r requirements.txt
RUN venv/bin/pip install gunicorn

copy app app
copy migrations migrations
copy onlinejudge.py config.py boot.sh ./
RUN chmod +x boot.sh

ENV FLASK_APP onlinejudge.py

RUN chown -R onlinejudge:onlinejudge ./
USER onlinejudge

EXPOSE 5000
ENTRYPOINT ["./boot.sh"]

