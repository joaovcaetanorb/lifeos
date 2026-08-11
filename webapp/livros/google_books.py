"""Busca de capa via Google Books API — mesmo papel que
webapp/musica/spotify_service.py.buscar_albuns cumpre pra música: devolve
candidatos pro usuário escolher, sem exigir que ele tire foto ou faça
upload manual da capa.

Exige API key (core.config.settings.google_books_api_key): a cota
"anônima" (sem `key=`) da Google Books API está zerada globalmente hoje
(HTTP 429 / RESOURCE_EXHAUSTED mesmo na primeira chamada) — não é limite
de uso nosso, é a Google que fechou esse caminho. Chave gratuita, criada
em console.cloud.google.com (APIs e Serviços > Credenciais > Criar chave
de API, restrita à Books API).

O `thumbnail` que a Google Books devolve é sempre pequeno (a API não expõe
versão maior pra a maioria dos títulos) — fica borrado quando esticado num
card grande. Pra cada resultado com ISBN, tenta a capa da Open Library
(costuma ser bem maior) antes de aceitar o thumbnail pequeno como
resposta; sem chave, sem custo extra de setup pro usuário."""

import requests

from core.config import settings

_BASE_URL = "https://www.googleapis.com/books/v1/volumes"

# Open Library devolve HTTP 200 com uma imagem de 1x1px (~43 bytes) quando
# não tem capa pro ISBN, em vez de 404 — precisa checar o tamanho da
# resposta pra distinguir "capa de verdade" de "placeholder vazio".
_OPENLIBRARY_PLACEHOLDER_MAX_BYTES = 500


def _isbn13(info: dict) -> str | None:
    for ident in info.get("industryIdentifiers", []):
        if ident.get("type") == "ISBN_13":
            return ident.get("identifier")
    for ident in info.get("industryIdentifiers", []):
        if ident.get("type") == "ISBN_10":
            return ident.get("identifier")
    return None


def _capa_openlibrary(isbn: str) -> str | None:
    url = f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"
    try:
        resposta = requests.get(url, timeout=5)
        resposta.raise_for_status()
        if len(resposta.content) <= _OPENLIBRARY_PLACEHOLDER_MAX_BYTES:
            return None
        return url
    except Exception:
        return None


def buscar_capas(query: str, limit: int = 6) -> list[dict]:
    """[{titulo, autor, capa_url}, ...]. Lista vazia se sem termo de busca,
    sem chave configurada, sem resultado, ou erro de rede — busca de capa é
    auxiliar, não deve quebrar o fluxo de cadastro do livro."""
    if not query.strip() or not settings.google_books_api_key:
        return []
    try:
        params = {"q": query, "maxResults": limit, "key": settings.google_books_api_key}
        resposta = requests.get(_BASE_URL, params=params, timeout=10)
        resposta.raise_for_status()
        dados = resposta.json()
    except Exception:
        return []

    resultado = []
    for item in dados.get("items", []):
        info = item.get("volumeInfo", {})
        capa_google = info.get("imageLinks", {}).get("thumbnail", "")
        if not capa_google:
            continue
        # a API devolve http:// — navegador bloqueia como conteúdo misto
        # numa página https.
        capa_google = capa_google.replace("http://", "https://", 1)

        isbn = _isbn13(info)
        capa_url = (_capa_openlibrary(isbn) if isbn else None) or capa_google
        resultado.append({
            "titulo": info.get("title", ""),
            "autor": ", ".join(info.get("authors", [])),
            "capa_url": capa_url,
        })
    return resultado
