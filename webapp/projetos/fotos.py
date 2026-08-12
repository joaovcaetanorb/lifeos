"""Prepara bytes + mime type de foto de projeto/item de checklist pra salvar
como BLOB no banco (ver webapp/projetos/repo.py) — mesma razão de
webapp/musica/covers.py: nada é gravado em disco, disco local não sobrevive
a redeploy. Sem busca externa (Google Books/Spotify): aqui é só upload
manual mesmo, como no Streamlit original."""

import mimetypes

from fastapi import UploadFile


def mime_de_arquivo(arquivo: UploadFile, conteudo: bytes) -> str:
    if arquivo.content_type and arquivo.content_type.startswith("image/"):
        return arquivo.content_type
    tipo, _ = mimetypes.guess_type(arquivo.filename or "")
    return tipo or "image/jpeg"
