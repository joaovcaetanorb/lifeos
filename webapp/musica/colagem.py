"""Monta a colagem de capas: mosaico quadrado com os álbuns mais escutados
num período, pronto pra postar. Port de modules/musica/colagem.py —
verbatim (o original já não dependia de Streamlit), só troca o import
tardio de spotify_client por covers.baixar_capa."""

import io

from PIL import Image

from . import covers
from . import utils
from .db import DB_DIR

LADO_POST = 1080
TAMANHO_STORIES = (1080, 1920)


def _abrir_imagem(item: dict) -> Image.Image | None:
    if item.get("capa_path"):
        caminho = DB_DIR / item["capa_path"]
        if caminho.exists():
            return Image.open(caminho)
    elif item.get("capa_url"):
        conteudo = covers.baixar_capa(item["capa_url"])
        if conteudo is not None:
            return Image.open(io.BytesIO(conteudo))
    return None


def _tile_capa(item: dict, tamanho: int) -> Image.Image:
    imagem = _abrir_imagem(item)
    if imagem is not None:
        with imagem:
            img = imagem.convert("RGB")
            lado = min(img.size)
            esquerda = (img.width - lado) // 2
            topo = (img.height - lado) // 2
            img = img.crop((esquerda, topo, esquerda + lado, topo + lado))
            return img.resize((tamanho, tamanho), Image.Resampling.LANCZOS)

    return Image.new("RGB", (tamanho, tamanho), utils.COR_FUNDO_ALT)


def montar_mosaico(albuns: list[dict], lado_grade: int, lado_total: int) -> Image.Image:
    tamanho_tile = lado_total // lado_grade
    lado_mosaico = tamanho_tile * lado_grade
    mosaico = Image.new("RGB", (lado_mosaico, lado_mosaico), utils.COR_FUNDO)

    total_slots = lado_grade * lado_grade
    for i in range(total_slots):
        item = albuns[i] if i < len(albuns) else {}
        tile = _tile_capa(item, tamanho_tile)
        col, linha = i % lado_grade, i // lado_grade
        mosaico.paste(tile, (col * tamanho_tile, linha * tamanho_tile))
    return mosaico


def gerar_colagem(albuns: list[dict], lado_grade: int, formato: str = "post") -> bytes:
    mosaico = montar_mosaico(albuns, lado_grade, LADO_POST)

    if formato == "stories":
        largura, altura = TAMANHO_STORIES
        canvas = Image.new("RGB", (largura, altura), utils.COR_FUNDO)
        x = (largura - mosaico.width) // 2
        y = (altura - mosaico.height) // 2
        canvas.paste(mosaico, (x, y))
    else:
        canvas = mosaico

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()
