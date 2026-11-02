import json
from html.parser import HTMLParser

import httpx


class PolemicaProfileError(ValueError):
    pass


class _ProfileParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.user: dict[str, object] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "site-settings":
            return

        user_json = dict(attrs).get(":user")
        if not user_json:
            return

        try:
            parsed_user = json.loads(user_json)
        except json.JSONDecodeError:
            return

        if isinstance(parsed_user, dict):
            self.user = parsed_user


async def get_polemica_nickname(polemica_id: int) -> str:
    url = f"https://polemicagame.com/profile/{polemica_id}"
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()

    parser = _ProfileParser()
    parser.feed(response.text)
    if parser.user is None:
        raise PolemicaProfileError("Профиль Polemica не найден или недоступен.")

    nickname = parser.user.get("username")
    if not isinstance(nickname, str) or not nickname.strip():
        raise PolemicaProfileError("В профиле Polemica не найден ник.")
    return nickname.strip()
