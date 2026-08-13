"""Monta a colagem de capas: mosaico quadrado com os álbuns mais escutados
num período, pronto pra postar. Port de modules/musica/colagem.py —
verbatim (o original já não dependia de Streamlit), só troca o import
tardio de spotify_client por covers.baixar_capa."""

import colorsys
import io

from PIL import Image

from . import covers
from . import repo as models
from . import utils

LADO_POST = 1080
TAMANHO_STORIES = (1080, 1920)


def _abrir_imagem(item: dict) -> Image.Image | None:
    if item.get("album_id"):
        capa = models.obter_capa_album(int(item["album_id"]))
        if capa is not None:
            conteudo, _mime = capa
            return Image.open(io.BytesIO(conteudo))
    if item.get("capa_url"):
        conteudo = covers.baixar_capa(item["capa_url"])
        if conteudo is not None:
            return Image.open(io.BytesIO(conteudo))
    return None


def tile_capa(item: dict, tamanho: int) -> Image.Image:
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


def cor_dominante(imagem: Image.Image, cor_reserva: str = "#4ADE94") -> str:
    """Cor de destaque "puxada" da capa (tipo Wrapped) — reduz a paleta,
    pega as cores mais frequentes e escolhe a mais saturada/vibrante entre
    elas (evita cair numa cor de fundo cinza/preta/branca sem graça).
    Clampa saturação e brilho pra sempre ficar legível sobre o fundo escuro
    do card. cor_reserva é usada se a capa não render nenhuma cor viável
    (ex.: capa em preto e branco)."""
    pequena = imagem.convert("RGB").resize((80, 80))
    paleta = pequena.convert("P", palette=Image.ADAPTIVE, colors=8)
    contagens = sorted(paleta.getcolors(), reverse=True)
    cores_rgb = [paleta.getpalette()[i * 3:i * 3 + 3] for _count, i in contagens]

    melhor = None
    melhor_pontuacao = -1.0
    for r, g, b in cores_rgb:
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if s < 0.28 or v < 0.05:
            continue  # cinza/preto/quase-branco (matiz não confiável) — não rende como "cor da capa"
        # não descarta cor escura por ser escura (o brilho é renormalizado
        # depois de qualquer forma) — só usa v aqui pra priorizar entre as
        # candidatas que sobraram, não pra excluir tons escuros e saturados
        # (ex.: vermelho vinho de capa) que ainda rendem uma boa cor de destaque.
        pontuacao = s * min(v + 0.3, 1.0)
        if pontuacao > melhor_pontuacao:
            melhor_pontuacao, melhor = pontuacao, (h, s, v)

    if melhor is None:
        return cor_reserva

    h, s, v = melhor
    s = max(s, 0.55)  # garante saturação mínima pra não ficar "lavada"
    v = min(max(v, 0.62), 0.92)  # nem escura demais (some no fundo), nem estourada
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return "#{:02X}{:02X}{:02X}".format(int(r * 255), int(g * 255), int(b * 255))


def montar_mosaico(albuns: list[dict], lado_grade: int, lado_total: int) -> Image.Image:
    tamanho_tile = lado_total // lado_grade
    lado_mosaico = tamanho_tile * lado_grade
    mosaico = Image.new("RGB", (lado_mosaico, lado_mosaico), utils.COR_FUNDO)

    total_slots = lado_grade * lado_grade
    for i in range(total_slots):
        item = albuns[i] if i < len(albuns) else {}
        tile = tile_capa(item, tamanho_tile)
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
