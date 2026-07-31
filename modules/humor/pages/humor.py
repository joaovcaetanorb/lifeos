"""Humor: registro rápido (nota + tags + nota livre) e histórico/gráficos."""

import calendar
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import calculations as calc
import database
import models
import relatorio
import ui
import utils

st.set_page_config(page_title="Humor | Humor", page_icon="🙂", layout="wide")
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


def _resumo() -> None:
    resumo = calc.resumo_geral()
    if resumo["total_registros"] == 0:
        st.caption("Nenhum registro ainda.")
        return
    media_7d_txt = f"{resumo['nota_media_7d']:.1f}" if resumo["nota_media_7d"] is not None else "—"
    st.caption(
        f"{resumo['total_registros']} registro(s) · nota média geral {resumo['nota_media_geral']:.1f} "
        f"· últimos 7 dias {media_7d_txt}"
    )


def _formulario_novo_registro() -> None:
    with st.expander("+ novo registro", expanded=True):
        with st.form("form_novo_registro", clear_on_submit=True):
            c1, c2 = st.columns(2)
            data_registro = c1.date_input("Data", value=date.today(), format="DD/MM/YYYY")
            hora_registro = c2.text_input("Hora", value=utils.agora_hora(), help="Formato HH:MM")

            nota = st.slider("Nota", min_value=1, max_value=10, value=6)
            tags = st.multiselect("Tags", utils.TAGS_HUMOR)
            nota_livre = st.text_area("Nota livre (opcional)", placeholder="O que aconteceu, se quiser registrar...")

            if st.form_submit_button("registrar", use_container_width=True):
                models.inserir_registro(
                    data_registro.isoformat(), hora_registro.strip(), nota,
                    utils.tags_para_texto(tags), nota_livre.strip(),
                )
                st.success("Registro salvo.")
                st.rerun()


def _popover_registro(registro: dict) -> None:
    registro_id = int(registro["id"])
    with st.popover("✎"):
        with st.form(f"form_editar_registro_{registro_id}"):
            c1, c2 = st.columns(2)
            data_val = c1.date_input(
                "Data", value=date.fromisoformat(registro["data"]), format="DD/MM/YYYY",
                key=f"data_{registro_id}",
            )
            hora_val = c2.text_input("Hora", value=registro["hora"], key=f"hora_{registro_id}")
            nota_val = st.slider(
                "Nota", min_value=1, max_value=10, value=int(registro["nota"]), key=f"nota_{registro_id}",
            )
            tags_val = st.multiselect(
                "Tags", utils.TAGS_HUMOR, default=utils.texto_para_tags(registro["tags"]), key=f"tags_{registro_id}",
            )
            nota_livre_val = st.text_area("Nota livre", value=registro["nota_livre"], key=f"livre_{registro_id}")

            c3, c4 = st.columns(2)
            salvar = c3.form_submit_button("salvar")
            excluir = c4.form_submit_button("excluir")

        if salvar:
            models.atualizar_registro(
                registro_id, data_val.isoformat(), hora_val.strip(), nota_val,
                utils.tags_para_texto(tags_val), nota_livre_val.strip(),
            )
            st.rerun()
        if excluir:
            models.excluir_registro(registro_id)
            st.rerun()


def _linha_registro(registro: dict) -> None:
    col_texto, col_acao = st.columns([8, 1])
    with col_texto:
        tags = utils.texto_para_tags(registro["tags"])
        tags_txt = " ".join(f":{utils.badge_cor_tag(t)}-badge[{t}]" for t in tags) or "sem tags"
        st.markdown(f"**{registro['nota']}/10** · {tags_txt}")
        st.caption(f"{utils.formatar_data_br(registro['data'])} {registro['hora']}".strip())
        if registro["nota_livre"]:
            st.caption(registro["nota_livre"])
    with col_acao:
        _popover_registro(registro)


def _secao_historico() -> None:
    ui.eyebrow("histórico")
    st.subheader("Registros")
    registros = models.listar_registros()
    if registros.empty:
        st.caption("Nenhum registro ainda.")
        return
    for _, registro in registros.head(30).iterrows():
        _linha_registro(dict(registro))
        st.divider()


def _grafico_heatmap_diario(hoje: date) -> None:
    st.markdown("**Calendário de humor (últimos 6 meses)**")
    df = calc.evolucao_diaria(182, hoje)[["data", "nota"]]
    if df["nota"].dropna().empty:
        st.caption("Sem dados suficientes ainda.")
        return

    df = df.copy()
    df["dia_semana"] = df["data"].dt.dayofweek
    primeiro_dia_semana = int(df["data"].min().dayofweek)
    df["semana"] = ((df["data"] - df["data"].min()).dt.days + primeiro_dia_semana) // 7

    dias_semana_labels = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
    pivot = df.pivot(index="dia_semana", columns="semana", values="nota").reindex(index=range(7))

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
        colorscale=[[0, utils.COR_TAG_NEGATIVO], [0.5, utils.COR_NEUTRO], [1, utils.COR_TAG_POSITIVO]],
        showscale=False,
        xgap=3, ygap=3,
        hovertemplate="%{z:.1f}/10<extra></extra>",
        zmin=1, zmax=10,
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
        horizontal=True, label_visibility="collapsed", key="humor_stats_periodo",
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
    inicio = c1.date_input("De", value=date(hoje.year, 1, 1), format="DD/MM/YYYY", key="humor_stats_data_inicio")
    fim = c2.date_input("Até", value=hoje, format="DD/MM/YYYY", key="humor_stats_data_fim")
    return inicio.isoformat(), fim.isoformat(), "período personalizado"


def _range_eixo_dias(dias: pd.Series, margem_minima: pd.Timedelta = pd.Timedelta(days=1)) -> list:
    """Range manual do eixo X (em dias) com margem mínima — o autorange do
    Plotly colapsa pra uma janela de frações de milissegundo quando todos
    os pontos caem no mesmo dia, o que faz o eixo mostrar horários tipo
    '23:59:59.9995' em vez da data."""
    minimo, maximo = dias.min(), dias.max()
    margem = max(margem_minima, (maximo - minimo) * 0.08)
    return [minimo - margem, maximo + margem]


def _grafico_hora_do_dia(data_inicio: str, data_fim: str) -> None:
    """Um ponto por registro, dia no eixo X e horário no eixo Y — ao
    contrário de um eixo de tempo contínuo, registros múltiplos no mesmo
    dia caem em alturas diferentes em vez de colar um no outro, então dá
    pra ver a que hora cada um foi feito sem precisar passar o mouse."""
    st.markdown("**Humor por horário do dia**")
    df = calc.registros_periodo(data_inicio, data_fim)
    if df.empty:
        st.caption("Nenhum registro nesse período.")
        return

    df = df.copy()
    df["hora_decimal"] = df["datetime"].dt.hour + df["datetime"].dt.minute / 60
    dias = df["datetime"].dt.normalize()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dias, y=df["hora_decimal"], mode="markers",
        marker=dict(
            size=11, color=df["nota"], cmin=1, cmax=10,
            colorscale=[[0, utils.COR_TAG_NEGATIVO], [0.5, utils.COR_NEUTRO], [1, utils.COR_TAG_POSITIVO]],
            line=dict(width=1, color=utils.COR_FUNDO),
        ),
        customdata=pd.concat([df["datetime"].dt.strftime("%H:%M"), df["nota"]], axis=1),
        hovertemplate="%{x|%d/%m} %{customdata[0]} — %{customdata[1]}/10<extra></extra>",
    ))
    range_x = _range_eixo_dias(dias)
    largura_dias = (range_x[1] - range_x[0]).days
    fig.update_xaxes(
        range=range_x, tickformat="%d/%m",
        dtick=86400000 if largura_dias <= 10 else None,
    )
    fig.update_yaxes(range=[24, 0], tickvals=[0, 6, 12, 18, 24], ticktext=["00h", "06h", "12h", "18h", "24h"])
    fig.update_layout(xaxis_title=None, yaxis_title=None)
    st.plotly_chart(_grid_style(fig), use_container_width=True)
    st.caption("vermelho = nota baixa · azul = nota alta")


def _meses_disponiveis() -> list[tuple[int, int]]:
    """(ano, mês) de cada mês entre o primeiro registro e hoje, mais
    recente primeiro — popula o seletor da visão \"Por mês\"."""
    hoje = date.today()
    intervalo = models.intervalo_datas_registros()
    inicio = date.fromisoformat(intervalo[0]) if intervalo else hoje

    meses = []
    ano, mes = inicio.year, inicio.month
    while (ano, mes) <= (hoje.year, hoje.month):
        meses.append((ano, mes))
        ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
    return list(reversed(meses))


def _grafico_calendario_mes(ano: int, mes: int) -> None:
    """Um retângulo por dia do mês — dias com mais de um registro são
    divididos em faixas horizontais (uma por registro, em ordem
    cronológica de cima pra baixo), então dá pra ver na hora quando o
    humor mudou dentro do mesmo dia, sem depender do hover."""
    primeiro_dia_semana, dias_no_mes = calendar.monthrange(ano, mes)
    data_inicio = date(ano, mes, 1).isoformat()
    data_fim = date(ano, mes, dias_no_mes).isoformat()
    df = calc.registros_periodo(data_inicio, data_fim)
    if df.empty:
        st.caption("Nenhum registro nesse mês.")
        return

    registros_por_dia = {
        dia: grupo.sort_values("datetime") for dia, grupo in df.groupby(df["datetime"].dt.day)
    }
    dias_semana_labels = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
    n_semanas = (primeiro_dia_semana + dias_no_mes - 1) // 7 + 1

    fig = go.Figure()
    hover_x, hover_y, hover_texto = [], [], []
    for dia in range(1, dias_no_mes + 1):
        posicao = primeiro_dia_semana + dia - 1
        semana, coluna = posicao // 7, posicao % 7
        registros_dia = registros_por_dia.get(dia)

        if registros_dia is None or registros_dia.empty:
            fig.add_shape(
                type="rect", x0=coluna, x1=coluna + 1, y0=semana, y1=semana + 1,
                fillcolor=utils.COR_FUNDO_ALT, line=dict(width=1, color=utils.COR_HAIRLINE),
            )
            cor_numero = utils.COR_TEXTO_MUTED
        else:
            n = len(registros_dia)
            for i, (_, registro) in enumerate(registros_dia.iterrows()):
                y0, y1 = semana + i / n, semana + (i + 1) / n
                fig.add_shape(
                    type="rect", x0=coluna, x1=coluna + 1, y0=y0, y1=y1,
                    fillcolor=utils.cor_nota(registro["nota"]), line=dict(width=1, color=utils.COR_FUNDO),
                )
                hover_x.append(coluna + 0.5)
                hover_y.append((y0 + y1) / 2)
                tags_txt = ", ".join(utils.texto_para_tags(registro["tags"])) or "sem tags"
                hover_texto.append(
                    f"{registro['datetime'].strftime('%H:%M')} — {registro['nota']}/10<br>{tags_txt}"
                )
            cor_numero = utils.COR_TEXTO

        fig.add_annotation(
            x=coluna + 0.06, y=semana + 0.12, text=str(dia), showarrow=False,
            font=dict(size=9, color=cor_numero), xanchor="left", yanchor="top",
        )

    if hover_x:
        fig.add_trace(go.Scatter(
            x=hover_x, y=hover_y, mode="markers",
            marker=dict(size=28, color="rgba(0,0,0,0)"),
            text=hover_texto, hovertemplate="%{text}<extra></extra>",
            showlegend=False,
        ))

    fig.update_xaxes(
        range=[0, 7], tickmode="array", tickvals=[i + 0.5 for i in range(7)], ticktext=dias_semana_labels,
        showgrid=False, zeroline=False,
    )
    fig.update_yaxes(range=[n_semanas, 0], showgrid=False, zeroline=False, showticklabels=False)
    fig.update_layout(**{**CHART_LAYOUT, "height": 110 * n_semanas + 60})
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "vermelho = nota baixa · azul = nota alta · dias com mais de um registro aparecem "
        "divididos em faixas (a de cima é o registro mais cedo)"
    )


def _grafico_tags(data_inicio: str, data_fim: str) -> None:
    st.markdown("**Tags mais frequentes**")
    df = calc.tags_mais_frequentes(data_inicio, data_fim)
    if df.empty:
        st.caption("Nenhuma tag registrada nesse período.")
        return
    df = df.sort_values("total")
    cores = [utils.cor_tag(tag) for tag in df["tag"]]
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["total"], y=df["tag"], orientation="h", marker_color=cores))
    fig.update_layout(xaxis_title=None, yaxis_title=None)
    st.plotly_chart(_grid_style(fig), use_container_width=True)
    st.caption("azul = sentimento positivo · vermelho = negativo")


def _secao_analises() -> None:
    ui.eyebrow("análises")
    st.subheader("Evolução e padrões")
    with st.expander("ver gráficos"):
        modo_calendario = st.radio(
            "Calendário", ["Últimos 6 meses", "Por mês"],
            horizontal=True, label_visibility="collapsed", key="humor_modo_calendario",
        )
        if modo_calendario == "Últimos 6 meses":
            _grafico_heatmap_diario(date.today())
            st.caption(
                "Cada célula é a média do dia — se o humor mudou bastante nesse dia, "
                "troque pra \"Por mês\" pra ver cada registro separado."
            )
        else:
            meses = _meses_disponiveis()
            ano, mes = st.selectbox(
                "Mês", meses, format_func=lambda m: f"{utils.NOMES_MESES[m[1] - 1]} de {m[0]}",
                key="humor_mes_selecionado",
            )
            st.markdown(f"**{utils.NOMES_MESES[mes - 1]} de {ano}**")
            _grafico_calendario_mes(ano, mes)

        st.divider()
        st.caption("O filtro de período abaixo vale pros dois gráficos seguintes.")
        data_inicio, data_fim, _ = _periodo_selecionado()
        col_a, col_b = st.columns(2)
        with col_a:
            _grafico_hora_do_dia(data_inicio, data_fim)
        with col_b:
            _grafico_tags(data_inicio, data_fim)


def _secao_relatorio() -> None:
    ui.eyebrow("fechamento")
    st.subheader("Relatório em PDF")
    st.caption(
        "Gera um PDF com o resumo do período, os gráficos, o histórico e a nota final — "
        "bom pra guardar ou olhar depois de um tempo."
    )

    opcoes_dias = {7: "últimos 7 dias", 30: "últimos 30 dias", 90: "últimos 90 dias"}
    dias = st.selectbox(
        "Período do relatório", list(opcoes_dias.keys()),
        format_func=lambda d: opcoes_dias[d], index=1, key="dias_relatorio_humor",
    )

    if st.button("gerar relatório", key="gerar_relatorio_humor"):
        pdf_bytes = relatorio.gerar_pdf_relatorio(dias)
        st.session_state["pdf_relatorio_humor"] = pdf_bytes
        st.session_state["pdf_relatorio_humor_dias"] = dias

    if (
        st.session_state.get("pdf_relatorio_humor")
        and st.session_state.get("pdf_relatorio_humor_dias") == dias
    ):
        st.download_button(
            "baixar PDF",
            data=st.session_state["pdf_relatorio_humor"],
            file_name=f"relatorio_humor_{dias}d.pdf",
            mime="application/pdf",
            key="baixar_relatorio_humor",
        )


def render() -> None:
    ui.titulo_pagina("humor")
    _resumo()

    st.divider()
    _formulario_novo_registro()

    st.divider()
    _secao_analises()

    st.divider()
    _secao_historico()

    st.divider()
    _secao_relatorio()


render()
