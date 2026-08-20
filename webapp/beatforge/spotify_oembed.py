"""Busca título + capa de um link do Spotify via oEmbed público
(https://open.spotify.com/oembed) — funciona pra track/álbum/playlist sem
precisar de credencial nenhuma (diferente do Client Credentials Flow que
webapp/musica/spotify_client.py usa pra busca). Degrada em silêncio: se o
link não for do Spotify, a rede falhar ou o formato mudar, devolve None e
quem chamou segue sem metadata — mesma filosofia de webapp/analytics/groq_client.py."""

import requests

_OEMBED_URL = "https://open.spotify.com/oembed"


def buscar_metadata_spotify(link: str) -> dict | None:
    if not link or "open.spotify.com" not in link:
        return None
    try:
        resp = requests.get(_OEMBED_URL, params={"url": link}, timeout=5)
        if resp.status_code != 200:
            return None
        dados = resp.json()
        return {
            "titulo": dados.get("title") or "",
            "capa_url": dados.get("thumbnail_url") or "",
        }
    except Exception:
        return None


def baixar_capa(capa_url: str) -> tuple[bytes, str] | None:
    if not capa_url:
        return None
    try:
        resp = requests.get(capa_url, timeout=5)
        if resp.status_code != 200:
            return None
        mime = resp.headers.get("Content-Type", "image/jpeg").split(";")[0].strip()
        return resp.content, mime
    except Exception:
        return None
