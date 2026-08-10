"""Monta a colagem de capas: mosaico quadrado com os álbuns mais escutados
num período, pronto pra postar. Dois formatos de saída — post (quadrado
1080x1080) e stories (vertical 1080x1920, com o mosaico centralizado).
"""

import io

from PIL import Image

import database
import utils

LADO_POST = 1080
TAMANHO_STORIES = (1080, 1920)


def _abrir_imagem(item: dict) -> Image.Image | None:
    """Abre a capa de `item` — local (`capa_path`, álbuns do Diário) ou
    remota (`capa_url`, faixas do histórico Spotify, baixada na hora).
    None se não tem nenhuma das duas ou a capa não existe/falha."""
    if item.get("capa_path"):
        caminho = database.DB_DIR / item["capa_path"]
        if caminho.exists():
            return Image.open(caminho)
    elif item.get("capa_url"):
        import spotify_client  # import tardio: só existe no módulo música
        conteudo = spotify_client.baixar_capa(item["capa_url"])
        if conteudo is not None:
            return Image.open(io.BytesIO(conteudo))
    return None


def _tile_capa(item: dict, tamanho: int) -> Image.Image:
    """Capa recortada em quadrado (crop central) e redimensionada. Sem
    capa ou falha ao abrir: retorna um quadrado liso (sem texto — evita
    depender de fonte TrueType instalada, e é o caso raro já que a
    maioria dos álbuns vem com capa do Spotify)."""
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


def gerar_colagem(albuns: list[dict], lado_grade: int, formato: str = "post") -> bytes:
    """albuns: lista de dicts com album_nome/artista_nome + capa_path
    (Diário) ou capa_url (histórico Spotify), já ordenados por relevância
    (mais escutado/tocado primeiro). lado_grade: 3, 4 ou 5. formato:
    'post' (quadrado) ou 'stories' (vertical). PNG bytes."""
    tamanho_tile = LADO_POST // lado_grade
    lado_mosaico = tamanho_tile * lado_grade
    mosaico = Image.new("RGB", (lado_mosaico, lado_mosaico), utils.COR_FUNDO)

    total_slots = lado_grade * lado_grade
    for i in range(total_slots):
        item = albuns[i] if i < len(albuns) else {}
        tile = _tile_capa(item, tamanho_tile)
        col, linha = i % lado_grade, i // lado_grade
        mosaico.paste(tile, (col * tamanho_tile, linha * tamanho_tile))

    if formato == "stories":
        largura, altura = TAMANHO_STORIES
        canvas = Image.new("RGB", (largura, altura), utils.COR_FUNDO)
        x = (largura - lado_mosaico) // 2
        y = (altura - lado_mosaico) // 2
        canvas.paste(mosaico, (x, y))
    else:
        canvas = mosaico

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()
