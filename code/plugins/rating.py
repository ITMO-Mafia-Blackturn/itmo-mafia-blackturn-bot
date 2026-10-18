import json

import requests

from database.models import UserProfile
from database.requests import get_users_with_polemica_id
from utils import setup_logger
from html import escape

from datetime import date, timedelta, datetime

logger = setup_logger()


async def get_club_rating() -> str:
    
    today = date.today().strftime("%Y-%m-%d")
    dt = datetime.now() - timedelta(seconds=1)
    hms = dt.strftime("%H:%M:%S.%f")[:-3]
    
    resp = requests.get(
        f"https://app.polemicagame.com/v1/clubs/289/metrics?startDate=2024-09-01T00:00:00.000&endDate={today}T{hms}")
    if resp.status_code != 200:
        logger.warn(resp.text)
        return "Неизвестная ошибка"
    data = json.loads(resp.text)
    registered_users: list[UserProfile] = list(await get_users_with_polemica_id())
    ranking = []
    for user in data:
        db_users = list(filter(lambda it: it.polemica_id == user["id"], registered_users))
        if len(db_users) == 0:
            continue
        db_user: UserProfile = db_users[0]

        username = db_user.nickname
        # Суммируем totalScores и totalAwards из всех категорий
        total_score = sum(category["totalScores"] for category in user["metrics"].values())
        total_awards = sum(category["totalAwards"] for category in user["metrics"].values())
        total_games = sum(category["games"] for category in user["metrics"].values())

        # Добавляем пользователя в рейтинг
        ranking.append({"username": username, "totalScores": total_score, "totalAwards": total_awards, "totalGames": total_games})

    # Сортируем рейтинг по totalScores в порядке убывания
    ranking = sorted(ranking, key=lambda x: x["totalScores"], reverse=True)
    top10 = ranking[:10]
    
    # Выводим топ-результат
    ranks_texts = [f"<pre>{"СТАТИСТИКА КЛУБА".center(59)}\n\n",
                   f"{'#':>2}. {'Ник':<27} {'Сумма баллов':>10} {'Средний балл':>10}",
                   f'{"-" * 59}']
    for rank, user in enumerate(top10, 1):
        username = escape(user["username"])
        avg = user["totalScores"] / user["totalGames"]

        ranks_texts.append(
            f"{rank:>2}. {username:<27} "
            f"{user['totalScores']:>10.2f} "
            f"{avg:>10.4f}"
        )
    return f'<pre>{"\n".join(ranks_texts)}</pre>'
