"""Prepara bytes + mime type de capa de livro pra salvar como BLOB no banco
(ver webapp/livros/repo.py) — mesma razão de webapp/musica/covers.py: nada
é gravado em disco, disco local não sobrevive a redeploy."""

import mimetypes

import requests
from fastapi import UploadFile


def mime_de_arquivo(arquivo: UploadFile, conteudo: bytes) -> str:
    if arquivo.content_type and arquivo.content_type.startswith("image/"):
        return arquivo.content_type
    tipo, _ = mimetypes.guess_type(arquivo.filename or "")
    return tipo or "image/jpeg"


def baixar_capa(url: str) -> bytes | None:
    if not url:
        return None
    try:
        resposta = requests.get(url, timeout=10)
        resposta.raise_for_status()
        return resposta.content
    except Exception:
        return None
