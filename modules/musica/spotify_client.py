"""Integração com a Web API do Spotify via spotipy — só busca de metadado
público (nome, artista, ano, capa, gênero). Nunca lê o que o usuário está
ouvindo nem precisa de login pessoal (Client Credentials Flow, credenciais
de app em .streamlit/secrets.toml) — a conta dona do app precisa ter
Premium ativo pra esse modo de busca funcionar (exigência da própria
Spotify desde início de 2026).

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


def ultimo_erro() -> str | None:
    """Mensagem amigável do último erro de `buscar_albuns`, se houver — pra
    UI distinguir 'sem resultado' de 'a busca falhou'. None enquanto a
    última chamada não deu erro."""
    return st.session_state.get("spotify_ultimo_erro")


def buscar_albuns(query: str, limit: int = 5) -> list[dict]:
    """[{nome, artista, artista_spotify_id, ano, capa_url, spotify_id,
    spotify_url}, ...]. Lista vazia se indisponível, sem resultado, ou erro
    (nesse último caso, `ultimo_erro()` explica o motivo). Gênero não vem
    aqui — a Web API só devolve gênero no recurso de ARTISTA, não no de
    álbum; usar `buscar_genero_artista()` sob demanda (ver
    _campo_faixa_favorita/escolha em diario.py) evita 1 chamada extra por
    resultado da lista pra só usar 1 deles."""
    st.session_state["spotify_ultimo_erro"] = None
    sp = _get_client()
    if sp is None or not query.strip():
        return []
    try:
        resultado = sp.search(q=query, type="album", limit=limit)
    except spotipy.SpotifyException as e:
        if e.http_status == 403:
            st.session_state["spotify_ultimo_erro"] = (
                "Spotify recusou a busca (403): a Web API exige que a conta dona do app "
                "tenha assinatura Premium ativa para usar o modo de busca (Client "
                "Credentials). Confira a assinatura em developer.spotify.com/dashboard — "
                "se já tiver Premium e o erro persistir, tente regenerar o Client Secret do app."
            )
        else:
            st.session_state["spotify_ultimo_erro"] = f"Spotify recusou a busca (HTTP {e.http_status})."
        return []
    except Exception:
        st.session_state["spotify_ultimo_erro"] = "Não foi possível buscar no Spotify agora (erro de rede)."
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


def buscar_genero_artista(artista_spotify_id: str) -> str:
    """Primeiro gênero listado pro artista no Spotify (title-case), ou ""
    se o artista não tem gênero catalogado, id inválido, ou erro de rede.
    Chamado só pro artista JÁ escolhido (não pra cada resultado da busca) —
    é 1 chamada de API a mais, então só vale a pena depois que o usuário
    decidiu qual álbum quer."""
    sp = _get_client()
    if sp is None or not artista_spotify_id:
        return ""
    try:
        artista = sp.artist(artista_spotify_id)
    except Exception:
        return ""
    generos = artista.get("genres", [])
    return generos[0].strip().title() if generos else ""


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
