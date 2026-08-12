"""Endpoints REST do módulo música (/api/musica/...).

Cobre álbuns/escutas/estatísticas/insights. Busca de catálogo, conta OAuth
e exportações (colagem/relatório) ficam em spotify_router.py e
export_router.py — este arquivo só importa spotify_service pro breakdown
de gêneros reais (única estatística que precisa de uma chamada nova à API
do Spotify por artista, em vez de só ler o histórico já sincronizado).
"""

import math
from datetime import date
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from . import calculations as calc
from . import covers
from . import groq_service
from . import repo as models
from . import spotify_service as spotify

router = APIRouter(prefix="/api/musica", tags=["musica"])


# ---------------------------------------------------------------------------
# helpers de serialização
# ---------------------------------------------------------------------------

def _limpar_nan(v):
    """float('nan') não é JSON válido (json.dumps explode) — precisa virar
    None explicitamente. `DataFrame.where(pd.notnull(df), None)` não é
    confiável pra isso em toda coluna/versão do pandas (visto quebrar o
    endpoint inteiro quando alguma escuta tinha nota NULL), então sanitiza
    valor a valor depois do to_dict()."""
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _df_records(df: pd.DataFrame) -> list[dict]:
    """DataFrame -> list[dict] JSON-seguro: NaN vira None."""
    if df.empty:
        return []
    return [{k: _limpar_nan(v) for k, v in r.items()} for r in df.to_dict("records")]


def _ano_valido(valor) -> int | None:
    """Mesma guarda de modules/musica/pages/albuns.py: NaN do pandas (SQL
    NULL) não pode virar int() nem passar cru pro JSON."""
    if valor is None:
        return None
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass
    return int(valor)


def _capa_url(album_id: int, capa_mime: str | None) -> str | None:
    return f"/api/musica/albuns/{album_id}/capa" if capa_mime else None


def _album_out(album: dict, stats: Optional[dict] = None) -> dict:
    album = dict(album)
    album["ano_lancamento"] = _ano_valido(album.get("ano_lancamento"))
    album["capa_url"] = _capa_url(album["id"], album.get("capa_mime"))
    album["favorito"] = bool(album.get("favorito"))
    stats = stats or {}
    album["nota_media"] = stats.get("nota_media")
    album["total_escutas"] = stats.get("total_escutas", 0)
    return album


def _estatisticas_por_album() -> dict[int, dict]:
    """{album_id: {nota_media, total_escutas}} — uma passada só sobre todas
    as escutas (evita N+1 query por álbum na listagem)."""
    escutas = models.listar_escutas_com_album()
    if escutas.empty:
        return {}
    resultado = {}
    for album_id, grupo in escutas.groupby("album_id"):
        notas = grupo["nota"].dropna()
        resultado[int(album_id)] = {
            "nota_media": round(float(notas.mean()), 2) if not notas.empty else None,
            "total_escutas": int(len(grupo)),
        }
    return resultado


def _periodo_diario(inicio: Optional[str], fim: Optional[str]) -> tuple[str, str]:
    if inicio and fim:
        return inicio, fim
    intervalo = models.intervalo_datas_escutas()
    hoje = date.today().isoformat()
    return intervalo if intervalo is not None else (hoje, hoje)


def _periodo_historico(inicio: Optional[str], fim: Optional[str]) -> tuple[str, str]:
    if inicio and fim:
        return inicio, fim
    intervalo = models.intervalo_datas_historico()
    hoje = date.today().isoformat()
    return intervalo if intervalo is not None else (hoje, hoje)


# ---------------------------------------------------------------------------
# álbuns
# ---------------------------------------------------------------------------

@router.get("/albuns")
def listar_albuns(q: str = "", favoritos: bool = False):
    df = models.listar_albuns()
    if df.empty:
        return []
    if q.strip():
        termo = q.strip().lower()
        mask = (
            df["nome"].str.lower().str.contains(termo, regex=False)
            | df["artista_nome"].str.lower().str.contains(termo, regex=False)
        )
        df = df[mask]
    if favoritos:
        df = df[df["favorito"] == 1]
    stats = _estatisticas_por_album()
    return [_album_out(a, stats.get(a["id"])) for a in _df_records(df)]


@router.get("/albuns/{album_id}")
def obter_album(album_id: int):
    album = models.obter_album(album_id)
    if album is None:
        raise HTTPException(404, "Álbum não encontrado.")
    return _album_out(album, _estatisticas_por_album().get(album_id))


@router.get("/albuns/{album_id}/escutas")
def listar_escutas_album(album_id: int):
    if models.obter_album(album_id) is None:
        raise HTTPException(404, "Álbum não encontrado.")
    return _df_records(models.listar_escutas(album_id))


@router.post("/albuns", status_code=201)
async def criar_album(
    artista_nome: str = Form(...),
    album_nome: str = Form(...),
    ano_lancamento: Optional[str] = Form(None),
    genero: str = Form(""),
    spotify_id: str = Form(""),
    spotify_url: str = Form(""),
    artista_spotify_id: str = Form(""),
    capa_url_spotify: str = Form(""),
    capa: Optional[UploadFile] = None,
):
    """Cria (ou reaproveita, se já existir) artista + álbum. Prioridade de
    capa: upload manual > capa do Spotify (capa_url_spotify) > nenhuma —
    mesma regra do formulário original de nova escuta."""
    if not artista_nome.strip() or not album_nome.strip():
        raise HTTPException(400, "Artista e álbum são obrigatórios.")

    ano = int(ano_lancamento) if ano_lancamento else None
    artista_id = models.obter_ou_criar_artista(artista_nome.strip(), artista_spotify_id)
    album_id = models.obter_ou_criar_album(
        album_nome.strip(), artista_id, ano, genero, spotify_id=spotify_id, spotify_url=spotify_url,
    )

    capa_dados, capa_mime = None, None
    if capa is not None and capa.filename:
        capa_dados = await capa.read()
        capa_mime = covers.mime_de_arquivo(capa, capa_dados)
    elif capa_url_spotify:
        capa_dados = covers.baixar_capa(capa_url_spotify)
        if capa_dados is not None:
            capa_mime = "image/jpeg"

    if capa_dados is not None:
        atual = models.obter_album(album_id)
        models.atualizar_album(
            album_id, atual["nome"], _ano_valido(atual["ano_lancamento"]), atual["genero"],
            capa_dados=capa_dados, capa_mime=capa_mime,
        )

    return _album_out(models.obter_album(album_id))


@router.patch("/albuns/{album_id}")
async def atualizar_album(
    album_id: int,
    nome: str = Form(...),
    ano_lancamento: Optional[str] = Form(None),
    genero: str = Form(""),
    capa: Optional[UploadFile] = None,
):
    if models.obter_album(album_id) is None:
        raise HTTPException(404, "Álbum não encontrado.")
    if not nome.strip():
        raise HTTPException(400, "Nome do álbum é obrigatório.")

    ano = int(ano_lancamento) if ano_lancamento else None
    capa_dados, capa_mime = None, None
    if capa is not None and capa.filename:
        capa_dados = await capa.read()
        capa_mime = covers.mime_de_arquivo(capa, capa_dados)

    models.atualizar_album(album_id, nome.strip(), ano, genero, capa_dados=capa_dados, capa_mime=capa_mime)
    return _album_out(models.obter_album(album_id))


class FavoritoIn(BaseModel):
    favorito: bool


@router.patch("/albuns/{album_id}/favorito")
def favoritar_album(album_id: int, body: FavoritoIn):
    if models.obter_album(album_id) is None:
        raise HTTPException(404, "Álbum não encontrado.")
    models.favoritar_album(album_id, body.favorito)
    return {"ok": True}


class CapaSpotifyIn(BaseModel):
    capa_url: str


@router.post("/albuns/{album_id}/capa-from-spotify")
def capa_from_spotify(album_id: int, body: CapaSpotifyIn):
    album = models.obter_album(album_id)
    if album is None:
        raise HTTPException(404, "Álbum não encontrado.")
    conteudo = covers.baixar_capa(body.capa_url)
    if conteudo is None:
        raise HTTPException(502, "Não foi possível baixar essa capa agora.")
    models.atualizar_album(
        album_id, album["nome"], _ano_valido(album["ano_lancamento"]), album["genero"],
        capa_dados=conteudo, capa_mime="image/jpeg",
    )
    return _album_out(models.obter_album(album_id))


@router.delete("/albuns/{album_id}", status_code=204)
def excluir_album(album_id: int):
    if models.obter_album(album_id) is None:
        raise HTTPException(404, "Álbum não encontrado.")
    models.excluir_album(album_id)


@router.get("/albuns/{album_id}/capa")
def obter_capa_album(album_id: int):
    capa = models.obter_capa_album(album_id)
    if capa is None:
        raise HTTPException(404, "Esse álbum não tem capa.")
    dados, mime = capa
    return Response(content=dados, media_type=mime, headers={"Cache-Control": "public, max-age=86400"})


# ---------------------------------------------------------------------------
# escutas
# ---------------------------------------------------------------------------

class EscutaIn(BaseModel):
    album_id: int
    data: str
    nota: Optional[float] = None
    review: str = ""
    faixa_favorita: str = ""


@router.post("/escutas", status_code=201)
def criar_escuta(body: EscutaIn):
    if models.obter_album(body.album_id) is None:
        raise HTTPException(404, "Álbum não encontrado.")
    models.inserir_escuta(body.album_id, body.data, body.nota, body.review, body.faixa_favorita)
    return {"ok": True}


class EscutaUpdateIn(BaseModel):
    data: str
    nota: Optional[float] = None
    review: str = ""
    faixa_favorita: str = ""


@router.put("/escutas/{escuta_id}")
def atualizar_escuta(escuta_id: int, body: EscutaUpdateIn):
    models.atualizar_escuta(escuta_id, body.data, body.nota, body.review, body.faixa_favorita)
    return {"ok": True}


@router.delete("/escutas/{escuta_id}", status_code=204)
def excluir_escuta(escuta_id: int):
    models.excluir_escuta(escuta_id)


@router.get("/diario")
def diario():
    """Timeline completa (todas as escutas + álbum/artista resolvidos) —
    mesma fonte que modules/musica/pages/diario.py usa."""
    registros = _df_records(models.listar_escutas_com_album())
    for r in registros:
        r["capa_url"] = _capa_url(r["album_id"], r.get("capa_mime"))
        r["album_ano"] = _ano_valido(r.get("album_ano"))
    return registros


# ---------------------------------------------------------------------------
# resumo / estatísticas / insights
# ---------------------------------------------------------------------------

@router.get("/resumo")
def resumo():
    return calc.resumo_geral()


@router.get("/estatisticas/diario")
def estatisticas_diario(inicio: Optional[str] = None, fim: Optional[str] = None):
    data_inicio, data_fim = _periodo_diario(inicio, fim)
    return {
        "periodo": {"inicio": data_inicio, "fim": data_fim},
        "resumo": calc.resumo_periodo(data_inicio, data_fim),
        "escutas_por_mes": _df_records(calc.escutas_por_mes(data_inicio, data_fim)),
        "distribuicao_notas": _df_records(calc.distribuicao_notas(data_inicio, data_fim)),
        "top_artistas": _df_records(calc.top_artistas(data_inicio, data_fim, 8)),
        "escutas_por_decada": _df_records(calc.escutas_por_decada(data_inicio, data_fim)),
        "nota_media_por_decada": _df_records(calc.nota_media_por_decada(data_inicio, data_fim)),
        "escutas_por_genero": _df_records(calc.escutas_por_genero(data_inicio, data_fim)),
        "nota_media_por_genero": _df_records(calc.nota_media_por_genero(data_inicio, data_fim)),
    }


@router.get("/estatisticas/spotify")
def estatisticas_spotify(inicio: Optional[str] = None, fim: Optional[str] = None):
    data_inicio, data_fim = _periodo_historico(inicio, fim)
    return {
        "periodo": {"inicio": data_inicio, "fim": data_fim},
        "conectado": models.obter_token_spotify() is not None,
        "resumo": calc.resumo_periodo_real(data_inicio, data_fim),
        "top_artistas": _df_records(calc.top_artistas_historico(data_inicio, data_fim, 8)),
        "top_faixas": _df_records(calc.top_faixas_historico(data_inicio, data_fim, 8)),
        "habito_por_hora": _df_records(calc.habito_por_hora(data_inicio, data_fim)),
        "habito_por_dia_semana": _df_records(calc.habito_por_dia_semana(data_inicio, data_fim)),
    }


@router.get("/estatisticas/generos-spotify")
def estatisticas_generos_spotify(inicio: Optional[str] = None, fim: Optional[str] = None):
    """Separado de /estatisticas/spotify de propósito: precisa de uma
    chamada à Web API do Spotify por artista (buscar_genero_artista), então
    é bem mais lento — o frontend chama isso à parte, sem travar o resto da
    página. Mesma lógica de modules/musica/pages/estatisticas.py
    (_grafico_genero_real)."""
    if not spotify.disponivel():
        return {"generos": [], "disponivel": False}

    data_inicio, data_fim = _periodo_historico(inicio, fim)
    top = calc.top_artistas_historico_com_id(data_inicio, data_fim, 15)
    if top.empty:
        return {"generos": [], "disponivel": True}

    contagem: dict[str, int] = {}
    for _, artista in top.iterrows():
        if not artista["artista_spotify_id"]:
            continue
        genero = spotify.buscar_genero_artista(artista["artista_spotify_id"])
        if genero:
            contagem[genero] = contagem.get(genero, 0) + int(artista["total"])

    generos = sorted(({"genero": g, "total": t} for g, t in contagem.items()), key=lambda d: -d["total"])
    return {"generos": generos, "disponivel": True}


class InsightsIn(BaseModel):
    fonte: str  # "diario" | "spotify"
    inicio: str
    fim: str


@router.post("/insights")
def insights(body: InsightsIn):
    if not groq_service.disponivel():
        raise HTTPException(503, "GROQ_API_KEY não configurada em webapp/.env.")
    if body.fonte not in ("diario", "spotify"):
        raise HTTPException(400, "fonte precisa ser 'diario' ou 'spotify'.")
    contexto = (
        calc.contexto_ia_diario(body.inicio, body.fim) if body.fonte == "diario"
        else calc.contexto_ia_real(body.inicio, body.fim)
    )
    texto = groq_service.gerar_insights(contexto)
    if texto is None:
        raise HTTPException(502, "Não consegui gerar insights agora. Tenta de novo em instantes.")
    return {"texto": texto}
