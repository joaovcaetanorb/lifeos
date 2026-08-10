"""Integração com a Web API do Spotify via spotipy — duas formas de auth
diferentes, cada uma pro seu propósito:

1. Client Credentials (`_get_client`) — credenciais do app só, sem login
   de ninguém. Só dá acesso a catálogo público (busca de álbum/artista).
   A conta dona do app precisa ter Premium ativo pra esse modo funcionar
   (exigência da própria Spotify desde início de 2026).
2. Authorization Code (`_get_oauth`) — login de verdade do usuário, com
   tela de consentimento. Dá acesso a dado da conta pessoal (histórico de
   faixas tocadas, top artistas/faixas) que o modo 1 nunca alcança.

Qualquer falha aqui (sem credencial configurada, erro de rede, timeout)
degrada pra "recurso indisponível" em vez de quebrar a página — tanto a
busca de catálogo quanto a conta conectada são atalhos opcionais, o
cadastro manual sempre continua funcionando.
"""

import requests
import spotipy
import streamlit as st
from spotipy.cache_handler import CacheHandler
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth

import models


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


# ---------------------------------------------------------------------------
# Conta conectada (Authorization Code — login de usuário, dado pessoal)
# ---------------------------------------------------------------------------

class _TursoCacheHandler(CacheHandler):
    """Guarda o token OAuth no Turso (via models.py) em vez do arquivo
    local que o spotipy usa por padrão — um arquivo não sobrevive no disco
    efêmero do Streamlit Cloud, e também não faria sentido compartilhar
    entre processos/sessões diferentes."""

    def get_cached_token(self):
        return models.obter_token_spotify()

    def save_token_to_cache(self, token_info):
        models.salvar_token_spotify(token_info)


def _get_oauth() -> SpotifyOAuth | None:
    try:
        client_id = st.secrets["SPOTIFY_CLIENT_ID"]
        client_secret = st.secrets["SPOTIFY_CLIENT_SECRET"]
        redirect_uri = st.secrets["SPOTIFY_REDIRECT_URI"]
    except (KeyError, FileNotFoundError):
        return None
    return SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope="user-read-recently-played user-top-read",
        cache_handler=_TursoCacheHandler(),
        open_browser=False,
    )


def conta_conectada() -> bool:
    """True se há um token salvo e válido — `validate_token` já renova
    sozinho (e persiste a renovação) se o access_token expirou mas o
    refresh_token ainda vale. Se o refresh_token foi revogado (usuário
    desconectou pelo lado da Spotify) essa renovação falha com exceção;
    trata como "não conectado" em vez de derrubar a página."""
    oauth = _get_oauth()
    if oauth is None:
        return False
    token = oauth.cache_handler.get_cached_token()
    if token is None:
        return False
    try:
        return oauth.validate_token(token) is not None
    except Exception:
        return False


def url_autorizacao() -> str | None:
    oauth = _get_oauth()
    return oauth.get_authorize_url() if oauth else None


def completar_conexao(code: str) -> bool:
    """Troca o `code` (query param que a Spotify manda de volta depois do
    login) por um token de verdade, e já deixa salvo via cache_handler."""
    oauth = _get_oauth()
    if oauth is None:
        return False
    try:
        oauth.get_access_token(code, as_dict=True, check_cache=False)
        return True
    except Exception:
        return False


def desconectar() -> None:
    models.limpar_token_spotify()


def _cliente_conta() -> spotipy.Spotify | None:
    if not conta_conectada():
        return None
    return spotipy.Spotify(auth_manager=_get_oauth())


def sincronizar_historico(limit: int = 50) -> int:
    """Puxa as últimas faixas tocadas (a API só devolve até 50, sempre a
    partir de agora pra trás) e salva as que ainda não estavam no
    histórico. Retorna quantas eram novas — 0 em qualquer falha, nunca
    derruba a página."""
    sp = _cliente_conta()
    if sp is None:
        return 0
    try:
        resultado = sp.current_user_recently_played(limit=limit)
    except Exception:
        return 0

    faixas = []
    for item in resultado.get("items", []):
        faixa = item.get("track", {})
        artistas = faixa.get("artists", [])
        album = faixa.get("album", {})
        faixas.append({
            "faixa_nome": faixa.get("name", ""),
            "artista_nome": artistas[0].get("name", "") if artistas else "",
            "album_nome": album.get("name", ""),
            "capa_url": album["images"][0]["url"] if album.get("images") else "",
            "track_spotify_id": faixa.get("id", ""),
            "album_spotify_id": album.get("id", ""),
            "artista_spotify_id": artistas[0].get("id", "") if artistas else "",
            "tocado_em": item.get("played_at", ""),
            "duration_ms": faixa.get("duration_ms", 0),
        })
    faixas = [f for f in faixas if f["faixa_nome"] and f["tocado_em"]]
    if not faixas:
        return 0
    return models.inserir_historico_faixas(faixas)


def top_artistas_conta(time_range: str = "medium_term", limit: int = 10) -> list[dict]:
    """[{nome, capa_url, spotify_url}, ...] — top artistas da conta no
    período (short_term=4 semanas, medium_term=6 meses, long_term=geral).
    Lista vazia se desconectado ou erro."""
    sp = _cliente_conta()
    if sp is None:
        return []
    try:
        resultado = sp.current_user_top_artists(limit=limit, time_range=time_range)
    except Exception:
        return []
    artistas = []
    for item in resultado.get("items", []):
        artistas.append({
            "nome": item.get("name", ""),
            "capa_url": item["images"][0]["url"] if item.get("images") else "",
            "spotify_url": item.get("external_urls", {}).get("spotify", ""),
        })
    return artistas


def top_faixas_conta(time_range: str = "medium_term", limit: int = 10) -> list[dict]:
    """[{nome, artista, album, capa_url, spotify_url}, ...] — top faixas
    da conta no período. Lista vazia se desconectado ou erro."""
    sp = _cliente_conta()
    if sp is None:
        return []
    try:
        resultado = sp.current_user_top_tracks(limit=limit, time_range=time_range)
    except Exception:
        return []
    faixas = []
    for item in resultado.get("items", []):
        artistas = item.get("artists", [])
        album = item.get("album", {})
        faixas.append({
            "nome": item.get("name", ""),
            "artista": artistas[0].get("name", "") if artistas else "",
            "album": album.get("name", ""),
            "capa_url": album["images"][0]["url"] if album.get("images") else "",
            "spotify_url": item.get("external_urls", {}).get("spotify", ""),
        })
    return faixas
