"""Salvar capa de álbum em disco — centraliza o que hoje está duplicado
verbatim em modules/musica/pages/diario.py e modules/musica/pages/albuns.py
(_salvar_capa/_salvar_capa_de_bytes).

Mesma convenção de nome de arquivo (`{album_id}{extensão}`, sempre
sobrescreve — uma capa por álbum, não versionada) e mesmo formato de
caminho salvo no banco: relativo a DB_DIR, em POSIX (barra normal mesmo no
Windows) — os covers já existentes, gravados pelo Streamlit, continuam
funcionando sem migração.
"""

from pathlib import Path

import requests
from fastapi import UploadFile

from .db import DB_DIR, UPLOADS_DIR


def salvar_capa_upload(album_id: int, arquivo: UploadFile, conteudo: bytes) -> str:
    """`conteudo` já lido de `arquivo` (UploadFile.read() é async — quem
    chama já resolveu isso antes)."""
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    extensao = Path(arquivo.filename or "").suffix or ".jpg"
    caminho = UPLOADS_DIR / f"{album_id}{extensao}"
    caminho.write_bytes(conteudo)
    return caminho.relative_to(DB_DIR).as_posix()


def salvar_capa_de_bytes(album_id: int, conteudo: bytes) -> str:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    caminho = UPLOADS_DIR / f"{album_id}.jpg"
    caminho.write_bytes(conteudo)
    return caminho.relative_to(DB_DIR).as_posix()


def baixar_capa(url: str) -> bytes | None:
    """Port de spotify_client.baixar_capa — sem dependência de credencial
    Spotify (é só um GET na URL pública da imagem)."""
    if not url:
        return None
    try:
        resposta = requests.get(url, timeout=10)
        resposta.raise_for_status()
        return resposta.content
    except Exception:
        return None


def caminho_capa_absoluto(capa_path: str) -> Path | None:
    """Resolve um capa_path salvo no banco pro arquivo real em disco, ou
    None se vazio/inexistente — mesma tolerância do original (`st.image`
    só se `Path.exists()`, sem 404 explícito)."""
    if not capa_path:
        return None
    caminho = DB_DIR / capa_path
    return caminho if caminho.exists() else None
