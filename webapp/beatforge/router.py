"""Endpoints REST do módulo Beat Forge (/api/beatforge/...). Mesmo padrão de
webapp/projetos/router.py."""

import math
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from humor import repo as humor_repo
from musica import repo as musica_repo

from . import calculations as calc
from . import fotos
from . import repo as models
from . import spotify_oembed

router = APIRouter(prefix="/api/beatforge", tags=["beatforge"])


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


def _beat_out(beat: dict) -> dict:
    beat = dict(beat)
    bid = int(beat["id"])
    beat["capa_url"] = f"/api/beatforge/beats/{bid}/capa" if beat.get("capa_mime") else None
    sessoes = models.listar_sessoes(bid)
    beat["tempo_investido_min"] = calc.tempo_total_investido(bid, sessoes)
    beat["ultimo_passo_brutal"] = calc.ultimo_passo_brutal(bid, sessoes)
    beat["total_sessoes"] = int(len(sessoes))
    return beat


# ---------------------------------------------------------------------------
# resumo
# ---------------------------------------------------------------------------

@router.get("/resumo")
def resumo():
    return calc.resumo_geral()


@router.get("/tecnicas")
def listar_tecnicas_disponiveis():
    return calc.TECNICAS_DISPONIVEIS


# ---------------------------------------------------------------------------
# contexto (humor + audição atuais — só leitura, cross-módulo)
# ---------------------------------------------------------------------------

@router.get("/contexto-atual")
def contexto_atual():
    estado_emocional = ""
    registros_humor = humor_repo.listar_registros()
    if not registros_humor.empty:
        atual = registros_humor.iloc[0]
        tags = str(atual.get("tags") or "").strip()
        estado_emocional = f"{int(atual['nota'])}/10" + (f" · {tags}" if tags else "")

    referencia_audicao = ""
    escutas = musica_repo.listar_escutas_com_album()
    if not escutas.empty:
        atual = escutas.iloc[0]
        referencia_audicao = f"{atual['artista_nome']} – {atual['album_nome']}"

    return {"estado_emocional": estado_emocional, "referencia_audicao": referencia_audicao}


# ---------------------------------------------------------------------------
# beats
# ---------------------------------------------------------------------------

@router.get("/beats")
def listar_beats(status: str = ""):
    df = models.listar_beats(status=status or None)
    if df.empty:
        return []
    return [_beat_out(b) for b in _df_records(df)]


@router.get("/beats/{beat_id}")
def obter_beat(beat_id: int):
    beat = models.obter_beat(beat_id)
    if beat is None:
        raise HTTPException(404, "Beat não encontrado.")
    return _beat_out(beat)


def _validar_campos_beat(origem_tipo: str, origem_metodo: str, status: str) -> None:
    if origem_tipo not in ("sample", "sintese"):
        raise HTTPException(400, "origem_tipo inválido.")
    if not origem_metodo.strip():
        raise HTTPException(400, "Descreva como extraiu o sample ou qual synth usou (campo Origem).")
    if status not in calc.STATUS_PIPELINE:
        raise HTTPException(400, "status inválido.")


@router.post("/beats", status_code=201)
async def criar_beat(
    nome: str = Form(...),
    data: str = Form(...),
    bpm: Optional[int] = Form(None),
    tonalidade: str = Form(""),
    duracao_alvo: str = Form(""),
    origem_tipo: str = Form(...),
    origem_referencia: str = Form(""),
    origem_metodo: str = Form(...),
    status: str = Form("Loop Eterno"),
    tecnicas: str = Form(""),
    link_externo: str = Form(""),
    observacoes: str = Form(""),
    capa: Optional[UploadFile] = None,
):
    if not nome.strip():
        raise HTTPException(400, "Informe um nome para o beat.")
    _validar_campos_beat(origem_tipo, origem_metodo, status)

    capa_dados, capa_mime = None, None
    if capa is not None and capa.filename:
        capa_dados = await capa.read()
        capa_mime = fotos.mime_de_arquivo(capa, capa_dados)

    beat_id = models.inserir_beat(
        nome.strip(), data, bpm, tonalidade.strip(), duracao_alvo.strip(),
        origem_tipo, origem_referencia.strip(), origem_metodo.strip(),
        status, tecnicas.strip(), link_externo.strip(), observacoes.strip(),
        capa_dados=capa_dados, capa_mime=capa_mime,
    )
    return _beat_out(models.obter_beat(beat_id))


@router.patch("/beats/{beat_id}")
async def atualizar_beat(
    beat_id: int,
    nome: str = Form(...),
    data: str = Form(...),
    bpm: Optional[int] = Form(None),
    tonalidade: str = Form(""),
    duracao_alvo: str = Form(""),
    origem_tipo: str = Form(...),
    origem_referencia: str = Form(""),
    origem_metodo: str = Form(...),
    status: str = Form(...),
    tecnicas: str = Form(""),
    link_externo: str = Form(""),
    observacoes: str = Form(""),
    capa: Optional[UploadFile] = None,
):
    if models.obter_beat(beat_id) is None:
        raise HTTPException(404, "Beat não encontrado.")
    if not nome.strip():
        raise HTTPException(400, "Informe um nome para o beat.")
    _validar_campos_beat(origem_tipo, origem_metodo, status)

    capa_dados, capa_mime = None, None
    if capa is not None and capa.filename:
        capa_dados = await capa.read()
        capa_mime = fotos.mime_de_arquivo(capa, capa_dados)

    models.atualizar_beat(
        beat_id, nome.strip(), data, bpm, tonalidade.strip(), duracao_alvo.strip(),
        origem_tipo, origem_referencia.strip(), origem_metodo.strip(),
        status, tecnicas.strip(), link_externo.strip(), observacoes.strip(),
        capa_dados=capa_dados, capa_mime=capa_mime,
    )
    return _beat_out(models.obter_beat(beat_id))


@router.delete("/beats/{beat_id}", status_code=204)
def excluir_beat(beat_id: int):
    if models.obter_beat(beat_id) is None:
        raise HTTPException(404, "Beat não encontrado.")
    models.excluir_beat(beat_id)


@router.get("/beats/{beat_id}/capa")
def obter_capa_beat(beat_id: int):
    capa = models.obter_capa_beat(beat_id)
    if capa is None:
        raise HTTPException(404, "Esse beat não tem capa.")
    dados, mime = capa
    return Response(content=dados, media_type=mime, headers={"Cache-Control": "public, max-age=86400"})


# ---------------------------------------------------------------------------
# sessões
# ---------------------------------------------------------------------------

def _sessao_out(sessao: dict) -> dict:
    sessao = dict(sessao)
    sessao["audio_url"] = f"/api/beatforge/sessoes/{int(sessao['id'])}/audio" if sessao.get("audio_mime") else None
    return sessao


@router.get("/beats/{beat_id}/sessoes")
def listar_sessoes(beat_id: int):
    if models.obter_beat(beat_id) is None:
        raise HTTPException(404, "Beat não encontrado.")
    return [_sessao_out(s) for s in _df_records(models.listar_sessoes(beat_id))]


@router.post("/beats/{beat_id}/sessoes", status_code=201)
async def criar_sessao(
    beat_id: int,
    data: str = Form(...),
    duracao_minutos: int = Form(...),
    proximo_passo_brutal: str = Form(...),
    estado_emocional_snapshot: str = Form(""),
    referencia_audicao_snapshot: str = Form(""),
    observacao: str = Form(""),
    audio: Optional[UploadFile] = None,
):
    if models.obter_beat(beat_id) is None:
        raise HTTPException(404, "Beat não encontrado.")
    if not proximo_passo_brutal.strip():
        raise HTTPException(
            400, "Sem Próximo Passo Brutal, sem fechar sessão — defina uma ação específica antes de salvar."
        )
    if duracao_minutos <= 0:
        raise HTTPException(400, "Informe uma duração maior que zero.")

    audio_dados, audio_mime = None, None
    if audio is not None and audio.filename:
        audio_dados = await audio.read()
        audio_mime = audio.content_type or "audio/webm"

    models.inserir_sessao(
        beat_id, data, duracao_minutos, proximo_passo_brutal.strip(),
        estado_emocional_snapshot.strip(), referencia_audicao_snapshot.strip(),
        observacao.strip(), audio_dados=audio_dados, audio_mime=audio_mime,
    )
    return _beat_out(models.obter_beat(beat_id))


@router.delete("/sessoes/{sessao_id}", status_code=204)
def excluir_sessao(sessao_id: int):
    models.excluir_sessao(sessao_id)


@router.get("/sessoes/{sessao_id}/audio")
def obter_audio_sessao(sessao_id: int):
    audio = models.obter_audio_sessao(sessao_id)
    if audio is None:
        raise HTTPException(404, "Essa sessão não tem áudio.")
    dados, mime = audio
    return Response(content=dados, media_type=mime, headers={"Cache-Control": "public, max-age=86400"})


# ---------------------------------------------------------------------------
# dicas
# ---------------------------------------------------------------------------

@router.get("/dicas")
def listar_dicas():
    return _df_records(models.listar_dicas())


class DicaIn(BaseModel):
    texto: str


@router.post("/dicas", status_code=201)
def criar_dica(body: DicaIn):
    if not body.texto.strip():
        raise HTTPException(400, "Escreva o texto da dica.")
    dica_id = models.inserir_dica(body.texto.strip())
    return {"id": dica_id, "texto": body.texto.strip()}


@router.delete("/dicas/{dica_id}", status_code=204)
def excluir_dica(dica_id: int):
    models.excluir_dica(dica_id)


# ---------------------------------------------------------------------------
# crate de samples
# ---------------------------------------------------------------------------

@router.get("/crate")
def listar_crate(status: str = ""):
    return _df_records(models.listar_crate(status=status or None))


@router.get("/crate/sortear")
def sortear_crate():
    item = models.sortear_item_crate()
    if item is None:
        raise HTTPException(404, "Nenhum sample novo no crate — adicione alguns antes de sortear.")
    return item


class CrateIn(BaseModel):
    link: str
    nome: str = ""
    fonte: str = ""
    tags: str = ""
    observacao: str = ""


@router.post("/crate", status_code=201)
def criar_item_crate(body: CrateIn):
    link = body.link.strip()
    if not link:
        raise HTTPException(400, "Informe o link do Spotify.")

    nome, capa_url = body.nome.strip(), ""
    metadata = spotify_oembed.buscar_metadata_spotify(link)
    if metadata:
        nome = nome or metadata["titulo"]
        capa_url = metadata["capa_url"]

    item_id = models.inserir_item_crate(
        link, nome, body.fonte.strip(), body.tags.strip(), body.observacao.strip(), capa_url,
    )
    return models.obter_item_crate(item_id)


class CrateUsarIn(BaseModel):
    data: str


@router.post("/crate/{item_id}/usar", status_code=201)
def usar_item_crate(item_id: int, body: CrateUsarIn):
    """Cria um beat a partir de um item do crate (fluxo do sorteio) — origem
    já vem preenchida com o link/nome do sample, sem exigir 'como extraiu'
    ainda (isso só se sabe depois de mexer no beat de verdade; editável
    depois no painel 'editar'). Baixa a capa do Spotify pro beat também,
    quando disponível."""
    item = models.obter_item_crate(item_id)
    if item is None:
        raise HTTPException(404, "Item não encontrado.")

    capa_dados, capa_mime = None, None
    baixada = spotify_oembed.baixar_capa(item.get("capa_url") or "")
    if baixada:
        capa_dados, capa_mime = baixada

    beat_id = models.inserir_beat(
        item["nome"] or item["link"], body.data, None, "", "",
        "sample", item["nome"] or item["link"], "",
        "Loop Eterno", "", item["link"], item.get("observacao") or "",
        capa_dados=capa_dados, capa_mime=capa_mime,
    )
    models.atualizar_status_crate(item_id, "usado")
    return _beat_out(models.obter_beat(beat_id))


class CrateStatusIn(BaseModel):
    status: str


@router.patch("/crate/{item_id}")
def atualizar_status_crate(item_id: int, body: CrateStatusIn):
    if models.obter_item_crate(item_id) is None:
        raise HTTPException(404, "Item não encontrado.")
    if body.status not in ("novo", "usado", "descartado"):
        raise HTTPException(400, "status inválido.")
    models.atualizar_status_crate(item_id, body.status)
    return models.obter_item_crate(item_id)


@router.delete("/crate/{item_id}", status_code=204)
def excluir_item_crate(item_id: int):
    if models.obter_item_crate(item_id) is None:
        raise HTTPException(404, "Item não encontrado.")
    models.excluir_item_crate(item_id)
