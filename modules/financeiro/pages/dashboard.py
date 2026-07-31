"""Tela principal: visão geral do mês + 'Dia do Pagamento' + configurações."""

from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import calculations as calc
import database
import models
import relatorio
import ui
import utils

st.set_page_config(page_title="Dashboard | Controle Financeiro", page_icon="💰", layout="wide")
database.inicializar_banco()
ui.aplicar_tema()
ui.mostrar_toast_pendente()

CHART_LAYOUT = dict(
    margin=dict(l=10, r=10, t=40, b=10),
    height=340,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="JetBrains Mono, monospace", color=utils.COR_TEXTO_MUTED),
)


def _grid_style(fig: go.Figure) -> go.Figure:
    fig.update_xaxes(showgrid=True, gridcolor=utils.COR_HAIRLINE, zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)
    fig.update_layout(**CHART_LAYOUT)
    return fig


def _secao_dia_pagamento(hoje: date) -> None:
    ui.eyebrow("caixa")
    st.subheader("Dia do pagamento")

    saldo = calc.saldo_disponivel_hoje(hoje)

    if not saldo["controle_ativo"]:
        data_controle = date.fromisoformat(saldo["inicio_controle"])
        st.info(
            f"Seu controle passa a valer a partir de **{data_controle.strftime('%d/%m/%Y')}** "
            f"(quando o pagamento cai de verdade). Até lá, considerando R$ 0 disponível — "
            f"os valores abaixo são só a projeção de quanto vai sobrar quando o pagamento chegar."
        )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Dinheiro livre no mês", utils.formatar_moeda(saldo["dinheiro_livre"]))
    col2.metric("Saldo restante hoje", utils.formatar_moeda(saldo["saldo_restante"]))
    col3.metric("Pode gastar por dia", utils.formatar_moeda(saldo["por_dia"]))
    col4.metric("Pode gastar por semana", utils.formatar_moeda(saldo["por_semana"]))

    if saldo["dinheiro_livre"] > 0:
        percentual_restante = max(0.0, min(saldo["saldo_restante"] / saldo["dinheiro_livre"], 1.0))
        st.progress(percentual_restante)
        st.caption(f"{percentual_restante * 100:.0f}% do dinheiro livre do ciclo ainda disponível.")

    if saldo["receita_extra_ciclo"] > 0:
        st.caption(
            f"Inclui {utils.formatar_moeda(saldo['receita_extra_ciclo'])} de renda extra "
            f"recebida neste ciclo (lançada em Gastos)."
        )

    st.caption(
        f"Ciclo atual: de {saldo['inicio_ciclo'].strftime('%d/%m/%Y')} até o próximo pagamento "
        f"em {saldo['proximo_pagamento'].strftime('%d/%m/%Y')} — faltam **{saldo['dias_restantes']} dias**. "
        f"Contas fixas, fatura do cartão calculada e aporte de reserva já saem descontados."
    )

    with st.expander("Ver como esse valor foi calculado"):
        st.write(
            f"- Salário: {utils.formatar_moeda(saldo['salario'])}\n"
            f"- (−) Contas fixas: {utils.formatar_moeda(saldo['contas_fixas'])}\n"
            f"- (−) Fatura do cartão (calculada): {utils.formatar_moeda(saldo['fatura_cartao'])}\n"
            f"- (−) Aporte para reserva: {utils.formatar_moeda(saldo['aporte_reserva'])}\n"
            f"- **= Dinheiro livre no mês: {utils.formatar_moeda(saldo['dinheiro_livre'])}**\n"
            f"- (−) Já gasto desde o último pagamento ({saldo['inicio_ciclo'].strftime('%d/%m')}, fora VA e crédito): "
            f"{utils.formatar_moeda(saldo['gasto_impacta_livre'])}\n"
            f"- (+) Renda extra recebida no ciclo: {utils.formatar_moeda(saldo['receita_extra_ciclo'])}\n"
            f"- **= Saldo restante hoje: {utils.formatar_moeda(saldo['saldo_restante'])}**\n\n"
            f"Vale alimentação ({utils.formatar_moeda(saldo['vale_alimentacao'])}) é tratado à parte, "
            f"pois só cobre gastos pagos com VA.\n\n"
            f"Por que 'desde o último pagamento' e não 'desde o dia 1 do mês'? Porque seu ciclo "
            f"financeiro vai de pagamento a pagamento — se ele virar o mês civil antes do próximo "
            f"pagamento cair, os gastos continuam contando no mesmo ciclo."
        )

    st.markdown("**Vale alimentação**")
    va = calc.saldo_vale_alimentacao(calc.mes_referencia_atual(hoje))
    va1, va2, va3 = st.columns(3)
    va1.metric("VA do mês", utils.formatar_moeda(va["total"]))
    va2.metric("Já gasto com VA", utils.formatar_moeda(va["gasto"]))
    va3.metric("Saldo do VA", utils.formatar_moeda(va["saldo"]))
    if va["total"] > 0:
        percentual_va = max(0.0, min(va["saldo"] / va["total"], 1.0))
        st.progress(percentual_va)
        st.caption(f"{percentual_va * 100:.0f}% do VA ainda disponível.")
    if va["saldo"] < 0:
        st.warning(
            f"O VA já estourou em {utils.formatar_moeda(abs(va['saldo']))} — os gastos além do "
            f"vale acabam saindo do dinheiro livre normal, mesmo marcados como 'Vale alimentação'."
        )
    st.caption(
        "Some automaticamente todo gasto lançado com forma de pagamento "
        "'Vale alimentação' neste mês e desconta do valor do VA."
    )


def _secao_metricas_gerais(hoje: date) -> None:
    mes_ref = calc.mes_referencia_atual(hoje)
    config = models.get_config()
    fatura_atual = calc.fatura_do_mes(mes_ref)
    comprometido = calc.total_comprometido_cartao(hoje)
    gasto_mes = calc.gasto_total_mes(mes_ref)

    st.subheader(f"Resumo de {utils.nome_mes(mes_ref)}")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Salário", utils.formatar_moeda(config["salario"]))
    col2.metric("Vale alimentação", utils.formatar_moeda(config["vale_alimentacao"]))
    col3.metric("Gastos do mês", utils.formatar_moeda(gasto_mes))
    col4.metric("Fatura atual", utils.formatar_moeda(fatura_atual))
    col5.metric("Comprometido no cartão", utils.formatar_moeda(comprometido))


def _grafico_gastos_categoria(mes_ref: str) -> None:
    df = calc.gasto_por_categoria(mes_ref)
    st.markdown("**Gastos por categoria**")
    if df.empty:
        st.caption("Nenhum gasto lançado neste mês ainda.")
        return
    df = df.sort_values("valor")
    fig = px.bar(
        df, x="valor", y="categoria", orientation="h",
        color="categoria", color_discrete_map=utils.CATEGORIA_CORES,
        text=df["valor"].map(utils.formatar_moeda),
    )
    fig.update_traces(textposition="outside", cliponaxis=False)
    fig.update_layout(showlegend=False, xaxis_title=None, yaxis_title=None)
    st.plotly_chart(_grid_style(fig), use_container_width=True)


def _grafico_evolucao_mensal(hoje: date) -> None:
    df = calc.evolucao_mensal(6, hoje)
    st.markdown("**Evolução mensal de gastos**")
    fig = px.bar(df, x="mes_nome", y="valor", text=df["valor"].map(utils.formatar_moeda))
    fig.update_traces(marker_color=utils.COR_REALIZADO, textposition="outside", cliponaxis=False)
    fig.update_layout(xaxis_title=None, yaxis_title=None)
    st.plotly_chart(_grid_style(fig), use_container_width=True)


def _grafico_orcamento_realizado(mes_ref: str) -> None:
    df = calc.planejamento_vs_realizado(mes_ref)
    st.markdown("**Orçamento planejado x realizado**")
    if df.empty or (df["valor_planejado"].sum() == 0 and df["valor_realizado"].sum() == 0):
        st.caption("Cadastre um planejamento mensal para ver essa comparação.")
        return

    longo = df.melt(
        id_vars="categoria",
        value_vars=["valor_planejado", "valor_realizado"],
        var_name="tipo", value_name="valor",
    )
    longo["tipo"] = longo["tipo"].map({"valor_planejado": "Planejado", "valor_realizado": "Realizado"})

    fig = px.bar(
        longo, x="categoria", y="valor", color="tipo", barmode="group",
        color_discrete_map={"Planejado": utils.COR_PLANEJADO, "Realizado": utils.COR_REALIZADO},
    )
    fig.update_layout(xaxis_title=None, yaxis_title=None, legend_title=None)
    st.plotly_chart(_grid_style(fig), use_container_width=True)


def _grafico_evolucao_reserva() -> None:
    df = calc.evolucao_reserva()
    st.markdown("**Evolução da reserva**")
    if df.empty:
        st.caption("Nenhum movimento de reserva cadastrado ainda.")
        return

    config = models.get_config()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["data"], y=df["saldo_acumulado"], mode="lines+markers",
        line=dict(color=utils.COR_REALIZADO, width=2),
        marker=dict(size=8),
        hovertemplate="%{x}<br>Saldo: %{y:,.2f}<extra></extra>",
    ))
    if config["reserva_meta"] > 0:
        fig.add_hline(
            y=config["reserva_meta"], line_dash="dash", line_color=utils.COR_TEXTO_MUTED,
            annotation_text="Meta", annotation_position="top left",
        )
    fig.update_layout(xaxis_title=None, yaxis_title=None)
    st.plotly_chart(_grid_style(fig), use_container_width=True)


def _grafico_tendencia_diaria(hoje: date) -> None:
    st.markdown("**Tendência de gastos diários (últimos 60 dias)**")
    ui.explicacao(
        "Cada barra cinza é o quanto você gastou naquele dia (dias sem lançamento aparecem "
        "como zero — por isso o início do período costuma ficar baixo, antes de você começar "
        "a usar o app). A linha verde é a média móvel dos últimos 7 dias: em vez de pular a "
        "cada gasto pontual, ela sobe quando o ritmo geral de gastos acelera e desce quando "
        "desacelera — é o jeito de ver a tendência sem se distrair com um dia isolado."
    )
    df = calc.tendencia_diaria(60, hoje)
    if df.empty:
        st.caption("Sem dados suficientes ainda.")
        return

    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["data"], y=df["valor"], name="Gasto diário", marker_color=utils.COR_PLANEJADO))
    fig.add_trace(go.Scatter(
        x=df["data"], y=df["media_movel_7d"], name="Média móvel (7d)",
        line=dict(color=utils.COR_REALIZADO, width=2),
    ))
    fig.update_layout(xaxis_title=None, yaxis_title=None, legend_title=None)
    st.plotly_chart(_grid_style(fig), use_container_width=True)


def _sunburst_categoria_forma(hoje: date) -> None:
    st.markdown("**Categoria x forma de pagamento (últimos 6 meses)**")
    df = calc.gastos_periodo(180, hoje)
    if df.empty:
        st.caption("Sem dados suficientes ainda.")
        return

    agrupado = df.groupby(["categoria", "forma_pagamento"], as_index=False)["valor"].sum()
    fig = px.sunburst(
        agrupado, path=["categoria", "forma_pagamento"], values="valor",
        color="categoria", color_discrete_map=utils.CATEGORIA_CORES,
    )
    fig.update_layout(margin=dict(l=10, r=10, t=40, b=10), height=380,
                       paper_bgcolor="rgba(0,0,0,0)",
                       font=dict(family="JetBrains Mono, monospace", color=utils.COR_TEXTO_MUTED))
    st.plotly_chart(fig, use_container_width=True)


def _secao_analises_avancadas(hoje: date) -> None:
    ui.eyebrow("análises")
    st.subheader("Análises avançadas")
    with st.expander("ver gráficos"):
        _grafico_tendencia_diaria(hoje)
        _sunburst_categoria_forma(hoje)


def _secao_insights(hoje: date) -> None:
    insights = calc.gerar_insights(hoje)
    if not insights:
        return
    ui.eyebrow("leitura automática")
    st.subheader("Inteligência financeira")
    for texto in insights:
        st.info(texto)


def _secao_relatorio(hoje: date) -> None:
    ui.eyebrow("fechamento")
    st.subheader("Relatório mensal em PDF")
    st.caption(
        "Gera um PDF com o resumo do mês, os gráficos principais e a nota final — "
        "bom pra guardar ou olhar depois de fechar o mês."
    )

    opcoes = [calc.mes_referencia_atual(utils.somar_meses(hoje, -i)) for i in range(6)]
    rotulos = {m: utils.nome_mes(m) for m in opcoes}
    mes_relatorio = st.selectbox(
        "Mês do relatório", opcoes, format_func=lambda m: rotulos[m], key="mes_relatorio_pdf",
    )

    if st.button("gerar relatório"):
        pdf_bytes = relatorio.gerar_pdf_mensal(mes_relatorio)
        st.session_state["pdf_relatorio"] = pdf_bytes
        st.session_state["pdf_relatorio_mes"] = mes_relatorio

    if st.session_state.get("pdf_relatorio") and st.session_state.get("pdf_relatorio_mes") == mes_relatorio:
        st.download_button(
            "baixar PDF",
            data=st.session_state["pdf_relatorio"],
            file_name=f"relatorio_{mes_relatorio}.pdf",
            mime="application/pdf",
        )


def _secao_configuracoes() -> None:
    with st.expander("configurar salário, vale e contas fixas"):
        config = models.get_config()

        with st.form("form_config"):
            c1, c2 = st.columns(2)
            salario = c1.number_input("Salário", min_value=0.0, value=float(config["salario"]), step=50.0)
            vale = c2.number_input("Vale alimentação", min_value=0.0, value=float(config["vale_alimentacao"]), step=50.0)

            c3, c4 = st.columns(2)
            dia_util = c3.number_input(
                "Dia útil do pagamento", min_value=1, max_value=22,
                value=int(config["dia_util_pagamento"]), step=1,
                help="Ex.: 5 = 5º dia útil do mês",
            )
            aporte_padrao = c4.number_input(
                "Aporte mensal padrão para reserva", min_value=0.0,
                value=float(config["reserva_aporte_padrao"]), step=50.0,
            )

            meta_reserva = st.number_input(
                "Meta da reserva de emergência", min_value=0.0,
                value=float(config["reserva_meta"]), step=100.0,
            )

            if st.form_submit_button("Salvar configurações"):
                models.atualizar_config(salario, vale, int(dia_util), meta_reserva, aporte_padrao)
                ui.marcar_toast("Configurações atualizadas.")
                st.rerun()

        st.markdown("---")
        st.markdown("**Início do controle**")
        st.caption(
            "Use isso se você está começando a usar o app no meio de um ciclo e ainda não tem "
            "o dinheiro do pagamento anterior em mãos: o Dia do Pagamento mostra R$ 0 até essa "
            "data chegar, e passa a calcular normalmente a partir dela."
        )
        ativar_controle = st.checkbox(
            "Só considerar o Dia do Pagamento a partir de uma data específica",
            value=bool(config.get("inicio_controle")),
        )
        if ativar_controle:
            valor_atual = (
                date.fromisoformat(config["inicio_controle"])
                if config.get("inicio_controle")
                else utils.proximo_pagamento(date.today(), int(config["dia_util_pagamento"]))
            )
            nova_data = st.date_input("A partir de", value=valor_atual, format="DD/MM/YYYY")
            if st.button("salvar data de início"):
                models.definir_inicio_controle(nova_data.isoformat())
                ui.marcar_toast("Data de início do controle salva.")
                st.rerun()
        elif config.get("inicio_controle"):
            if st.button("desativar (voltar a calcular sempre)"):
                models.definir_inicio_controle("")
                ui.marcar_toast("Controle reativado imediatamente.")
                st.rerun()

        st.markdown("---")
        st.markdown("**Contas fixas**")
        contas = models.listar_contas_fixas()
        for _, conta in contas.iterrows():
            cc1, cc2, cc3 = st.columns([3, 2, 1])
            cc1.write(conta["descricao"])
            novo_valor = cc2.number_input(
                "Valor", min_value=0.0, value=float(conta["valor"]), step=10.0,
                key=f"conta_valor_{conta['id']}", label_visibility="collapsed",
            )
            if novo_valor != conta["valor"]:
                models.atualizar_conta_fixa(int(conta["id"]), conta["descricao"], novo_valor, True)
                ui.marcar_toast(f"Valor de '{conta['descricao']}' atualizado.")
                st.rerun()
            if cc3.button("Remover", key=f"conta_remover_{conta['id']}"):
                models.excluir_conta_fixa(int(conta["id"]))
                ui.marcar_toast(f"Conta fixa '{conta['descricao']}' removida.", icone="🗑️")
                st.rerun()

        with st.form("form_nova_conta", clear_on_submit=True):
            nc1, nc2, nc3 = st.columns([3, 2, 1])
            descricao_nova = nc1.text_input("Descrição", label_visibility="collapsed", placeholder="Nova conta fixa")
            valor_novo = nc2.number_input("Valor", min_value=0.0, step=10.0, label_visibility="collapsed")
            if nc3.form_submit_button("Adicionar") and descricao_nova:
                models.inserir_conta_fixa(descricao_nova, valor_novo)
                ui.marcar_toast(f"Conta fixa '{descricao_nova}' adicionada.")
                st.rerun()


def render() -> None:
    hoje = date.today()
    mes_ref = calc.mes_referencia_atual(hoje)

    ui.titulo_pagina("dashboard")

    _secao_dia_pagamento(hoje)
    st.divider()
    _secao_metricas_gerais(hoje)
    st.divider()

    col_a, col_b = st.columns(2)
    with col_a:
        _grafico_gastos_categoria(mes_ref)
        _grafico_orcamento_realizado(mes_ref)
    with col_b:
        _grafico_evolucao_mensal(hoje)
        _grafico_evolucao_reserva()

    st.divider()
    _secao_analises_avancadas(hoje)

    st.divider()
    _secao_insights(hoje)

    st.divider()
    _secao_relatorio(hoje)

    st.divider()
    _secao_configuracoes()


render()
