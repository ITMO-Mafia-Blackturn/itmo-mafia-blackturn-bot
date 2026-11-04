FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt 
RUN pip install --no-cache-dir aiohttp-socks

COPY ./code ./code
COPY ./migration_add_passes_sent.sql ./migration_add_passes_sent.sql
COPY ./migration_tournament_passes_sent.sql ./migration_tournament_passes_sent.sql
COPY ./migration_tournaments.sql ./migration_tournaments.sql
COPY ./migration_tournament_guest_capacity.sql ./migration_tournament_guest_capacity.sql

EXPOSE 12345

CMD ["python", "code/run.py"]