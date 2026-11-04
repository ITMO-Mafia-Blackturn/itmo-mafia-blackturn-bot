from html.parser import HTMLParser

import httpx


class PolemicaProfileError(ValueError):
    pass


class _ProfileParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)


async def get_polemica_nickname(polemica_id: int) -> str:
    url = f"https://polemicagame.com/profile/{polemica_id}"
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()

    parser = _ProfileParser()
    parser.feed(response.text)
    title = "".join(parser.title_parts).strip()
    print()
    print(response.text, title, sep = "\n")
    print()
    if "–" not in title:
        raise PolemicaProfileError("Профиль Polemica не найден или недоступен.")

    nickname = title.split("–", maxsplit=1)[0].strip()
    if not nickname:
        raise PolemicaProfileError("В заголовке профиля Polemica не найден ник.")

    return nickname
