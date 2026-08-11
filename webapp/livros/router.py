"""Endpoints REST do módulo livros (/api/livros/...). Mesmo padrão de
webapp/musica/router.py, sem a parte de Spotify/exportações (livros não
tem integração externa)."""

import math
from datetime import date
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Form, HTTPException, UploadFile
from pydantic import BaseModel

from . import calculations as calc
from . import covers
from . import google_books
from . import repo as models

router = APIRouter(prefix="/api/livros", tags=["livros"])


# ---------------------------------------------------------------------------
# helpers de serialização
# ---------------------------------------------------------------------------

def _limpar_nan(v):
    """float('nan') não é JSON válido (json.dumps explode) — precisa virar
    None explicitamente. `DataFrame.where(pd.notnull(df), None)` não é
    confiável pra isso em toda coluna/versão do pandas (foi visto quebrar
    o endpoint inteiro quando alguma leitura tinha nota NULL), então
    sanitiza valor a valor depois do to_dict()."""
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _df_records(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    return [{k: _limpar_nan(v) for k, v in r.items()} for r in df.to_dict("records")]


def _ano_valido(valor) -> int | None:
    if valor is None:
        return None
    try:
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass
    return int(valor)


def _capa_url(capa_path: str | None) -> str | None:
    caminho = covers.caminho_capa_absoluto(capa_path or "")
    if caminho is None:
        return None
    return f"/static/livros-covers/{caminho.name}"


def _livro_out(livro: dict, status: Optional[str] = None, stats: Optional[dict] = None) -> dict:
    livro = dict(livro)
    livro["ano_publicacao"] = _ano_valido(livro.get("ano_publicacao"))
    livro["capa_url"] = _capa_url(livro.get("capa_path"))
    livro["favorito"] = bool(livro.get("favorito"))
    livro["status_atual"] = status or "Não iniciado"
    stats = stats or {}
    livro["nota_media"] = stats.get("nota_media")
    livro["total_leituras"] = stats.get("total_leituras", 0)
    return livro


def _estatisticas_por_livro() -> dict[int, dict]:
    leituras = models.listar_leituras_com_livro()
    if leituras.empty:
        return {}
    resultado = {}
    for livro_id, grupo in leituras.groupby("livro_id"):
        notas = grupo["nota"].dropna()
        resultado[int(livro_id)] = {
            "nota_media": round(float(notas.mean()), 2) if not notas.empty else None,
            "total_leituras": int(len(grupo)),
        }
    return resultado


def _periodo_query(inicio: Optional[str], fim: Optional[str]) -> tuple[str, str]:
    if inicio and fim:
        return inicio, fim
    intervalo = models.intervalo_datas_leituras()
    hoje = date.today().isoformat()
    return intervalo if intervalo is not None else (hoje, hoje)


# ---------------------------------------------------------------------------
# livros
# ---------------------------------------------------------------------------

@router.get("/livros")
def listar_livros(q: str = "", favoritos: bool = False, status: str = ""):
    df = models.listar_livros()
    if df.empty:
        return []
    if q.strip():
        termo = q.strip().lower()
        mask = (
            df["nome"].str.lower().str.contains(termo, regex=False)
            | df["autor_nome"].str.lower().str.contains(termo, regex=False)
        )
        df = df[mask]
    if favoritos:
        df = df[df["favorito"] == 1]

    status_todos = calc.status_por_livro()
    stats = _estatisticas_por_livro()
    registros = _df_records(df)
    saida = [_livro_out(l, status_todos.get(l["id"], "Não iniciado"), stats.get(l["id"])) for l in registros]
    if status and status != "Todos":
        saida = [l for l in saida if l["status_atual"] == status]
    return saida


@router.get("/livros/{livro_id}")
def obter_livro(livro_id: int):
    livro = models.obter_livro(livro_id)
    if livro is None:
        raise HTTPException(404, "Livro não encontrado.")
    status_todos = calc.status_por_livro()
    stats = _estatisticas_por_livro()
    return _livro_out(livro, status_todos.get(livro_id), stats.get(livro_id))


@router.get("/livros/{livro_id}/leituras")
def listar_leituras_livro(livro_id: int):
    if models.obter_livro(livro_id) is None:
        raise HTTPException(404, "Livro não encontrado.")
    return _df_records(models.listar_leituras(livro_id))


@router.post("/livros", status_code=201)
async def criar_livro(
    autor_nome: str = Form(...),
    livro_nome: str = Form(...),
    ano_publicacao: Optional[str] = Form(None),
    genero: str = Form(""),
    capa: Optional[UploadFile] = None,
):
    if not autor_nome.strip() or not livro_nome.strip():
        raise HTTPException(400, "Autor e livro são obrigatórios.")

    ano = int(ano_publicacao) if ano_publicacao else None
    autor_id = models.obter_ou_criar_autor(autor_nome.strip())
    livro_id = models.obter_ou_criar_livro(livro_nome.strip(), autor_id, ano, genero)

    if capa is not None and capa.filename:
        conteudo = await capa.read()
        caminho = covers.salvar_capa_upload(livro_id, capa, conteudo)
        atual = models.obter_livro(livro_id)
        models.atualizar_livro(livro_id, atual["nome"], _ano_valido(atual["ano_publicacao"]), atual["genero"], capa_path=caminho)

    return _livro_out(models.obter_livro(livro_id))


@router.patch("/livros/{livro_id}")
async def atualizar_livro(
    livro_id: int,
    nome: str = Form(...),
    ano_publicacao: Optional[str] = Form(None),
    genero: str = Form(""),
    capa: Optional[UploadFile] = None,
):
    if models.obter_livro(livro_id) is None:
        raise HTTPException(404, "Livro não encontrado.")
    if not nome.strip():
        raise HTTPException(400, "Nome do livro é obrigatório.")

    ano = int(ano_publicacao) if ano_publicacao else None
    caminho = None
    if capa is not None and capa.filename:
        conteudo = await capa.read()
        caminho = covers.salvar_capa_upload(livro_id, capa, conteudo)

    models.atualizar_livro(livro_id, nome.strip(), ano, genero, capa_path=caminho)
    return _livro_out(models.obter_livro(livro_id))


@router.get("/buscar-capa")
def buscar_capa(q: str = ""):
    return google_books.buscar_capas(q)


class CapaGoogleIn(BaseModel):
    capa_url: str


@router.post("/livros/{livro_id}/capa-from-google")
def capa_from_google(livro_id: int, body: CapaGoogleIn):
    livro = models.obter_livro(livro_id)
    if livro is None:
        raise HTTPException(404, "Livro não encontrado.")
    conteudo = covers.baixar_capa(body.capa_url)
    if conteudo is None:
        raise HTTPException(502, "Não foi possível baixar essa capa agora.")
    caminho = covers.salvar_capa_de_bytes(livro_id, conteudo)
    models.atualizar_livro(
        livro_id, livro["nome"], _ano_valido(livro["ano_publicacao"]), livro["genero"], capa_path=caminho,
    )
    return _livro_out(models.obter_livro(livro_id))


class FavoritoIn(BaseModel):
    favorito: bool


@router.patch("/livros/{livro_id}/favorito")
def favoritar_livro(livro_id: int, body: FavoritoIn):
    if models.obter_livro(livro_id) is None:
        raise HTTPException(404, "Livro não encontrado.")
    models.favoritar_livro(livro_id, body.favorito)
    return {"ok": True}


@router.delete("/livros/{livro_id}", status_code=204)
def excluir_livro(livro_id: int):
    if models.obter_livro(livro_id) is None:
        raise HTTPException(404, "Livro não encontrado.")
    models.excluir_livro(livro_id)


# ---------------------------------------------------------------------------
# leituras
# ---------------------------------------------------------------------------

class LeituraIn(BaseModel):
    livro_id: int
    data: str
    status: str
    nota: Optional[float] = None
    review: str = ""


@router.post("/leituras", status_code=201)
def criar_leitura(body: LeituraIn):
    if models.obter_livro(body.livro_id) is None:
        raise HTTPException(404, "Livro não encontrado.")
    if body.status not in ("Lendo", "Concluído", "Abandonado"):
        raise HTTPException(400, "status inválido.")
    models.inserir_leitura(body.livro_id, body.data, body.status, body.nota, body.review)
    return {"ok": True}


class LeituraUpdateIn(BaseModel):
    data: str
    status: str
    nota: Optional[float] = None
    review: str = ""


@router.put("/leituras/{leitura_id}")
def atualizar_leitura(leitura_id: int, body: LeituraUpdateIn):
    if body.status not in ("Lendo", "Concluído", "Abandonado"):
        raise HTTPException(400, "status inválido.")
    models.atualizar_leitura(leitura_id, body.data, body.status, body.nota, body.review)
    return {"ok": True}


@router.delete("/leituras/{leitura_id}", status_code=204)
def excluir_leitura(leitura_id: int):
    models.excluir_leitura(leitura_id)


@router.get("/diario")
def diario():
    registros = _df_records(models.listar_leituras_com_livro())
    for r in registros:
        r["capa_url"] = _capa_url(r.get("capa_path"))
    return registros


# ---------------------------------------------------------------------------
# resumo / estatísticas
# ---------------------------------------------------------------------------

@router.get("/resumo")
def resumo():
    return calc.resumo_geral()


@router.get("/estatisticas")
def estatisticas(inicio: Optional[str] = None, fim: Optional[str] = None):
    data_inicio, data_fim = _periodo_query(inicio, fim)
    return {
        "periodo": {"inicio": data_inicio, "fim": data_fim},
        "resumo": calc.resumo_periodo(data_inicio, data_fim),
        "concluidos_por_mes": _df_records(calc.livros_concluidos_por_mes(data_inicio, data_fim)),
        "distribuicao_notas": _df_records(calc.distribuicao_notas(data_inicio, data_fim)),
        "top_autores": _df_records(calc.top_autores(data_inicio, data_fim, 8)),
    }
