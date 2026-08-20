"""Busca título + capa de um link do Spotify via oEmbed público
(https://open.spotify.com/oembed) — funciona pra track/álbum/playlist sem
precisar de credencial nenhuma (diferente do Client Credentials Flow que
webapp/musica/spotify_client.py usa pra busca). Degrada em silêncio: se o
link não for do Spotify, a rede falhar ou o formato mudar, devolve None e
quem chamou segue sem metadata — mesma filosofia de webapp/analytics/groq_client.py."""

import re

import requests

_OEMBED_URL = "https://open.spotify.com/oembed"

# Links compartilhados pelo app do Spotify vêm às vezes com um prefixo de
# idioma no meio do caminho (ex.: open.spotify.com/intl-pt/track/<id>) — o
# endpoint de oEmbed não reconhece essa variante e devolve vazio. Normaliza
# pro formato canônico antes de consultar (o link original continua sendo o
# que fica salvo/exibido, só a consulta usa a versão limpa).
_SPOTIFY_LINK_RE = re.compile(
    r"open\.spotify\.com/(?:intl-[a-z]{2}/)?(track|album|playlist|artist|episode|show)/([A-Za-z0-9]+)"
)


def _normalizar_link(link: str) -> str | None:
    m = _SPOTIFY_LINK_RE.search(link or "")
    if not m:
        return None
    tipo, spotify_id = m.groups()
    return f"https://open.spotify.com/{tipo}/{spotify_id}"


def buscar_metadata_spotify(link: str) -> dict | None:
    link_normalizado = _normalizar_link(link)
    if not link_normalizado:
        return None
    try:
        resp = requests.get(_OEMBED_URL, params={"url": link_normalizado}, timeout=5)
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
