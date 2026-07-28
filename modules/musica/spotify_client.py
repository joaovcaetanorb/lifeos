"""Integração com a Web API do Spotify via spotipy — só busca de metadado
público (nome, artista, ano, capa). Nunca lê o que o usuário está ouvindo
nem precisa de login pessoal (Client Credentials Flow, credenciais de app
em .streamlit/secrets.toml).

Qualquer falha aqui (sem credencial configurada, erro de rede, timeout)
degrada pra "recurso indisponível" em vez de quebrar a página — a busca é
um atalho opcional, o cadastro manual sempre continua funcionando.
"""

import requests
import spotipy
import streamlit as st
from spotipy.oauth2 import SpotifyClientCredentials


@st.cache_resource(show_spinner=False)
def _get_client() -> spotipy.Spotify | None:
    try:
        client_id = st.secrets["SPOTIFY_CLIENT_ID"]
        client_secret = st.secrets["SPOTIFY_CLIENT_SECRET"]
    except (KeyError, FileNotFoundError):
        return None
    auth = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    return spotipy.Spotify(client_credentials_manager=auth)


def disponivel() -> bool:
    return _get_client() is not None


def buscar_albuns(query: str, limit: int = 5) -> list[dict]:
    """[{nome, artista, artista_spotify_id, ano, capa_url, spotify_id,
    spotify_url}, ...]. Lista vazia se indisponível, sem resultado, ou erro."""
    sp = _get_client()
    if sp is None or not query.strip():
        return []
    try:
        resultado = sp.search(q=query, type="album", limit=limit)
    except Exception:
        return []

    albuns = []
    for item in resultado.get("albums", {}).get("items", []):
        artista = item["artists"][0] if item["artists"] else {}
        albuns.append({
            "nome": item["name"],
            "artista": artista.get("name", ""),
            "artista_spotify_id": artista.get("id", ""),
            "ano": int(item["release_date"][:4]) if item.get("release_date") else None,
            "capa_url": item["images"][0]["url"] if item.get("images") else "",
            "spotify_id": item["id"],
            "spotify_url": item.get("external_urls", {}).get("spotify", ""),
        })
    return albuns


def buscar_faixas(album_spotify_id: str) -> list[str]:
    """Nomes das faixas do álbum, na ordem do disco. Lista vazia se
    indisponível, id inválido, ou erro de rede."""
    sp = _get_client()
    if sp is None or not album_spotify_id:
        return []
    try:
        resultado = sp.album_tracks(album_spotify_id)
    except Exception:
        return []
    return [faixa["name"] for faixa in resultado.get("items", [])]


def baixar_capa(url: str) -> bytes | None:
    if not url:
        return None
    try:
        resposta = requests.get(url, timeout=10)
        resposta.raise_for_status()
        return resposta.content
    except Exception:
        return None
