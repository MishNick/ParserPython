import requests
from bs4 import BeautifulSoup
import urllib.parse
import json
import time

BASE_URL = "https://sd.hostco.ru"
LOGIN_URL = BASE_URL + "/login"

START_PATH = "/projects/amurmis/wiki/%D0%9C%D0%BE%D0%B4%D1%83%D0%BB%D0%B8_WEB_%D0%9C%D0%98%D0%A1"

USERNAME = "amur_mis"
PASSWORD = "1234567890"

session = requests.Session()
visited = set()


def login():
    print("Получение страницы логина...")
    resp = session.get(LOGIN_URL)
    soup = BeautifulSoup(resp.text, "html.parser")

    token_tag = soup.find("input", {"name": "authenticity_token"})
    if not token_tag:
        raise RuntimeError("Не найден authenticity_token — логин невозможен.")

    token = token_tag["value"]

    print("Выполняю вход...")

    data = {
        "username": USERNAME,
        "password": PASSWORD,
        "authenticity_token": token,
        "login": "Войти"
    }

    resp = session.post(LOGIN_URL, data=data)

    if "Выйти" not in resp.text and "Мой профиль" not in resp.text:
        raise RuntimeError("Ошибка входа — проверь логин/пароль.")

    print("Успешный вход.")


def get_soup(path):
    url = urllib.parse.urljoin(BASE_URL, path)

    try:
        resp = session.get(url)
        resp.raise_for_status()
    except requests.HTTPError as e:
        print(f"[!] Страница недоступна (HTTP {resp.status_code}): {url}")
        return None, url
    except Exception as e:
        print(f"[!] Ошибка при загрузке: {url} — {e}")
        return None, url

    return BeautifulSoup(resp.text, "html.parser"), url


def parse_page(path, parents):
    # Нормализация пути
    path = urllib.parse.unquote(path).rstrip("/")

    soup, full_url = get_soup(path)
    if soup is None:
        return {
            "name": path,
            "url": full_url,
            "type": "Missing",
            "parents": parents,
            "data": {},
            "children": []
        }

    # Имя страницы (обычно <h1>)
    title = soup.find("h1")
    name = title.text.strip() if title else path.split("/")[-1]

    node_type = "Document"  # тип можно поменять при необходимости

    # Ищем pdf/html/txt
    data_files = {}

    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        file_url = urllib.parse.urljoin(BASE_URL, a["href"])

        if href.endswith(".pdf"):
            data_files["pdf"] = file_url
        elif href.endswith(".html"):
            data_files["html"] = file_url
        elif href.endswith(".txt"):
            data_files["txt"] = file_url

    children = []

    for a in soup.find_all("a", href=True):
        href = a["href"]

        # Пропуск служебных URL Redmine
        if any(x in href for x in ["/edit", "/history", "/diff", "version=", "?sort=", "&sort="]):
            continue

        # Нам нужны только wiki-страницы проекта
        if "/projects/amurmis/wiki/" not in href:
            continue

        parsed = urllib.parse.urlparse(href)
        child_path = urllib.parse.unquote(parsed.path).rstrip("/")

        if "#" in child_path:
            child_path = child_path.split("#")[0]

        # Пропуск уже посещённых страниц (анти-рекурсивный цикл)
        if child_path in visited:
            continue

        visited.add(child_path)

        time.sleep(0.2)  # лёгкая пауза, чтобы не спамить сервер

        child_node = parse_page(
            child_path,
            parents + [{"name": name, "url": full_url}]
        )

        children.append(child_node)

    return {
        "name": name,
        "url": full_url,
        "type": node_type,
        "parents": parents,
        "data": data_files,
        "children": children
    }

def build_tree():
    visited.add(START_PATH)
    return parse_page(START_PATH, [])

if __name__ == "__main__":
    login()
    print("Строю дерево...")

    tree = build_tree()

    with open("wiki_tree.json", "w", encoding="utf-8") as f:
        json.dump(tree, f, ensure_ascii=False, indent=4)

    print("Готово! Файл wiki_tree.json создан.")