"""Estatísticas: poucos números que importam sobre a jornada musical,
filtráveis por período e por fonte (o que você mesmo avalia no Diário, ou
o que a conta Spotify realmente tocou)."""

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import calculations as calc
import database
import models
import relatorio_stories
import spotify_client
import ui
import utils

st.set_page_config(page_title="Estatísticas | Música", page_icon="🎵", layout="wide")
database.inicializar_banco()
ui.aplicar_tema()

CHART_LAYOUT = dict(
    margin=dict(l=10, r=10, t=30, b=10),
    height=420,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="JetBrains Mono, monospace", color=utils.COR_TEXTO_MUTED),
)


def _cor_com_opacidade(cor_hex: str, alpha: float) -> str:
    cor_hex = cor_hex.lstrip("#")
    r, g, b = int(cor_hex[0:2], 16), int(cor_hex[2:4], 16), int(cor_hex[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def _cores_por_destaque(valores: list) -> list[str]:
    """Cor cheia pro maior valor da lista, cor apagada pro resto — o olho
    vai direto pro que importa em vez de N marcas do mesmo peso visual."""
    maximo = max(valores) if len(valores) else None
    return [utils.COR_ACENTO if v == maximo else _cor_com_opacidade(utils.COR_ACENTO, 0.4) for v in valores]


def _lollipop_horizontal(df: pd.DataFrame, col_categoria: str, col_valor: str, formatar=str) -> go.Figure:
    """Ranking horizontal em 'lollipop' (linha fina + ponto na ponta, valor
    escrito ao lado) — lê melhor que uma barra chapada pra um ranking curto
    (top N), e o primeiro colocado sai com cor cheia enquanto o resto fica
    apagado."""
    df = df.iloc[::-1].reset_index(drop=True)  # maior no topo do gráfico
    valores = df[col_valor].tolist()
    cores = _cores_por_destaque(valores)
    rotulos = [formatar(v) for v in valores]

    fig = go.Figure()
    for categoria, valor, cor in zip(df[col_categoria], valores, cores):
        fig.add_trace(go.Scatter(
            x=[0, valor], y=[categoria, categoria], mode="lines",
            line=dict(color=cor, width=4), hoverinfo="skip", showlegend=False,
        ))
    fig.add_trace(go.Scatter(
        x=valores, y=df[col_categoria], mode="markers+text",
        marker=dict(size=13, color=cores, line=dict(width=2, color=utils.COR_FUNDO)),
        text=rotulos, textposition="middle right",
        textfont=dict(color=utils.COR_TEXTO, family="JetBrains Mono, monospace", size=13),
        customdata=rotulos, hovertemplate="%{y}: %{customdata}<extra></extra>",
        showlegend=False,
    ))
    maximo = max(valores) if valores else 1
    fig.update_xaxes(showgrid=True, gridcolor=utils.COR_HAIRLINE, zeroline=False, range=[0, maximo * 1.4])
    fig.update_yaxes(showgrid=False, zeroline=False)
    fig.update_layout(**{**CHART_LAYOUT, "margin": dict(l=10, r=10, t=20, b=10)})
    return fig


def _lollipop_vertical(df: pd.DataFrame, col_categoria: str, col_valor: str, formatar=str, eixo_max=None) -> go.Figure:
    """Série categórica vertical em 'lollipop' — só rotula o ponto de pico
    diretamente (o resto fica disponível no eixo e no hover), pra não
    empilhar um número em cima de cada barra quando há muitas categorias
    (24 horas, 12 meses)."""
    valores = df[col_valor].tolist()
    cores = _cores_por_destaque(valores)
    maximo_valor = max(valores) if valores else 0
    rotulos_hover = [formatar(v) for v in valores]
    rotulos_visiveis = [formatar(v) if v == maximo_valor else "" for v in valores]

    fig = go.Figure()
    for categoria, valor, cor in zip(df[col_categoria], valores, cores):
        fig.add_trace(go.Scatter(
            x=[categoria, categoria], y=[0, valor], mode="lines",
            line=dict(color=cor, width=4), hoverinfo="skip", showlegend=False,
        ))
    fig.add_trace(go.Scatter(
        x=df[col_categoria], y=valores, mode="markers+text",
        marker=dict(size=12, color=cores, line=dict(width=2, color=utils.COR_FUNDO)),
        text=rotulos_visiveis, textposition="top center",
        textfont=dict(color=utils.COR_TEXTO, family="JetBrains Mono, monospace", size=14),
        customdata=rotulos_hover, hovertemplate="%{x}: %{customdata}<extra></extra>",
        showlegend=False,
    ))
    limite = eixo_max if eixo_max is not None else (maximo_valor * 1.3 if maximo_valor else 1)
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor=utils.COR_HAIRLINE, zeroline=False, range=[0, limite])
    fig.update_layout(**CHART_LAYOUT)
    return fig


def _com_tendencia(fig: go.Figure, df: pd.DataFrame, col_categoria: str, col_valor: str) -> go.Figure:
    """Acrescenta uma média móvel de 3 períodos por cima do lollipop
    vertical, no mesmo eixo (mesma unidade) — sem ela um gráfico mês a mês
    só mostra ruído, não se a tendência é de alta ou de baixa."""
    if len(df) < 2:
        return fig
    media_movel = df[col_valor].rolling(3, min_periods=1).mean()
    fig.add_trace(go.Scatter(
        x=df[col_categoria], y=media_movel, mode="lines",
        line=dict(color=_cor_com_opacidade(utils.COR_TEXTO, 0.55), width=2),
        hoverinfo="skip", showlegend=False,
    ))
    return fig


def _periodo_selecionado() -> tuple[str, str, str]:
    """Retorna (data_inicio_iso, data_fim_iso, rótulo pra exibição)."""
    hoje = date.today()
    atalho = st.radio(
        "Período", ["Este mês", "Este ano", "Todos os tempos", "Personalizado"],
        horizontal=True, label_visibility="collapsed", key="stats_periodo",
    )

    if atalho == "Este mês":
        inicio = hoje.replace(day=1)
        return inicio.isoformat(), hoje.isoformat(), "este mês"
    if atalho == "Este ano":
        inicio = date(hoje.year, 1, 1)
        return inicio.isoformat(), hoje.isoformat(), str(hoje.year)
    if atalho == "Todos os tempos":
        intervalo = models.intervalo_datas_escutas()
        if intervalo is None:
            return hoje.isoformat(), hoje.isoformat(), "todos os tempos"
        return intervalo[0], intervalo[1], "todos os tempos"

    c1, c2 = st.columns(2)
    inicio = c1.date_input("De", value=date(hoje.year, 1, 1), format="DD/MM/YYYY", key="stats_data_inicio")
    fim = c2.date_input("Até", value=hoje, format="DD/MM/YYYY", key="stats_data_fim")
    return inicio.isoformat(), fim.isoformat(), "período personalizado"


# ---------------------------------------------------------------------------
# Fonte "Diário" — o que você mesmo cadastra e avalia
# ---------------------------------------------------------------------------

def _secao_resumo(data_inicio: str, data_fim: str, rotulo: str) -> None:
    resumo = calc.resumo_periodo(data_inicio, data_fim)
    ui.eyebrow(f"resumo — {rotulo}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Álbuns novos", resumo["albuns_novos"])
    c2.metric("Escutas", resumo["escutas"])
    c3.metric("Nota média", utils.formatar_nota(resumo["nota_media"]))
    c4.metric("Artista destaque", resumo["artista_destaque"] or "—")


def _grafico_escutas_por_mes(data_inicio: str, data_fim: str) -> None:
    ui.eyebrow("atividade")
    st.subheader("Escutas por mês")
    df = calc.escutas_por_mes(data_inicio, data_fim)
    if df["total"].sum() == 0:
        st.caption("Nenhuma escuta registrada nesse período.")
        return
    fig = _com_tendencia(_lollipop_vertical(df, "mes_nome", "total"), df, "mes_nome", "total")
    st.plotly_chart(fig, use_container_width=True)


def _grafico_distribuicao_notas(data_inicio: str, data_fim: str) -> None:
    ui.eyebrow("avaliações")
    st.subheader("Distribuição de notas")
    df = calc.distribuicao_notas(data_inicio, data_fim)
    if df["total"].sum() == 0:
        st.caption("Nenhuma escuta avaliada nesse período.")
        return
    df = df.assign(nota_label=[utils.formatar_nota(n) for n in df["nota"]])
    st.plotly_chart(_lollipop_vertical(df, "nota_label", "total"), use_container_width=True)


def _grafico_top_artistas(data_inicio: str, data_fim: str) -> None:
    ui.eyebrow("recorrência")
    st.subheader("Artistas mais escutados")
    df = calc.top_artistas(data_inicio, data_fim, 8)
    if df.empty:
        st.caption("Nenhuma escuta registrada nesse período.")
        return
    st.plotly_chart(_lollipop_horizontal(df, "artista_nome", "total"), use_container_width=True)


def _grafico_por_decada(data_inicio: str, data_fim: str) -> None:
    ui.eyebrow("linha do tempo musical")
    st.subheader("Escutas por década de lançamento")
    df = calc.escutas_por_decada(data_inicio, data_fim)
    if df.empty:
        st.caption("Nenhum álbum com ano de lançamento cadastrado nesse período.")
        return
    st.plotly_chart(_lollipop_vertical(df, "decada", "total"), use_container_width=True)


def _grafico_por_genero(data_inicio: str, data_fim: str) -> None:
    ui.eyebrow("gosto musical")
    st.subheader("Gêneros mais escutados")
    df = calc.escutas_por_genero(data_inicio, data_fim)
    if df.empty:
        st.caption(
            "Nenhum álbum com gênero cadastrado nesse período — álbuns adicionados via busca "
            "no Spotify já sugerem um gênero automaticamente ao cadastrar."
        )
        return
    st.plotly_chart(_lollipop_horizontal(df, "genero", "total"), use_container_width=True)


def _grafico_nota_por_genero(data_inicio: str, data_fim: str) -> None:
    st.subheader("Nota média por gênero")
    df = calc.nota_media_por_genero(data_inicio, data_fim)
    if df.empty:
        st.caption("Nenhuma escuta avaliada com gênero cadastrado nesse período.")
        return
    st.plotly_chart(
        _lollipop_horizontal(df, "genero", "nota_media", formatar=utils.formatar_nota),
        use_container_width=True,
    )


def _grafico_nota_por_decada(data_inicio: str, data_fim: str) -> None:
    st.subheader("Nota média por década de lançamento (disco antigo ou novo?)")
    df = calc.nota_media_por_decada(data_inicio, data_fim)
    if df.empty:
        st.caption("Nenhuma escuta avaliada com ano de lançamento cadastrado nesse período.")
        return
    st.plotly_chart(
        _lollipop_vertical(df, "decada", "nota_media", formatar=utils.formatar_nota, eixo_max=5),
        use_container_width=True,
    )


def _secao_diario(data_inicio: str, data_fim: str, rotulo: str) -> None:
    _secao_resumo(data_inicio, data_fim, rotulo)
    st.divider()
    _grafico_escutas_por_mes(data_inicio, data_fim)
    st.divider()
    _grafico_distribuicao_notas(data_inicio, data_fim)
    st.divider()
    _grafico_top_artistas(data_inicio, data_fim)
    st.divider()
    _grafico_por_decada(data_inicio, data_fim)
    _grafico_nota_por_decada(data_inicio, data_fim)
    st.divider()
    _grafico_por_genero(data_inicio, data_fim)
    _grafico_nota_por_genero(data_inicio, data_fim)


# ---------------------------------------------------------------------------
# Fonte "Spotify" — o que a conta conectada realmente tocou
# ---------------------------------------------------------------------------

def _secao_resumo_real(data_inicio: str, data_fim: str, rotulo: str) -> None:
    dados = calc.resumo_periodo_real(data_inicio, data_fim)
    ui.eyebrow(f"resumo real — {rotulo}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Faixas ouvidas", dados["total_faixas"])
    horas, minutos_resto = divmod(dados["minutos"], 60)
    c2.metric("Tempo ouvido", f"{horas}h{minutos_resto:02d}" if horas else f"{minutos_resto}min")
    c3.metric("Artistas diferentes", dados["artistas_distintos"])
    c4.metric("Artista destaque", dados["top_artista"] or "—")


def _grafico_top_artistas_real(data_inicio: str, data_fim: str) -> None:
    ui.eyebrow("consumo real")
    st.subheader("Artistas mais tocados de verdade")
    df = calc.top_artistas_historico(data_inicio, data_fim, 8)
    if df.empty:
        st.caption("Nenhuma faixa sincronizada nesse período.")
        return
    st.plotly_chart(_lollipop_horizontal(df, "artista_nome", "total"), use_container_width=True)


def _grafico_top_faixas_real(data_inicio: str, data_fim: str) -> None:
    st.subheader("Faixas mais tocadas de verdade")
    df = calc.top_faixas_historico(data_inicio, data_fim, 8)
    if df.empty:
        st.caption("Nenhuma faixa sincronizada nesse período.")
        return
    df = df.assign(rotulo=[f"{f} — {a}" for f, a in zip(df["faixa_nome"], df["artista_nome"])])
    st.plotly_chart(_lollipop_horizontal(df, "rotulo", "total"), use_container_width=True)


def _grafico_volume_historico(data_inicio: str, data_fim: str) -> None:
    st.subheader("Faixas tocadas por mês")
    df = calc.volume_historico_por_mes(data_inicio, data_fim)
    if df["total"].sum() == 0:
        st.caption("Nenhuma faixa sincronizada nesse período.")
        return
    fig = _com_tendencia(_lollipop_vertical(df, "mes_nome", "total"), df, "mes_nome", "total")
    st.plotly_chart(fig, use_container_width=True)


def _grafico_habito_hora(data_inicio: str, data_fim: str) -> None:
    ui.eyebrow("hábito de escuta")
    st.subheader("Horário em que você mais escuta")
    df = calc.habito_por_hora(data_inicio, data_fim)
    if df["total"].sum() == 0:
        st.caption("Nenhuma faixa sincronizada nesse período.")
        return
    df = df.assign(hora_label=[f"{h}h" for h in df["hora"]])
    st.plotly_chart(_lollipop_vertical(df, "hora_label", "total"), use_container_width=True)


def _grafico_habito_dia_semana(data_inicio: str, data_fim: str) -> None:
    st.subheader("Dia da semana em que você mais escuta")
    df = calc.habito_por_dia_semana(data_inicio, data_fim)
    if df["total"].sum() == 0:
        st.caption("Nenhuma faixa sincronizada nesse período.")
        return
    st.plotly_chart(_lollipop_vertical(df, "dia_semana", "total"), use_container_width=True)


def _secao_relatorio_stories(data_inicio: str, data_fim: str, rotulo: str) -> None:
    dados = calc.resumo_periodo_real(data_inicio, data_fim)
    if dados["total_faixas"] == 0:
        return
    if st.button("gerar relatório estilo Stories", use_container_width=True, key="gerar_stories"):
        top_albuns = calc.top_albuns_historico(data_inicio, data_fim, 9).to_dict("records")
        imagem = relatorio_stories.gerar_relatorio_stories(dados, rotulo, top_albuns)
        st.session_state["stories_bytes"] = imagem
        st.session_state["stories_arquivo"] = f"spotify-{data_inicio}-a-{data_fim}.png"

    if st.session_state.get("stories_bytes"):
        c1, c2 = st.columns([1, 2])
        with c1:
            st.image(st.session_state["stories_bytes"], width=260)
        with c2:
            st.download_button(
                "baixar PNG",
                data=st.session_state["stories_bytes"],
                file_name=st.session_state["stories_arquivo"],
                mime="image/png",
            )


def _secao_spotify(data_inicio: str, data_fim: str, rotulo: str) -> None:
    """Estatísticas a partir do histórico real sincronizado da conta
    Spotify — diferente da fonte Diário, que vem do que você avalia
    manualmente. Só aparece se a conta estiver conectada; se não, indica
    onde conectar em vez de mostrar gráficos vazios."""
    if not spotify_client.conta_conectada():
        st.caption("Conecte sua conta na página **Spotify** para ver essas estatísticas.")
        return

    _secao_resumo_real(data_inicio, data_fim, rotulo)
    st.divider()
    _secao_relatorio_stories(data_inicio, data_fim, rotulo)
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        _grafico_top_artistas_real(data_inicio, data_fim)
    with col2:
        _grafico_top_faixas_real(data_inicio, data_fim)
    _grafico_volume_historico(data_inicio, data_fim)

    col3, col4 = st.columns(2)
    with col3:
        _grafico_habito_hora(data_inicio, data_fim)
    with col4:
        _grafico_habito_dia_semana(data_inicio, data_fim)


def render() -> None:
    ui.titulo_pagina("estatísticas")

    fonte = st.radio(
        "Fonte", ["Meus dados (Diário)", "Segundo o Spotify"],
        horizontal=True, key="stats_fonte",
    )
    data_inicio, data_fim, rotulo = _periodo_selecionado()
    st.divider()

    if fonte == "Meus dados (Diário)":
        _secao_diario(data_inicio, data_fim, rotulo)
    else:
        _secao_spotify(data_inicio, data_fim, rotulo)


render()
