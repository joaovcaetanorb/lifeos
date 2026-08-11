"""Salvar foto de projeto/item de checklist em disco — mesma convenção de
webapp/livros/covers.py (capa_path relativo a DB_DIR, em POSIX). Sem busca
externa (Google Books/Spotify): aqui é só upload manual mesmo, como no
Streamlit original."""

from pathlib import Path

from fastapi import UploadFile

from .db import DB_DIR, UPLOADS_DIR


def salvar_foto_projeto(projeto_id: int, arquivo: UploadFile, conteudo: bytes) -> str:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    extensao = Path(arquivo.filename or "").suffix or ".jpg"
    caminho = UPLOADS_DIR / f"{projeto_id}{extensao}"
    caminho.write_bytes(conteudo)
    return caminho.relative_to(DB_DIR).as_posix()


def salvar_foto_item(item_id: int, arquivo: UploadFile, conteudo: bytes) -> str:
    """Prefixo 'item_' pra não colidir com o nome de arquivo da foto de capa
    do projeto (ids de tabelas diferentes, mesma pasta de uploads)."""
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    extensao = Path(arquivo.filename or "").suffix or ".jpg"
    caminho = UPLOADS_DIR / f"item_{item_id}{extensao}"
    caminho.write_bytes(conteudo)
    return caminho.relative_to(DB_DIR).as_posix()


def caminho_foto_absoluto(foto_path: str) -> Path | None:
    if not foto_path:
        return None
    caminho = DB_DIR / foto_path
    return caminho if caminho.exists() else None
