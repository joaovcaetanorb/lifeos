"""Analytics: tendências cross-module, perguntas via IA, sugestões automáticas."""

from datetime import date

import plotly.graph_objects as go
import streamlit as st

import calculations as calc
import database
import groq_client
import models
import ui
import utils

st.set_page_config(page_title="Analytics | Analytics", page_icon="📈", layout="wide")
database.inicializar_banco()
ui.aplicar_tema()
ui.mostrar_toast_pendente()

CHART_LAYOUT = dict(
    margin=dict(l=10, r=10, t=40, b=10),
    height=300,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="JetBrains Mono, monospace", color=utils.COR_TEXTO_MUTED),
)


def _grid_style(fig: go.Figure) -> go.Figure:
    fig.update_xaxes(showgrid=True, gridcolor=utils.COR_HAIRLINE, zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)
    fig.update_layout(**CHART_LAYOUT)
    return fig


def _periodo_selecionado() -> tuple[str, str, str]:
    hoje = date.today()
    atalho = st.radio(
        "Período", ["Este mês", "Este ano", "Todos os tempos", "Personalizado"],
        horizontal=True, label_visibility="collapsed", key="analytics_periodo",
    )

    if atalho == "Este mês":
        inicio = hoje.replace(day=1)
        return inicio.isoformat(), hoje.isoformat(), "este mês"
    if atalho == "Este ano":
        inicio = date(hoje.year, 1, 1)
        return inicio.isoformat(), hoje.isoformat(), str(hoje.year)
    if atalho == "Todos os tempos":
        inicio = date(hoje.year - 3, 1, 1)
        return inicio.isoformat(), hoje.isoformat(), "todos os tempos"

    c1, c2 = st.columns(2)
    inicio = c1.date_input("De", value=date(hoje.year, 1, 1), format="DD/MM/YYYY", key="analytics_data_inicio")
    fim = c2.date_input("Até", value=hoje, format="DD/MM/YYYY", key="analytics_data_fim")
    return inicio.isoformat(), fim.isoformat(), "período personalizado"


def _grafico_financeiro(data_inicio: str, data_fim: str) -> None:
    st.markdown("**Gastos por mês**")
    df = calc.financeiro_por_mes(data_inicio, data_fim)
    if df["valor"].sum() == 0:
        st.caption("Sem dados suficientes ainda.")
        return
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["mes_nome"], y=df["valor"], marker_color=utils.COR_REALIZADO))
    st.plotly_chart(_grid_style(fig), use_container_width=True)


def _grafico_habitos(data_inicio: str, data_fim: str) -> None:
    st.markdown("**Cumprimento de hábitos por mês**")
    df = calc.habitos_por_mes(data_inicio, data_fim)
    if df["percentual"].sum() == 0:
        st.caption("Sem dados suficientes ainda.")
        return
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["mes_nome"], y=df["percentual"], marker_color=utils.COR_ACENTO))
    fig.update_layout(yaxis_range=[0, 100])
    st.plotly_chart(_grid_style(fig), use_container_width=True)


def _grafico_humor(data_inicio: str, data_fim: str) -> None:
    st.markdown("**Humor médio por mês**")
    df = calc.humor_por_mes(data_inicio, data_fim)
    if df["nota_media"].dropna().empty:
        st.caption("Sem dados suficientes ainda.")
        return
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["mes_nome"], y=df["nota_media"], mode="lines+markers",
        line=dict(color=utils.COR_ACENTO, width=2), marker=dict(size=8),
    ))
    fig.update_layout(yaxis_range=[0, 10])
    st.plotly_chart(_grid_style(fig), use_container_width=True)


def _grafico_projetos() -> None:
    st.markdown("**Progresso dos projetos**")
    df = calc.projetos_lista()
    df = df[df["progresso"].notna()]
    if df.empty:
        st.caption("Nenhum projeto com orçamento definido ainda.")
        return
    df = df.sort_values("progresso")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["progresso"], y=df["nome"], orientation="h", marker_color=utils.COR_ACENTO))
    fig.update_layout(xaxis_range=[0, 100])
    st.plotly_chart(_grid_style(fig), use_container_width=True)


def _secao_graficos(data_inicio: str, data_fim: str) -> None:
    ui.eyebrow("gráficos")
    st.subheader("Tendências")
    col_a, col_b = st.columns(2)
    with col_a:
        _grafico_financeiro(data_inicio, data_fim)
        _grafico_humor(data_inicio, data_fim)
    with col_b:
        _grafico_habitos(data_inicio, data_fim)
        _grafico_projetos()


def _secao_perguntas(data_inicio: str, data_fim: str) -> None:
    ui.eyebrow("perguntas")
    st.subheader("Pergunte aos seus dados")

    if not groq_client.disponivel():
        st.caption(
            "Configure GROQ_API_KEY em modules/analytics/.streamlit/secrets.toml pra "
            "ativar essa seção. Sem ela, só os gráficos ficam disponíveis."
        )
        return

    st.caption("Escolha uma pergunta pronta ou escreva a sua — a resposta usa só os números agregados dos seus módulos.")
    cols = st.columns(3)
    pergunta_clicada = None
    for i, pergunta in enumerate(utils.PERGUNTAS_PREDEFINIDAS):
        with cols[i % 3]:
            if st.button(pergunta, key=f"pergunta_predef_{i}", use_container_width=True):
                pergunta_clicada = pergunta

    with st.form("form_pergunta_livre"):
        pergunta_livre = st.text_input("Ou pergunte o que quiser", placeholder="Ex.: Em que dias da semana eu gasto mais?")
        enviar = st.form_submit_button("perguntar")

    pergunta_final = pergunta_clicada or (pergunta_livre.strip() if enviar and pergunta_livre.strip() else None)

    if pergunta_final:
        cache = models.obter_resposta_cacheada(pergunta_final)
        if cache is not None:
            resposta = cache["resposta"]
        else:
            with st.spinner("gerando resposta..."):
                contexto = calc.contexto_geral(data_inicio, data_fim)
                resposta = groq_client.responder_pergunta(pergunta_final, contexto)
            if resposta:
                models.salvar_resposta(pergunta_final, resposta)
        st.session_state["analytics_ultima_pergunta"] = pergunta_final
        st.session_state["analytics_ultima_resposta"] = resposta

    if st.session_state.get("analytics_ultima_pergunta"):
        st.divider()
        st.markdown(f"**{st.session_state['analytics_ultima_pergunta']}**")
        resposta = st.session_state.get("analytics_ultima_resposta")
        if resposta:
            st.info(resposta)
        else:
            st.warning("Não consegui gerar uma resposta agora. Tente de novo em instantes.")


def _secao_sugestoes(data_inicio: str, data_fim: str) -> None:
    ui.eyebrow("sugestões")
    st.subheader("O que a IA notou")

    if not groq_client.disponivel():
        st.caption("Disponível assim que a chave do Groq for configurada.")
        return

    sugestao = models.obter_sugestao_mais_recente()
    desatualizada = sugestao is None or utils.horas_desde(sugestao["gerado_em"]) >= 24

    if desatualizada:
        with st.spinner("Gerando sugestões..."):
            contexto = calc.contexto_geral(data_inicio, data_fim)
            texto = groq_client.gerar_sugestoes(contexto)
        if texto:
            models.salvar_sugestao(texto)
            sugestao = models.obter_sugestao_mais_recente()

    if sugestao:
        st.markdown(sugestao["texto"])
        st.caption(f"gerado em {sugestao['gerado_em']} UTC · atualiza sozinho a cada ~24h")
    else:
        st.caption("Ainda sem dados suficientes pra gerar sugestões.")

    if st.button("atualizar agora", key="atualizar_sugestoes"):
        with st.spinner("Gerando sugestões..."):
            contexto = calc.contexto_geral(data_inicio, data_fim)
            texto = groq_client.gerar_sugestoes(contexto)
        if texto:
            models.salvar_sugestao(texto)
            ui.marcar_toast("Sugestões atualizadas.")
            st.rerun()


_TITULOS_PAR = {
    "humor_habitos": "Humor × Hábitos",
    "humor_financeiro": "Humor × Financeiro",
    "humor_cultura": "Humor × Livros/Música",
}


def _descricao_comparacao(r: dict) -> str:
    return (
        f"Nos {r['label_a']} (n={r['n_a']} dias), a nota média de humor foi {r['media_a']}/10. "
        f"Nos {r['label_b']} (n={r['n_b']} dias), foi {r['media_b']}/10."
    )


def _cruzamento(r: dict) -> None:
    st.markdown(f"**{_TITULOS_PAR.get(r['par'], r['par'])}**")
    descricao = _descricao_comparacao(r)

    col_a, col_b = st.columns(2)
    col_a.metric(r["label_a"].capitalize(), f"{r['media_a']}/10", help=f"{r['n_a']} dias")
    col_b.metric(r["label_b"].capitalize(), f"{r['media_b']}/10", help=f"{r['n_b']} dias")

    if groq_client.disponivel():
        cache = models.obter_correlacao_cacheada(r["par"])
        desatualizado = cache is None or utils.horas_desde(cache["gerado_em"]) >= 24
        if desatualizado:
            with st.spinner("Gerando explicação..."):
                texto = groq_client.narrar_correlacao(descricao)
            if texto:
                models.salvar_correlacao(r["par"], texto)
                cache = models.obter_correlacao_cacheada(r["par"])
        if cache:
            st.caption(cache["texto"])


def _secao_correlacoes(data_inicio: str, data_fim: str) -> None:
    ui.eyebrow("cruzamentos")
    st.subheader("Isso se relaciona com seu humor?")
    st.caption(
        "Comparações reais (calculadas a partir dos seus dados, não \"achismo\" da IA) — "
        "só aparecem quando já há dias suficientes em cada grupo pra significar algo."
    )

    resultados = calc.correlacoes_humor(data_inicio, data_fim)
    if not resultados:
        st.caption(
            "Ainda não há dados suficientes pra cruzar hábitos, financeiro ou atividades "
            "culturais com o humor — continue registrando por mais algumas semanas."
        )
        return

    for r in resultados:
        _cruzamento(r)
        st.divider()


def render() -> None:
    ui.titulo_pagina("analytics")
    data_inicio, data_fim, _ = _periodo_selecionado()

    st.divider()
    _secao_graficos(data_inicio, data_fim)

    st.divider()
    _secao_perguntas(data_inicio, data_fim)

    st.divider()
    _secao_sugestoes(data_inicio, data_fim)

    st.divider()
    _secao_correlacoes(data_inicio, data_fim)


render()
