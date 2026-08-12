"""Regras de negócio do módulo Música: agregações sobre escutas e álbuns.

Port de modules/musica/calculations.py — verbatim, exceto os imports
(pacote relativo em vez de módulo solto). O arquivo original já não tinha
nenhuma dependência de Streamlit, então a lógica é idêntica linha a linha.
"""

from datetime import date, timedelta

import pandas as pd

from . import repo as models
from . import utils


def nota_media_album(album_id: int) -> float | None:
    escutas = models.listar_escutas(album_id)
    notas = escutas["nota"].dropna()
    if notas.empty:
        return None
    return round(notas.mean(), 2)


def total_escutas_album(album_id: int) -> int:
    return len(models.listar_escutas(album_id))


def resumo_geral() -> dict:
    albuns = models.listar_albuns()
    escutas = models.listar_escutas_com_album()

    nota_media_geral = None
    if not escutas.empty:
        notas = escutas["nota"].dropna()
        if not notas.empty:
            nota_media_geral = round(notas.mean(), 2)

    return {
        "total_albuns": len(albuns),
        "total_escutas": len(escutas),
        "nota_media_geral": nota_media_geral,
    }


def _filtrar_periodo(escutas: pd.DataFrame, data_inicio: str, data_fim: str) -> pd.DataFrame:
    if escutas.empty:
        return escutas
    return escutas[(escutas["data"] >= data_inicio) & (escutas["data"] <= data_fim)]


def escutas_por_mes(data_inicio: str, data_fim: str) -> pd.DataFrame:
    inicio = date.fromisoformat(data_inicio)
    fim = date.fromisoformat(data_fim)
    periodos = []
    cursor = date(inicio.year, inicio.month, 1)
    while cursor <= fim:
        periodos.append(cursor.strftime("%Y-%m"))
        cursor = utils.somar_meses(cursor, 1)

    escutas = _filtrar_periodo(models.listar_escutas_com_album(), data_inicio, data_fim)
    contagem_por_periodo = {}
    if not escutas.empty:
        periodo_da_escuta = escutas["data"].str.slice(0, 7)
        contagem_por_periodo = periodo_da_escuta.value_counts().to_dict()

    return pd.DataFrame({
        "periodo": periodos,
        "mes_nome": [utils.nome_mes_curto(p) for p in periodos],
        "total": [int(contagem_por_periodo.get(p, 0)) for p in periodos],
    })


def distribuicao_notas(data_inicio: str, data_fim: str) -> pd.DataFrame:
    escutas = _filtrar_periodo(models.listar_escutas_com_album(), data_inicio, data_fim)
    notas_validas = escutas["nota"].dropna() if not escutas.empty else pd.Series(dtype=float)
    contagem = notas_validas.value_counts().to_dict()

    return pd.DataFrame({
        "nota": utils.OPCOES_NOTA,
        "total": [int(contagem.get(n, 0)) for n in utils.OPCOES_NOTA],
    })


def top_artistas(data_inicio: str, data_fim: str, limit: int = 8) -> pd.DataFrame:
    escutas = _filtrar_periodo(models.listar_escutas_com_album(), data_inicio, data_fim)
    if escutas.empty:
        return pd.DataFrame(columns=["artista_nome", "total"])
    contagem = escutas.groupby("artista_nome").size().reset_index(name="total")
    return contagem.sort_values("total", ascending=False).head(limit)


def escutas_por_decada(data_inicio: str, data_fim: str) -> pd.DataFrame:
    escutas = _filtrar_periodo(models.listar_escutas_com_album(), data_inicio, data_fim)
    anos = escutas["album_ano"].dropna() if not escutas.empty else pd.Series(dtype=float)
    if anos.empty:
        return pd.DataFrame(columns=["decada", "total"])

    decadas = (anos.astype(int) // 10 * 10).astype(int)
    rotulos = decadas.map(lambda d: f"{d}s")
    contagem = rotulos.value_counts()
    ordem = sorted(contagem.index, key=lambda r: decadas[rotulos == r].iloc[0])
    return pd.DataFrame({"decada": ordem, "total": [int(contagem[d]) for d in ordem]})


def escutas_por_genero(data_inicio: str, data_fim: str, limit: int = 8) -> pd.DataFrame:
    escutas = _filtrar_periodo(models.listar_escutas_com_album(), data_inicio, data_fim)
    if escutas.empty:
        return pd.DataFrame(columns=["genero", "total"])
    generos = escutas["album_genero"].replace("", None).dropna()
    if generos.empty:
        return pd.DataFrame(columns=["genero", "total"])
    contagem = generos.value_counts().head(limit).reset_index()
    contagem.columns = ["genero", "total"]
    return contagem


def nota_media_por_genero(data_inicio: str, data_fim: str, limit: int = 8) -> pd.DataFrame:
    escutas = _filtrar_periodo(models.listar_escutas_com_album(), data_inicio, data_fim)
    if escutas.empty:
        return pd.DataFrame(columns=["genero", "nota_media"])
    validas = escutas[(escutas["album_genero"] != "") & escutas["nota"].notna()]
    if validas.empty:
        return pd.DataFrame(columns=["genero", "nota_media"])
    medias = validas.groupby("album_genero")["nota"].mean().round(2).sort_values(ascending=False).head(limit)
    return medias.reset_index().rename(columns={"album_genero": "genero", "nota": "nota_media"})


def nota_media_por_decada(data_inicio: str, data_fim: str) -> pd.DataFrame:
    escutas = _filtrar_periodo(models.listar_escutas_com_album(), data_inicio, data_fim)
    if escutas.empty:
        return pd.DataFrame(columns=["decada", "nota_media"])
    validas = escutas[escutas["album_ano"].notna() & escutas["nota"].notna()].copy()
    if validas.empty:
        return pd.DataFrame(columns=["decada", "nota_media"])
    validas["decada"] = (validas["album_ano"].astype(int) // 10 * 10).astype(int)
    medias = validas.groupby("decada")["nota"].mean().round(2)
    ordem = sorted(medias.index)
    return pd.DataFrame({"decada": [f"{d}s" for d in ordem], "nota_media": [medias[d] for d in ordem]})


def top_albuns_periodo(data_inicio: str, data_fim: str, limite: int) -> pd.DataFrame:
    colunas = ["album_id", "album_nome", "artista_nome", "total"]
    escutas = _filtrar_periodo(models.listar_escutas_com_album(), data_inicio, data_fim)
    if escutas.empty:
        return pd.DataFrame(columns=colunas)

    agrupado = (
        escutas.groupby(["album_id", "album_nome", "artista_nome"])
        .size()
        .reset_index(name="total")
        .sort_values("total", ascending=False)
    )
    return agrupado.head(limite)


def top_albuns_historico(data_inicio: str, data_fim: str, limite: int) -> pd.DataFrame:
    """Agrupa por album_spotify_id (nunca por artista) e nunca repete
    capa_url no resultado — ver docstring original em
    modules/musica/calculations.py pro raciocínio completo."""
    colunas = ["album_nome", "artista_nome", "capa_url", "total"]
    historico = models.listar_historico(limit=100000)
    if historico.empty:
        return pd.DataFrame(columns=colunas)

    dia = _dia_brt(historico["tocado_em"])
    periodo = historico[(dia >= data_inicio) & (dia <= data_fim)]
    if periodo.empty:
        return pd.DataFrame(columns=colunas)

    periodo = periodo.copy()
    periodo["chave_album"] = periodo["album_spotify_id"].where(
        periodo["album_spotify_id"] != "", periodo["album_nome"] + "||" + periodo["artista_nome"],
    )

    agrupado = (
        periodo.groupby("chave_album")
        .agg(
            album_nome=("album_nome", "first"),
            artista_nome=("artista_nome", "first"),
            capa_url=("capa_url", "first"),
            total=("chave_album", "size"),
        )[colunas]
        .sort_values("total", ascending=False)
    )

    tem_capa = agrupado["capa_url"] != ""
    sem_repetir = pd.concat([
        agrupado[tem_capa].drop_duplicates(subset="capa_url", keep="first"),
        agrupado[~tem_capa],
    ]).sort_values("total", ascending=False)

    return sem_repetir.head(limite)


def _historico_periodo(data_inicio: str, data_fim: str) -> pd.DataFrame:
    historico = models.listar_historico(limit=100000)
    if historico.empty:
        return historico
    dia = _dia_brt(historico["tocado_em"])
    return historico[(dia >= data_inicio) & (dia <= data_fim)]


def _horario_brt(tocado_em: pd.Series) -> pd.Series:
    """UTC-3 fixo (sem horário de verão desde 2019) — não trocar por
    zoneinfo/timezone dinâmico sem confirmar que o resultado bate."""
    utc = pd.to_datetime(tocado_em, format="ISO8601", utc=True)
    return utc - pd.Timedelta(hours=3)


def _dia_brt(tocado_em: pd.Series) -> pd.Series:
    """Data (YYYY-MM-DD) no fuso de Brasília — tocado_em vem em UTC direto
    do Spotify (played_at), então fatiar a string crua faz uma escuta de
    madrugada (ainda "ontem" em BRT) cair no dia seguinte errado."""
    return _horario_brt(tocado_em).dt.strftime("%Y-%m-%d")


def top_artistas_historico(data_inicio: str, data_fim: str, limite: int = 8) -> pd.DataFrame:
    colunas = ["artista_nome", "total"]
    periodo = _historico_periodo(data_inicio, data_fim)
    if periodo.empty:
        return pd.DataFrame(columns=colunas)
    contagem = periodo.groupby("artista_nome").size().reset_index(name="total")
    return contagem.sort_values("total", ascending=False).head(limite)


def top_artistas_historico_com_id(data_inicio: str, data_fim: str, limite: int = 15) -> pd.DataFrame:
    colunas = ["artista_nome", "artista_spotify_id", "total"]
    periodo = _historico_periodo(data_inicio, data_fim)
    if periodo.empty:
        return pd.DataFrame(columns=colunas)
    contagem = (
        periodo.groupby(["artista_nome", "artista_spotify_id"]).size().reset_index(name="total")
        .sort_values("total", ascending=False)
    )
    return contagem.head(limite)


def top_faixas_historico(data_inicio: str, data_fim: str, limite: int = 8) -> pd.DataFrame:
    colunas = ["faixa_nome", "artista_nome", "total"]
    periodo = _historico_periodo(data_inicio, data_fim)
    if periodo.empty:
        return pd.DataFrame(columns=colunas)
    contagem = (
        periodo.groupby(["faixa_nome", "artista_nome"]).size().reset_index(name="total")
        .sort_values("total", ascending=False)
    )
    return contagem.head(limite)


def habito_por_hora(data_inicio: str, data_fim: str) -> pd.DataFrame:
    periodo = _historico_periodo(data_inicio, data_fim)
    horas = list(range(24))
    if periodo.empty:
        return pd.DataFrame({"hora": horas, "total": [0] * 24})
    contagem = _horario_brt(periodo["tocado_em"]).dt.hour.value_counts().to_dict()
    return pd.DataFrame({"hora": horas, "total": [int(contagem.get(h, 0)) for h in horas]})


def sequencia_dias_ativos(referencia: str) -> int:
    historico = models.listar_historico(limit=100000)
    if historico.empty:
        return 0
    dias_ativos = set(_horario_brt(historico["tocado_em"]).dt.date)
    cursor = date.fromisoformat(referencia)
    sequencia = 0
    while cursor in dias_ativos:
        sequencia += 1
        cursor -= timedelta(days=1)
    return sequencia


def resumo_periodo_real(data_inicio: str, data_fim: str) -> dict:
    sequencia_dias = sequencia_dias_ativos(data_fim)
    periodo = _historico_periodo(data_inicio, data_fim)
    if periodo.empty:
        return {
            "total_faixas": 0, "minutos": 0, "artistas_distintos": 0,
            "top_artista": None, "top_faixa": None, "top_faixa_artista": None,
            "hora_favorita": None, "sequencia_dias": sequencia_dias,
        }

    minutos = int(periodo["duration_ms"].fillna(0).sum() // 60000)

    top_artista = None
    contagem_artistas = periodo.groupby("artista_nome").size().sort_values(ascending=False)
    if not contagem_artistas.empty:
        top_artista = contagem_artistas.index[0]

    top_faixa = None
    top_faixa_artista = None
    contagem_faixas = periodo.groupby(["faixa_nome", "artista_nome"]).size().sort_values(ascending=False)
    if not contagem_faixas.empty:
        top_faixa, top_faixa_artista = contagem_faixas.index[0]

    hora_favorita = int(_horario_brt(periodo["tocado_em"]).dt.hour.value_counts().idxmax())

    return {
        "total_faixas": len(periodo),
        "minutos": minutos,
        "artistas_distintos": int(periodo["artista_nome"].nunique()),
        "top_artista": top_artista,
        "top_faixa": top_faixa,
        "top_faixa_artista": top_faixa_artista,
        "hora_favorita": hora_favorita,
        "sequencia_dias": sequencia_dias,
    }


def habito_por_dia_semana(data_inicio: str, data_fim: str) -> pd.DataFrame:
    dias = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    periodo = _historico_periodo(data_inicio, data_fim)
    if periodo.empty:
        return pd.DataFrame({"dia_semana": dias, "total": [0] * 7})
    contagem = _horario_brt(periodo["tocado_em"]).dt.dayofweek.value_counts().to_dict()
    return pd.DataFrame({"dia_semana": dias, "total": [int(contagem.get(i, 0)) for i in range(7)]})


def contexto_ia_diario(data_inicio: str, data_fim: str) -> str:
    resumo = resumo_periodo(data_inicio, data_fim)
    top_art = top_artistas(data_inicio, data_fim, 5)
    generos = escutas_por_genero(data_inicio, data_fim, 5)
    decadas = escutas_por_decada(data_inicio, data_fim)
    notas = distribuicao_notas(data_inicio, data_fim)

    linhas = [
        f"Álbuns novos cadastrados: {resumo['albuns_novos']}",
        f"Escutas registradas: {resumo['escutas']}",
        f"Nota média: {resumo['nota_media'] if resumo['nota_media'] is not None else 'sem notas'}",
        f"Artista destaque: {resumo['artista_destaque'] or 'nenhum'}",
    ]
    if not top_art.empty:
        linhas.append("Top artistas: " + ", ".join(f"{r.artista_nome} ({r.total})" for r in top_art.itertuples()))
    if not generos.empty:
        linhas.append("Gêneros mais escutados: " + ", ".join(f"{r.genero} ({r.total})" for r in generos.itertuples()))
    if not decadas.empty:
        linhas.append("Escutas por década de lançamento: " + ", ".join(f"{r.decada} ({r.total})" for r in decadas.itertuples()))
    if notas["total"].sum() > 0:
        pico = notas.loc[notas["total"].idxmax()]
        linhas.append(f"Nota mais comum: {utils.formatar_nota(pico['nota'])} ({int(pico['total'])}x)")
    return "\n".join(linhas)


def contexto_ia_real(data_inicio: str, data_fim: str) -> str:
    dados = resumo_periodo_real(data_inicio, data_fim)
    top_art = top_artistas_historico(data_inicio, data_fim, 5)
    top_fx = top_faixas_historico(data_inicio, data_fim, 5)
    horas = habito_por_hora(data_inicio, data_fim)
    dias = habito_por_dia_semana(data_inicio, data_fim)

    linhas = [
        f"Faixas ouvidas de verdade: {dados['total_faixas']}",
        f"Tempo ouvido: {dados['minutos']} minutos",
        f"Artistas diferentes: {dados['artistas_distintos']}",
        f"Artista mais tocado: {dados['top_artista'] or 'nenhum'}",
        f"Faixa mais tocada: {dados['top_faixa'] or 'nenhuma'}"
        + (f" (de {dados['top_faixa_artista']})" if dados["top_faixa"] else ""),
        f"Sequência de dias seguidos ouvindo: {dados['sequencia_dias']}",
    ]
    if not top_art.empty:
        linhas.append("Top artistas: " + ", ".join(f"{r.artista_nome} ({r.total})" for r in top_art.itertuples()))
    if not top_fx.empty:
        linhas.append("Top faixas: " + ", ".join(f"{r.faixa_nome} — {r.artista_nome} ({r.total})" for r in top_fx.itertuples()))
    if horas["total"].sum() > 0:
        pico_hora = horas.loc[horas["total"].idxmax()]
        linhas.append(f"Hora do dia com mais faixas tocadas: {int(pico_hora['hora'])}h ({int(pico_hora['total'])} faixas)")
    if dias["total"].sum() > 0:
        pico_dia = dias.loc[dias["total"].idxmax()]
        linhas.append(f"Dia da semana com mais faixas tocadas: {pico_dia['dia_semana']} ({int(pico_dia['total'])} faixas)")
    return "\n".join(linhas)


def resumo_periodo(data_inicio: str, data_fim: str) -> dict:
    escutas = _filtrar_periodo(models.listar_escutas_com_album(), data_inicio, data_fim)

    albuns = models.listar_albuns()
    albuns_periodo = pd.DataFrame()
    if not albuns.empty:
        criado_em = albuns["created_at"].str.slice(0, 10)
        albuns_periodo = albuns[(criado_em >= data_inicio) & (criado_em <= data_fim)]

    nota_media = None
    artista_destaque = None
    if not escutas.empty:
        notas = escutas["nota"].dropna()
        if not notas.empty:
            nota_media = round(notas.mean(), 2)
        top = escutas.groupby("artista_nome").size().sort_values(ascending=False)
        if not top.empty:
            artista_destaque = top.index[0]

    return {
        "albuns_novos": len(albuns_periodo),
        "escutas": len(escutas),
        "nota_media": nota_media,
        "artista_destaque": artista_destaque,
    }
