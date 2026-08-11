"""Integração com a Web API do Spotify — port de modules/musica/spotify_client.py.

Duas formas de auth, mesmo raciocínio do original:
1. Client Credentials — credenciais do app só, sem login de ninguém. Só dá
   acesso a catálogo público (busca de álbum/artista, gênero, faixas).
2. Authorization Code — login de verdade do usuário (OAuth), para
   histórico real de faixas tocadas e top artistas/faixas da conta.

Diferenças em relação ao original: sem st.cache_resource (singleton de
módulo simples) e sem st.session_state pra "último erro" — quem chama uma
função daqui e precisa de uma mensagem amigável recebe uma exceção
(SpotifyIndisponivel) com o texto já pronto pro router transformar em
resposta HTTP, em vez de guardar estado entre requests."""

import spotipy
from spotipy.cache_handler import CacheHandler
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth

from core.config import settings
from . import repo as models


class SpotifyIndisponivel(Exception):
    """Erro amigável pronto pra virar resposta HTTP (ver router)."""


# ---------------------------------------------------------------------------
# Client Credentials (catálogo público)
# ---------------------------------------------------------------------------

_client_singleton: spotipy.Spotify | None = None
_client_tentado = False


def _get_client() -> spotipy.Spotify | None:
    global _client_singleton, _client_tentado
    if _client_tentado:
        return _client_singleton
    _client_tentado = True
    if settings.spotify_client_id and settings.spotify_client_secret:
        auth = SpotifyClientCredentials(
            client_id=settings.spotify_client_id, client_secret=settings.spotify_client_secret,
        )
        _client_singleton = spotipy.Spotify(client_credentials_manager=auth)
    return _client_singleton


def disponivel() -> bool:
    return _get_client() is not None


def buscar_albuns(query: str, limit: int = 5) -> list[dict]:
    """[{nome, artista, artista_spotify_id, ano, capa_url, spotify_id,
    spotify_url}, ...]. Lista vazia se sem credencial ou sem resultado.
    Levanta SpotifyIndisponivel com mensagem amigável em erro de verdade
    (403 de falta de Premium na conta do app, ou erro de rede)."""
    sp = _get_client()
    if sp is None or not query.strip():
        return []
    try:
        resultado = sp.search(q=query, type="album", limit=limit)
    except spotipy.SpotifyException as e:
        if e.http_status == 403:
            raise SpotifyIndisponivel(
                "Spotify recusou a busca (403): a Web API exige que a conta dona do app tenha "
                "assinatura Premium ativa para usar o modo de busca (Client Credentials)."
            )
        raise SpotifyIndisponivel(f"Spotify recusou a busca (HTTP {e.http_status}).")
    except Exception:
        raise SpotifyIndisponivel("Não foi possível buscar no Spotify agora (erro de rede).")

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
    sp = _get_client()
    if sp is None or not artista_spotify_id:
        return ""
    try:
        artista = sp.artist(artista_spotify_id)
    except Exception:
        return ""
    generos = artista.get("genres", [])
    return generos[0].strip().title() if generos else ""


def buscar_capa_album(album_spotify_id: str) -> str:
    """URL da capa (maior resolução disponível) de um álbum já conhecido
    pelo spotify_id — usado pra recuperar a capa de um álbum cadastrado
    que perdeu o arquivo local (capa_path aponta pra um arquivo que só
    existia no disco de outro processo/servidor)."""
    sp = _get_client()
    if sp is None or not album_spotify_id:
        return ""
    try:
        album = sp.album(album_spotify_id)
    except Exception:
        return ""
    imagens = album.get("images", [])
    return imagens[0]["url"] if imagens else ""


def buscar_faixas(album_spotify_id: str) -> list[str]:
    sp = _get_client()
    if sp is None or not album_spotify_id:
        return []
    try:
        resultado = sp.album_tracks(album_spotify_id)
    except Exception:
        return []
    return [faixa["name"] for faixa in resultado.get("items", [])]


# ---------------------------------------------------------------------------
# Conta conectada (Authorization Code)
# ---------------------------------------------------------------------------

class _TursoCacheHandler(CacheHandler):
    def get_cached_token(self):
        return models.obter_token_spotify()

    def save_token_to_cache(self, token_info):
        models.salvar_token_spotify(token_info)


def _get_oauth() -> SpotifyOAuth | None:
    if not (settings.spotify_client_id and settings.spotify_client_secret and settings.spotify_redirect_uri):
        return None
    return SpotifyOAuth(
        client_id=settings.spotify_client_id,
        client_secret=settings.spotify_client_secret,
        redirect_uri=settings.spotify_redirect_uri,
        scope="user-read-recently-played user-top-read",
        cache_handler=_TursoCacheHandler(),
        open_browser=False,
    )


def conta_conectada() -> bool:
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
    sp = _cliente_conta()
    if sp is None:
        return []
    try:
        resultado = sp.current_user_top_artists(limit=limit, time_range=time_range)
    except Exception:
        return []
    return [{
        "nome": item.get("name", ""),
        "capa_url": item["images"][0]["url"] if item.get("images") else "",
        "spotify_url": item.get("external_urls", {}).get("spotify", ""),
    } for item in resultado.get("items", [])]


def top_faixas_conta(time_range: str = "medium_term", limit: int = 10) -> list[dict]:
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
