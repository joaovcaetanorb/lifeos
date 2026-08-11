"""Salvar capa de livro em disco — mesma convenção de webapp/musica/covers.py
(nome de arquivo {livro_id}{extensão}, sobrescreve; capa_path relativo a
DB_DIR em POSIX)."""

from pathlib import Path

from fastapi import UploadFile

from .db import DB_DIR, UPLOADS_DIR


def salvar_capa_upload(livro_id: int, arquivo: UploadFile, conteudo: bytes) -> str:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    extensao = Path(arquivo.filename or "").suffix or ".jpg"
    caminho = UPLOADS_DIR / f"{livro_id}{extensao}"
    caminho.write_bytes(conteudo)
    return caminho.relative_to(DB_DIR).as_posix()


def caminho_capa_absoluto(capa_path: str) -> Path | None:
    if not capa_path:
        return None
    caminho = DB_DIR / capa_path
    return caminho if caminho.exists() else None
