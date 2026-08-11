"""Endpoints Spotify (/api/musica/spotify/...) — busca de catálogo (capas,
gênero, faixas) e conta conectada (OAuth, histórico, top). Ver
webapp/musica/spotify_service.py pro port da lógica."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from . import spotify_service as spotify
from . import repo as models

router = APIRouter(prefix="/api/musica/spotify", tags=["musica-spotify"])


@router.get("/status")
def status():
    return {
        "catalogo_disponivel": spotify.disponivel(),
        "conectado": spotify.conta_conectada(),
    }


@router.get("/search-albums")
def search_albums(q: str = ""):
    try:
        return spotify.buscar_albuns(q, limit=6)
    except spotify.SpotifyIndisponivel as e:
        raise HTTPException(502, str(e))


@router.get("/genero")
def genero(artista_spotify_id: str = ""):
    return {"genero": spotify.buscar_genero_artista(artista_spotify_id)}


@router.get("/albuns/{spotify_id}/faixas")
def faixas(spotify_id: str):
    return spotify.buscar_faixas(spotify_id)


@router.get("/albuns/{spotify_id}/capa")
def capa_album(spotify_id: str):
    return {"capa_url": spotify.buscar_capa_album(spotify_id)}


@router.get("/login")
def login():
    url = spotify.url_autorizacao()
    if url is None:
        raise HTTPException(503, "Credenciais do Spotify (CLIENT_ID/SECRET/REDIRECT_URI) não configuradas em webapp/.env.")
    return RedirectResponse(url)


@router.get("/callback")
def callback(code: Optional[str] = None, error: Optional[str] = None):
    if error or not code:
        return RedirectResponse("/musica/spotify.html?erro=1")
    ok = spotify.completar_conexao(code)
    return RedirectResponse("/musica/spotify.html?conectado=1" if ok else "/musica/spotify.html?erro=1")


@router.post("/sync")
def sync():
    if not spotify.conta_conectada():
        raise HTTPException(400, "Conta Spotify não conectada.")
    novas = spotify.sincronizar_historico()
    return {"novas": novas}


@router.post("/disconnect")
def disconnect():
    spotify.desconectar()
    return {"ok": True}


@router.get("/historico")
def historico(limit: int = 50):
    df = models.listar_historico(limit)
    import pandas as pd
    return [] if df.empty else df.where(pd.notnull(df), None).to_dict("records")


@router.get("/top")
def top(periodo: str = "medium_term", tipo: str = "artistas"):
    if periodo not in ("short_term", "medium_term", "long_term"):
        raise HTTPException(400, "periodo precisa ser short_term, medium_term ou long_term.")
    if tipo == "faixas":
        return spotify.top_faixas_conta(periodo)
    return spotify.top_artistas_conta(periodo)
