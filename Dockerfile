FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt 
RUN pip install --no-cache-dir aiohttp-socks

COPY ./code ./code
COPY ./migrations ./migrations


EXPOSE 12345

CMD ["python", "code/run.py"]