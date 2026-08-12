"""Prepara bytes + mime type de capa de álbum pra salvar como BLOB no banco
(ver webapp/musica/repo.py) — nada é gravado em disco. Substitui a versão
anterior (que escrevia em UPLOADS_DIR): disco local não sobrevive a
redeploy/restart em host na nuvem, e o Turso já guarda todo o resto dos
dados do usuário, então a capa vai junto na mesma linha do álbum."""

import mimetypes

import requests
from fastapi import UploadFile


def mime_de_arquivo(arquivo: UploadFile, conteudo: bytes) -> str:
    if arquivo.content_type and arquivo.content_type.startswith("image/"):
        return arquivo.content_type
    tipo, _ = mimetypes.guess_type(arquivo.filename or "")
    return tipo or "image/jpeg"


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
