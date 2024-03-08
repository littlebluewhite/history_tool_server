FROM python:3.12-alpine

WORKDIR /app

ENV CONN_SQL_HOST 127.0.0.1
ENV CONN_REDIS_HOST 127.0.0.1
ENV CONN_INFLUXDB_HOST 127.0.0.1

EXPOSE 9488

COPY . .

RUN apk add --no-cache gcc musl-dev libffi-dev openssl-dev make
RUN pip install --upgrade pip
RUN pip install --no-cache-dir --upgrade -r ./requirements.txt

CMD python3.12 main.py