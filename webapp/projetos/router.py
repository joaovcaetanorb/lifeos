"""Endpoints REST do módulo projetos (/api/projetos/...). Mesmo padrão de
webapp/livros/router.py."""

import math
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Form, HTTPException, UploadFile
from pydantic import BaseModel

from . import calculations as calc
from . import fotos
from . import repo as models

router = APIRouter(prefix="/api/projetos", tags=["projetos"])


# ---------------------------------------------------------------------------
# helpers de serialização
# ---------------------------------------------------------------------------

def _limpar_nan(v):
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _df_records(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    return [{k: _limpar_nan(v) for k, v in r.items()} for r in df.to_dict("records")]


def _foto_url(foto_path: str | None) -> str | None:
    caminho = fotos.caminho_foto_absoluto(foto_path or "")
    if caminho is None:
        return None
    return f"/static/projetos-uploads/{caminho.name}"


def _projeto_out(projeto: dict) -> dict:
    projeto = dict(projeto)
    pid = int(projeto["id"])
    projeto["foto_url"] = _foto_url(projeto.get("foto_path"))
    projeto["valor_acumulado"] = calc.valor_acumulado(pid)
    projeto["progresso_financeiro"] = calc.progresso_financeiro(pid, projeto["orcamento"])
    projeto["progresso_checklist"] = calc.progresso_checklist(pid)
    return projeto


def _item_checklist_out(item: dict) -> dict:
    item = dict(item)
    item["concluido"] = bool(item["concluido"])
    item["foto_url"] = _foto_url(item.get("foto_path"))
    item["vencido"] = calc.item_vencido(item.get("prazo") or "", item["concluido"])
    return item


# ---------------------------------------------------------------------------
# resumo
# ---------------------------------------------------------------------------

@router.get("/resumo")
def resumo():
    return calc.resumo_geral()


# ---------------------------------------------------------------------------
# projetos
# ---------------------------------------------------------------------------

@router.get("/projetos")
def listar_projetos(status: str = ""):
    df = models.listar_projetos(status=status or None)
    if df.empty:
        return []
    return [_projeto_out(p) for p in _df_records(df)]


@router.get("/projetos/{projeto_id}")
def obter_projeto(projeto_id: int):
    projeto = models.obter_projeto(projeto_id)
    if projeto is None:
        raise HTTPException(404, "Projeto não encontrado.")
    return _projeto_out(projeto)


@router.post("/projetos", status_code=201)
async def criar_projeto(
    nome: str = Form(...),
    descricao: str = Form(""),
    orcamento: float = Form(0.0),
    observacoes: str = Form(""),
    foto: Optional[UploadFile] = None,
):
    if not nome.strip():
        raise HTTPException(400, "Informe um nome para o projeto.")

    projeto_id = models.inserir_projeto(nome.strip(), descricao.strip(), orcamento, observacoes.strip())

    if foto is not None and foto.filename:
        conteudo = await foto.read()
        caminho = fotos.salvar_foto_projeto(projeto_id, foto, conteudo)
        atual = models.obter_projeto(projeto_id)
        models.atualizar_projeto(
            projeto_id, atual["nome"], atual["descricao"], atual["orcamento"],
            atual["observacoes"], atual["status"], foto_path=caminho,
        )

    return _projeto_out(models.obter_projeto(projeto_id))


@router.patch("/projetos/{projeto_id}")
async def atualizar_projeto(
    projeto_id: int,
    nome: str = Form(...),
    descricao: str = Form(""),
    orcamento: float = Form(0.0),
    observacoes: str = Form(""),
    status: str = Form("Ativo"),
    foto: Optional[UploadFile] = None,
):
    if models.obter_projeto(projeto_id) is None:
        raise HTTPException(404, "Projeto não encontrado.")
    if not nome.strip():
        raise HTTPException(400, "Informe um nome para o projeto.")
    if status not in ("Ativo", "Pausado", "Concluído"):
        raise HTTPException(400, "status inválido.")

    caminho = None
    if foto is not None and foto.filename:
        conteudo = await foto.read()
        caminho = fotos.salvar_foto_projeto(projeto_id, foto, conteudo)

    models.atualizar_projeto(
        projeto_id, nome.strip(), descricao.strip(), orcamento, observacoes.strip(), status, foto_path=caminho,
    )
    return _projeto_out(models.obter_projeto(projeto_id))


@router.delete("/projetos/{projeto_id}", status_code=204)
def excluir_projeto(projeto_id: int):
    if models.obter_projeto(projeto_id) is None:
        raise HTTPException(404, "Projeto não encontrado.")
    models.excluir_projeto(projeto_id)


# ---------------------------------------------------------------------------
# checklist
# ---------------------------------------------------------------------------

@router.get("/projetos/{projeto_id}/checklist")
def listar_checklist(projeto_id: int):
    if models.obter_projeto(projeto_id) is None:
        raise HTTPException(404, "Projeto não encontrado.")
    return [_item_checklist_out(i) for i in _df_records(models.listar_checklist(projeto_id))]


class ChecklistItemIn(BaseModel):
    descricao: str


@router.post("/projetos/{projeto_id}/checklist", status_code=201)
def criar_item_checklist(projeto_id: int, body: ChecklistItemIn):
    if models.obter_projeto(projeto_id) is None:
        raise HTTPException(404, "Projeto não encontrado.")
    if not body.descricao.strip():
        raise HTTPException(400, "Descrição do item é obrigatória.")
    item_id = models.inserir_item_checklist(projeto_id, body.descricao.strip())
    return _item_checklist_out(models.obter_item_checklist(item_id))


class ChecklistToggleIn(BaseModel):
    concluido: bool


@router.patch("/checklist/{item_id}")
def marcar_item_checklist(item_id: int, body: ChecklistToggleIn):
    if models.obter_item_checklist(item_id) is None:
        raise HTTPException(404, "Item não encontrado.")
    models.marcar_item_checklist(item_id, body.concluido)
    return _item_checklist_out(models.obter_item_checklist(item_id))


@router.patch("/checklist/{item_id}/detalhes")
async def atualizar_detalhes_item_checklist(
    item_id: int,
    notas: str = Form(""),
    prazo: str = Form(""),
    link: str = Form(""),
    foto: Optional[UploadFile] = None,
):
    if models.obter_item_checklist(item_id) is None:
        raise HTTPException(404, "Item não encontrado.")

    caminho = None
    if foto is not None and foto.filename:
        conteudo = await foto.read()
        caminho = fotos.salvar_foto_item(item_id, foto, conteudo)

    models.atualizar_detalhes_item_checklist(item_id, notas.strip(), prazo, link.strip(), foto_path=caminho)
    return _item_checklist_out(models.obter_item_checklist(item_id))


@router.delete("/checklist/{item_id}", status_code=204)
def excluir_item_checklist(item_id: int):
    if models.obter_item_checklist(item_id) is None:
        raise HTTPException(404, "Item não encontrado.")
    models.excluir_item_checklist(item_id)


# ---------------------------------------------------------------------------
# aportes
# ---------------------------------------------------------------------------

@router.get("/projetos/{projeto_id}/aportes")
def listar_aportes(projeto_id: int):
    if models.obter_projeto(projeto_id) is None:
        raise HTTPException(404, "Projeto não encontrado.")
    return _df_records(models.listar_aportes(projeto_id))


class AporteIn(BaseModel):
    data: str
    valor: float
    observacao: str = ""


@router.post("/projetos/{projeto_id}/aportes", status_code=201)
def criar_aporte(projeto_id: int, body: AporteIn):
    if models.obter_projeto(projeto_id) is None:
        raise HTTPException(404, "Projeto não encontrado.")
    if body.valor <= 0:
        raise HTTPException(400, "Informe um valor maior que zero.")
    models.inserir_aporte(projeto_id, body.data, body.valor, body.observacao.strip())
    return {"ok": True}


@router.delete("/aportes/{aporte_id}", status_code=204)
def excluir_aporte(aporte_id: int):
    models.excluir_aporte(aporte_id)
