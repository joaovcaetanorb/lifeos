"""Prepara bytes + mime type de capa de beat pra salvar como BLOB no banco
(ver webapp/beatforge/repo.py) — mesma razão de webapp/projetos/fotos.py:
nada é gravado em disco, disco local não sobrevive a redeploy."""

import mimetypes

from fastapi import UploadFile


def mime_de_arquivo(arquivo: UploadFile, conteudo: bytes) -> str:
    if arquivo.content_type and arquivo.content_type.startswith("image/"):
        return arquivo.content_type
    tipo, _ = mimetypes.guess_type(arquivo.filename or "")
    return tipo or "image/jpeg"
