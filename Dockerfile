FROM python:3.8-alpine

RUN adduser -D onlinejudge

WORKDIR /home/mainserver

RUN apk add postgresql-dev gcc python3-dev musl-dev

COPY requirements.txt requirements.txt

RUN python -m venv venv
RUN venv/bin/pip install -r requirements.txt

COPY app app
COPY migrations migrations
COPY onlinejudge.py config.py boot.sh ./
RUN chmod +x boot.sh

ENV FLASK_APP onlinejudge.py

RUN chown -R onlinejudge:onlinejudge ./
USER onlinejudge

EXPOSE 5000
ENTRYPOINT ["./boot.sh"]

