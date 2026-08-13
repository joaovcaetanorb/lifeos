"""Endpoints de exportação (/api/musica/...): colagem/mosaico de capas e
relatório estilo Stories — ambos devolvem PNG bytes direto, sem estado de
sessão (a versão Streamlit guardava os bytes em st.session_state pra
sobreviver a reruns; aqui cada request já devolve o arquivo pronto)."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from . import album_story
from . import calculations as calc
from . import colagem
from . import relatorio_stories
from . import repo as models

router = APIRouter(prefix="/api/musica", tags=["musica-export"])


class ColagemIn(BaseModel):
    fonte: str  # "diario" | "spotify"
    inicio: str
    fim: str
    lado_grade: int = 3
    formato: str = "post"  # "post" | "stories"


@router.post("/colagem")
def gerar_colagem(body: ColagemIn):
    if body.lado_grade not in (3, 4, 5, 6):
        raise HTTPException(400, "lado_grade precisa ser 3, 4, 5 ou 6.")
    if body.formato not in ("post", "stories"):
        raise HTTPException(400, "formato precisa ser 'post' ou 'stories'.")

    limite = body.lado_grade * body.lado_grade
    if body.fonte == "diario":
        top = calc.top_albuns_periodo(body.inicio, body.fim, limite)
    elif body.fonte == "spotify":
        top = calc.top_albuns_historico(body.inicio, body.fim, limite)
    else:
        raise HTTPException(400, "fonte precisa ser 'diario' ou 'spotify'.")

    if top.empty:
        raise HTTPException(404, "Nenhum álbum encontrado nesse período pra montar a colagem.")

    png = colagem.gerar_colagem(top.to_dict("records"), body.lado_grade, body.formato)
    nome = f"colagem_{body.inicio}_a_{body.fim}_{body.lado_grade}x{body.lado_grade}_{body.formato}.png"
    return Response(content=png, media_type="image/png", headers={"Content-Disposition": f'inline; filename="{nome}"'})


class RelatorioStoriesIn(BaseModel):
    inicio: str
    fim: str
    rotulo: Optional[str] = None
    lado_grade: int = 3


@router.post("/relatorio-stories")
def gerar_relatorio_stories(body: RelatorioStoriesIn):
    if body.lado_grade not in (3, 4, 5, 6):
        raise HTTPException(400, "lado_grade precisa ser 3, 4, 5 ou 6.")
    dados = calc.resumo_periodo_real(body.inicio, body.fim)
    if dados["total_faixas"] == 0:
        raise HTTPException(404, "Nenhuma faixa sincronizada nesse período.")
    top_albuns = calc.top_albuns_historico(body.inicio, body.fim, body.lado_grade ** 2).to_dict("records")
    rotulo = body.rotulo or f"{body.inicio} a {body.fim}"
    png = relatorio_stories.gerar_relatorio_stories(dados, rotulo, top_albuns, body.lado_grade)
    nome = f"spotify-{body.inicio}-a-{body.fim}-{body.lado_grade}x{body.lado_grade}.png"
    return Response(content=png, media_type="image/png", headers={"Content-Disposition": f'inline; filename="{nome}"'})


class AlbumStoryIn(BaseModel):
    escuta_id: int
    incluir_review: bool = True


@router.post("/album-stories")
def gerar_album_story(body: AlbumStoryIn):
    escuta = models.obter_escuta_com_album(body.escuta_id)
    if escuta is None:
        raise HTTPException(404, "Escuta não encontrada.")
    png = album_story.gerar_album_story(escuta, body.incluir_review)
    nome = f"album-{body.escuta_id}.png"
    return Response(content=png, media_type="image/png", headers={"Content-Disposition": f'inline; filename="{nome}"'})
