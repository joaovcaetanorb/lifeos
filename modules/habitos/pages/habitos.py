"""Hábitos: check-in diário, gerenciamento da lista e progresso de cada um."""

from datetime import date

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import calculations as calc
import database
import models
import relatorio
import ui
import utils

st.set_page_config(page_title="Hábitos | Hábitos", page_icon="✅", layout="wide")
database.inicializar_banco()
ui.aplicar_tema()

CHART_LAYOUT = dict(
    margin=dict(l=10, r=10, t=40, b=10),
    height=320,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="JetBrains Mono, monospace", color=utils.COR_TEXTO_MUTED),
)


def _grid_style(fig: go.Figure) -> go.Figure:
    fig.update_xaxes(showgrid=True, gridcolor=utils.COR_HAIRLINE, zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)
    fig.update_layout(**CHART_LAYOUT)
    return fig


def _resumo(registros, habitos) -> None:
    resumo = calc.resumo_geral(registros=registros, habitos=habitos)
    if resumo["ativos"] == 0:
        st.caption("Nenhum hábito cadastrado ainda.")
        return
    media_txt = f"{resumo['percentual_medio']:.0f}%" if resumo["percentual_medio"] is not None else "—"
    st.caption(f"{resumo['ativos']} hábito(s) ativo(s) · cumprimento médio (30 dias): {media_txt}")


def _formulario_novo_habito() -> None:
    with st.expander("+ novo hábito"):
        with st.form("form_novo_habito", clear_on_submit=True):
            nome = st.text_input("Nome", placeholder="Ex.: Exercitar")
            if st.form_submit_button("criar hábito", use_container_width=True):
                if not nome.strip():
                    st.warning("Informe um nome para o hábito.")
                else:
                    models.inserir_habito(nome.strip())
                    st.success(f"Hábito '{nome}' criado.")
                    st.rerun()


def _toggle_hoje(habito_id: int, hoje_iso: str) -> None:
    if st.session_state[f"chk_hoje_{habito_id}"]:
        models.marcar_dia(habito_id, hoje_iso)
    else:
        models.desmarcar_dia(habito_id, hoje_iso)


def _secao_editar(habito: dict) -> None:
    hid = int(habito["id"])
    with st.form(f"form_editar_{hid}"):
        nome = st.text_input("Nome", value=habito["nome"])
        ativo = st.checkbox("ativo", value=bool(habito["ativo"]))
        if st.form_submit_button("salvar alterações"):
            models.atualizar_habito(hid, nome.strip(), ativo)
            st.success("Hábito atualizado.")
            st.rerun()

    st.divider()
    confirmar = st.checkbox("confirmar exclusão deste hábito", key=f"confirmar_exclusao_{hid}")
    if st.button("excluir hábito", key=f"del_habito_{hid}", disabled=not confirmar):
        models.excluir_habito(hid)
        st.success("Hábito excluído.")
        st.rerun()


def _card_habito(habito: dict, hoje: date, registros) -> None:
    hid = int(habito["id"])
    hoje_iso = hoje.isoformat()
    resumo = calc.resumo_habito(hid, hoje, registros)

    with st.container(border=True):
        col_chk, col_main = st.columns([1, 5])
        with col_chk:
            st.checkbox(
                "feito hoje", value=resumo["feito_hoje"], key=f"chk_hoje_{hid}",
                on_change=_toggle_hoje, args=(hid, hoje_iso), label_visibility="collapsed",
            )
        with col_main:
            st.markdown(f"**{habito['nome']}**")
            st.caption(f"streak atual: {resumo['streak']} dia(s)")

        st.progress(
            resumo["percentual_30d"] / 100,
            text=f"{resumo['percentual_30d']:.0f}% dos últimos 30 dias",
        )

        with st.expander("editar / excluir"):
            _secao_editar(habito)


def _grafico_heatmap_diario(hoje: date, registros, habitos) -> None:
    st.markdown("**Calendário de cumprimento (últimos 6 meses)**")
    df = calc.heatmap_diario(182, hoje, registros, habitos)
    if df.empty:
        st.caption("Sem dados suficientes ainda.")
        return

    df = df.copy()
    df["dia_semana"] = df["data"].dt.dayofweek
    primeiro_dia_semana = int(df["data"].min().dayofweek)
    df["semana"] = ((df["data"] - df["data"].min()).dt.days + primeiro_dia_semana) // 7

    dias_semana_labels = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
    pivot = df.pivot(index="dia_semana", columns="semana", values="percentual").reindex(index=range(7))
    pivot_nomes = (
        df.pivot(index="dia_semana", columns="semana", values="nomes")
        .reindex(index=range(7))
        .fillna("")
        .map(lambda n: n if n else "nenhum hábito cumprido")
    )

    # Rótulo de mês só na primeira semana em que ele aparece (igual ao
    # calendário do GitHub) — repetir em toda semana poluiria o eixo.
    nomes_mes = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    primeiro_dia_por_semana = df.groupby("semana")["data"].min().sort_index()
    tick_vals, tick_texts = [], []
    mes_anterior = None
    for semana, primeiro_dia in primeiro_dia_por_semana.items():
        mes_atual = (primeiro_dia.year, primeiro_dia.month)
        if mes_atual != mes_anterior:
            tick_vals.append(semana)
            tick_texts.append(nomes_mes[primeiro_dia.month - 1])
            mes_anterior = mes_atual

    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        y=dias_semana_labels,
        colorscale=[[0, utils.COR_HAIRLINE], [1, utils.COR_ACENTO]],
        showscale=False,
        xgap=3, ygap=3,
        customdata=pivot_nomes.values,
        hovertemplate="%{z:.0f}%<br>%{customdata}<extra></extra>",
        zmin=0, zmax=100,
    ))
    fig.update_xaxes(tickmode="array", tickvals=tick_vals, ticktext=tick_texts, showgrid=False)
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10), height=220,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="JetBrains Mono, monospace", color=utils.COR_TEXTO_MUTED),
    )
    st.plotly_chart(fig, use_container_width=True)


def _periodo_selecionado() -> tuple[str, str, str]:
    """Retorna (data_inicio_iso, data_fim_iso, rótulo pra exibição)."""
    hoje = date.today()
    atalho = st.radio(
        "Período", ["Este mês", "Este ano", "Todos os tempos", "Personalizado"],
        horizontal=True, label_visibility="collapsed", key="habitos_stats_periodo",
    )

    if atalho == "Este mês":
        inicio = hoje.replace(day=1)
        return inicio.isoformat(), hoje.isoformat(), "este mês"
    if atalho == "Este ano":
        inicio = date(hoje.year, 1, 1)
        return inicio.isoformat(), hoje.isoformat(), str(hoje.year)
    if atalho == "Todos os tempos":
        intervalo = models.intervalo_datas_registros()
        if intervalo is None:
            return hoje.isoformat(), hoje.isoformat(), "todos os tempos"
        return intervalo[0], intervalo[1], "todos os tempos"

    c1, c2 = st.columns(2)
    inicio = c1.date_input("De", value=date(hoje.year, 1, 1), format="DD/MM/YYYY", key="habitos_stats_data_inicio")
    fim = c2.date_input("Até", value=hoje, format="DD/MM/YYYY", key="habitos_stats_data_fim")
    return inicio.isoformat(), fim.isoformat(), "período personalizado"


def _grafico_progresso_habito(data_inicio: str, data_fim: str, registros, habitos) -> None:
    st.markdown("**% cumprido por hábito**")
    df = calc.progresso_por_habito_periodo(data_inicio, data_fim, registros, habitos)
    if df.empty:
        st.caption("Nenhum hábito cadastrado ainda.")
        return
    fig = px.bar(
        df, x="percentual", y="nome", orientation="h",
        text=df["percentual"].map(lambda v: f"{v:.0f}%"),
    )
    fig.update_traces(marker_color=utils.COR_ACENTO, textposition="outside", cliponaxis=False)
    fig.update_layout(xaxis_title=None, yaxis_title=None, xaxis_range=[0, 100])
    st.plotly_chart(_grid_style(fig), use_container_width=True)


def _grafico_cumprimento_mensal(data_inicio: str, data_fim: str, registros, habitos) -> None:
    st.markdown("**Cumprimento por mês (todos os hábitos)**")
    df = calc.cumprimento_por_mes(data_inicio, data_fim, registros, habitos)
    if df.empty or df["percentual"].sum() == 0:
        st.caption("Sem dados suficientes ainda.")
        return
    fig = px.bar(df, x="mes_nome", y="percentual", text=df["percentual"].map(lambda v: f"{v:.0f}%"))
    fig.update_traces(marker_color=utils.COR_REALIZADO, textposition="outside", cliponaxis=False)
    fig.update_layout(xaxis_title=None, yaxis_title=None, yaxis_range=[0, 100])
    st.plotly_chart(_grid_style(fig), use_container_width=True)


def _secao_analises(registros, habitos) -> None:
    ui.eyebrow("análises")
    st.subheader("Progresso e evolução")
    with st.expander("ver gráficos"):
        st.caption("Calendário sempre mostra os últimos 6 meses — o filtro abaixo vale pros gráficos seguintes.")
        _grafico_heatmap_diario(date.today(), registros, habitos)
        st.divider()
        data_inicio, data_fim, _ = _periodo_selecionado()
        col_a, col_b = st.columns(2)
        with col_a:
            _grafico_progresso_habito(data_inicio, data_fim, registros, habitos)
        with col_b:
            _grafico_cumprimento_mensal(data_inicio, data_fim, registros, habitos)


def _secao_relatorio() -> None:
    ui.eyebrow("fechamento")
    st.subheader("Relatório em PDF")
    st.caption(
        "Gera um PDF com o resumo do período, os gráficos, o detalhe por hábito e a nota "
        "final — bom pra guardar ou olhar depois de um tempo."
    )

    opcoes_dias = {7: "últimos 7 dias", 30: "últimos 30 dias", 90: "últimos 90 dias"}
    dias = st.selectbox(
        "Período do relatório", list(opcoes_dias.keys()),
        format_func=lambda d: opcoes_dias[d], index=1, key="dias_relatorio_habitos",
    )

    if st.button("gerar relatório", key="gerar_relatorio_habitos"):
        pdf_bytes = relatorio.gerar_pdf_relatorio(dias)
        st.session_state["pdf_relatorio_habitos"] = pdf_bytes
        st.session_state["pdf_relatorio_habitos_dias"] = dias

    if (
        st.session_state.get("pdf_relatorio_habitos")
        and st.session_state.get("pdf_relatorio_habitos_dias") == dias
    ):
        st.download_button(
            "baixar PDF",
            data=st.session_state["pdf_relatorio_habitos"],
            file_name=f"relatorio_habitos_{dias}d.pdf",
            mime="application/pdf",
            key="baixar_relatorio_habitos",
        )


def render() -> None:
    hoje = date.today()
    habitos = calc.buscar_habitos()
    registros = calc.buscar_registros_todos()

    ui.titulo_pagina("hábitos")
    _resumo(registros, habitos)

    st.divider()
    _formulario_novo_habito()

    st.divider()
    ui.eyebrow("check-in de hoje")
    if habitos.empty:
        st.caption("Nenhum hábito cadastrado ainda.")
    else:
        for _, habito in habitos.iterrows():
            _card_habito(dict(habito), hoje, registros)

    st.divider()
    _secao_analises(registros, habitos)

    st.divider()
    _secao_relatorio()


render()
