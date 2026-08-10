"""Regras de negócio do módulo Música: agregações sobre escutas e álbuns.
Sem acesso direto a SQL — usa models.py.
"""

from datetime import date

import pandas as pd

import models
import utils


def nota_media_album(album_id: int) -> float | None:
    """Média das notas registradas nas escutas desse álbum (ignora escutas
    sem nota). None se não há nenhuma nota ainda."""
    escutas = models.listar_escutas(album_id)
    notas = escutas["nota"].dropna()
    if notas.empty:
        return None
    return round(notas.mean(), 2)


def total_escutas_album(album_id: int) -> int:
    return len(models.listar_escutas(album_id))


def resumo_geral() -> dict:
    """Números curtos para o topo das páginas: quantos álbuns, quantas
    escutas ao todo, e a nota média geral."""
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
    """Contagem de escutas por mês dentro do período — inclui meses sem
    nenhuma escuta (total 0), pra não sumir com o eixo do gráfico."""
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
    """Quantas escutas caíram em cada nota possível (0.5 a 5.0), dentro do período."""
    escutas = _filtrar_periodo(models.listar_escutas_com_album(), data_inicio, data_fim)
    notas_validas = escutas["nota"].dropna() if not escutas.empty else pd.Series(dtype=float)
    contagem = notas_validas.value_counts().to_dict()

    return pd.DataFrame({
        "nota": utils.OPCOES_NOTA,
        "total": [int(contagem.get(n, 0)) for n in utils.OPCOES_NOTA],
    })


def top_artistas(data_inicio: str, data_fim: str, limit: int = 8) -> pd.DataFrame:
    """Artistas com mais escutas registradas dentro do período (não álbuns
    distintos — um artista ouvido muitas vezes no mesmo álbum ainda conta
    bastante)."""
    escutas = _filtrar_periodo(models.listar_escutas_com_album(), data_inicio, data_fim)
    if escutas.empty:
        return pd.DataFrame(columns=["artista_nome", "total"])
    contagem = escutas.groupby("artista_nome").size().reset_index(name="total")
    return contagem.sort_values("total", ascending=False).head(limit)


def escutas_por_decada(data_inicio: str, data_fim: str) -> pd.DataFrame:
    """Escutas agrupadas pela década de lançamento do álbum (não pela data
    da escuta) — "anos 90", "anos 2000" etc. Ignora álbuns sem ano
    cadastrado (não entram nem como "desconhecido", pra não distorcer o
    eixo do gráfico com uma barra sem sentido comparativo)."""
    escutas = _filtrar_periodo(models.listar_escutas_com_album(), data_inicio, data_fim)
    anos = escutas["album_ano"].dropna() if not escutas.empty else pd.Series(dtype=float)
    if anos.empty:
        return pd.DataFrame(columns=["decada", "total"])

    decadas = (anos.astype(int) // 10 * 10).astype(int)
    rotulos = decadas.map(lambda d: f"{d}s")
    contagem = rotulos.value_counts()
    # ordena pelo início real da década (não alfabético — "20s" não pode
    # vir antes de "1990s")
    ordem = sorted(contagem.index, key=lambda r: decadas[rotulos == r].iloc[0])
    return pd.DataFrame({"decada": ordem, "total": [int(contagem[d]) for d in ordem]})


def escutas_por_genero(data_inicio: str, data_fim: str, limit: int = 8) -> pd.DataFrame:
    """Gêneros mais escutados no período, pelo campo `genero` do álbum
    (preenchido manualmente ou sugerido a partir do artista no Spotify).
    Ignora álbuns sem gênero cadastrado."""
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
    """Nota média das escutas avaliadas, por gênero do álbum — só entram
    gêneros com pelo menos uma escuta com nota (ignora sem nota e sem
    gênero cadastrado)."""
    escutas = _filtrar_periodo(models.listar_escutas_com_album(), data_inicio, data_fim)
    if escutas.empty:
        return pd.DataFrame(columns=["genero", "nota_media"])
    validas = escutas[(escutas["album_genero"] != "") & escutas["nota"].notna()]
    if validas.empty:
        return pd.DataFrame(columns=["genero", "nota_media"])
    medias = validas.groupby("album_genero")["nota"].mean().round(2).sort_values(ascending=False).head(limit)
    return medias.reset_index().rename(columns={"album_genero": "genero", "nota": "nota_media"})


def nota_media_por_decada(data_inicio: str, data_fim: str) -> pd.DataFrame:
    """Nota média das escutas avaliadas, por década de lançamento do
    álbum — pra ver se você costuma gostar mais de disco antigo ou novo.
    Ignora álbuns sem ano cadastrado e escutas sem nota."""
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
    """Álbuns mais escutados no período [data_inicio, data_fim] (ISO,
    ambos inclusive), rankeados por número de escutas — pra colagem."""
    colunas = ["album_id", "album_nome", "artista_nome", "capa_path", "total"]
    escutas = _filtrar_periodo(models.listar_escutas_com_album(), data_inicio, data_fim)
    if escutas.empty:
        return pd.DataFrame(columns=colunas)

    agrupado = (
        escutas.groupby(["album_id", "album_nome", "artista_nome", "capa_path"])
        .size()
        .reset_index(name="total")
        .sort_values("total", ascending=False)
    )
    return agrupado.head(limite)


def top_albuns_historico(data_inicio: str, data_fim: str, limite: int) -> pd.DataFrame:
    """Álbuns mais tocados de verdade no período (histórico sincronizado
    da conta Spotify, não o que foi avaliado no Diário), rankeados por
    número de faixas tocadas — pra colagem a partir do consumo real."""
    colunas = ["album_nome", "artista_nome", "capa_url", "total"]
    historico = models.listar_historico(limit=100000)
    if historico.empty:
        return pd.DataFrame(columns=colunas)

    dia = historico["tocado_em"].str.slice(0, 10)
    periodo = historico[(dia >= data_inicio) & (dia <= data_fim)]
    if periodo.empty:
        return pd.DataFrame(columns=colunas)

    agrupado = (
        periodo.groupby(["album_nome", "artista_nome", "capa_url"])
        .size()
        .reset_index(name="total")
        .sort_values("total", ascending=False)
    )
    return agrupado.head(limite)


def _historico_periodo(data_inicio: str, data_fim: str) -> pd.DataFrame:
    historico = models.listar_historico(limit=100000)
    if historico.empty:
        return historico
    dia = historico["tocado_em"].str.slice(0, 10)
    return historico[(dia >= data_inicio) & (dia <= data_fim)]


def _horario_brt(tocado_em: pd.Series) -> pd.Series:
    """Spotify manda `played_at` em UTC (ex: '2026-08-10T14:23:45.000Z') —
    converte pra horário de Brasília (UTC-3, sem horário de verão desde
    2019) antes de agrupar por hora/dia da semana, senão o hábito de
    escuta fica sistematicamente deslocado em 3h."""
    utc = pd.to_datetime(tocado_em, format="ISO8601", utc=True)
    return utc - pd.Timedelta(hours=3)


def top_artistas_historico(data_inicio: str, data_fim: str, limite: int = 8) -> pd.DataFrame:
    """Artistas mais tocados de verdade no período (histórico sincronizado
    da conta Spotify), rankeados por número de faixas tocadas — diferente
    de `top_artistas`, que conta escutas avaliadas no Diário."""
    colunas = ["artista_nome", "total"]
    periodo = _historico_periodo(data_inicio, data_fim)
    if periodo.empty:
        return pd.DataFrame(columns=colunas)
    contagem = periodo.groupby("artista_nome").size().reset_index(name="total")
    return contagem.sort_values("total", ascending=False).head(limite)


def top_faixas_historico(data_inicio: str, data_fim: str, limite: int = 8) -> pd.DataFrame:
    """Faixas mais tocadas de verdade no período (histórico sincronizado),
    rankeadas por número de reproduções."""
    colunas = ["faixa_nome", "artista_nome", "total"]
    periodo = _historico_periodo(data_inicio, data_fim)
    if periodo.empty:
        return pd.DataFrame(columns=colunas)
    contagem = (
        periodo.groupby(["faixa_nome", "artista_nome"]).size().reset_index(name="total")
        .sort_values("total", ascending=False)
    )
    return contagem.head(limite)


def volume_historico_por_mes(data_inicio: str, data_fim: str) -> pd.DataFrame:
    """Quantas faixas foram tocadas de verdade por mês dentro do período —
    inclui meses sem nenhuma faixa (total 0), pra não sumir com o eixo do
    gráfico."""
    inicio = date.fromisoformat(data_inicio)
    fim = date.fromisoformat(data_fim)
    periodos = []
    cursor = date(inicio.year, inicio.month, 1)
    while cursor <= fim:
        periodos.append(cursor.strftime("%Y-%m"))
        cursor = utils.somar_meses(cursor, 1)

    periodo = _historico_periodo(data_inicio, data_fim)
    contagem_por_periodo = {}
    if not periodo.empty:
        periodo_da_faixa = periodo["tocado_em"].str.slice(0, 7)
        contagem_por_periodo = periodo_da_faixa.value_counts().to_dict()

    return pd.DataFrame({
        "periodo": periodos,
        "mes_nome": [utils.nome_mes_curto(p) for p in periodos],
        "total": [int(contagem_por_periodo.get(p, 0)) for p in periodos],
    })


def habito_por_hora(data_inicio: str, data_fim: str) -> pd.DataFrame:
    """Quantas faixas tocadas em cada hora do dia (0-23, horário de
    Brasília), somando o período inteiro — pra ver em que hora do dia
    você mais ouve música de verdade."""
    periodo = _historico_periodo(data_inicio, data_fim)
    horas = list(range(24))
    if periodo.empty:
        return pd.DataFrame({"hora": horas, "total": [0] * 24})
    contagem = _horario_brt(periodo["tocado_em"]).dt.hour.value_counts().to_dict()
    return pd.DataFrame({"hora": horas, "total": [int(contagem.get(h, 0)) for h in horas]})


def resumo_periodo_real(data_inicio: str, data_fim: str) -> dict:
    """Números do histórico real do período, pro relatório estilo Stories.
    `minutos` só conta faixas sincronizadas depois que `duration_ms` passou
    a ser guardado (2026-08) — faixas mais antigas do histórico entram como
    0 nesse total, mas continuam contando normalmente pro resto (total de
    faixas, top artista/faixa, hora favorita)."""
    periodo = _historico_periodo(data_inicio, data_fim)
    if periodo.empty:
        return {
            "total_faixas": 0, "minutos": 0, "artistas_distintos": 0,
            "top_artista": None, "top_faixa": None, "top_faixa_artista": None,
            "hora_favorita": None,
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
    }


def habito_por_dia_semana(data_inicio: str, data_fim: str) -> pd.DataFrame:
    """Quantas faixas tocadas em cada dia da semana (horário de Brasília),
    somando o período inteiro."""
    dias = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
    periodo = _historico_periodo(data_inicio, data_fim)
    if periodo.empty:
        return pd.DataFrame({"dia_semana": dias, "total": [0] * 7})
    contagem = _horario_brt(periodo["tocado_em"]).dt.dayofweek.value_counts().to_dict()
    return pd.DataFrame({"dia_semana": dias, "total": [int(contagem.get(i, 0)) for i in range(7)]})


def resumo_periodo(data_inicio: str, data_fim: str) -> dict:
    """Números do período: álbuns novos no catálogo, escutas registradas,
    nota média e o artista mais escutado dentro dele."""
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
