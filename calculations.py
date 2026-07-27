"""Regras de negócio financeiras. Nenhuma função aqui toca o banco direto
(sempre via models) nem desenha UI (isso fica nas páginas).

Convenção: "mes_referencia" é sempre string 'AAAA-MM'.
"""

from datetime import date, timedelta
import pandas as pd

import models
import utils

# Percentual da renda mensal (salário + VA) considerado limite saudável de
# comprometimento com cartão de crédito. É uma heurística comum de
# planejamento pessoal (não um limite bancário real) — ajustável aqui.
PERCENTUAL_LIMITE_RECOMENDADO_CARTAO = 0.30


# ---------------------------------------------------------------------------
# Cartão de crédito: faturas calculadas a partir das compras cadastradas
# ---------------------------------------------------------------------------

def _parcelas_da_compra(compra: pd.Series) -> list[tuple[str, float]]:
    """Quebra uma compra em (mes_referencia, valor_parcela) para cada parcela."""
    data_compra = date.fromisoformat(compra["data_compra"])
    valor_parcela = compra["valor_total"] / compra["parcelas"]
    resultado = []
    for k in range(compra["parcelas"]):
        data_parcela = utils.somar_meses(data_compra, k)
        resultado.append((utils.mes_referencia(data_parcela), valor_parcela))
    return resultado


def fatura_do_mes(mes_referencia: str | None = None) -> float:
    """Soma das parcelas (de todas as compras) que caem no mês informado."""
    mes_referencia = mes_referencia or utils.mes_referencia()
    compras = models.listar_compras_cartao()
    total = 0.0
    for _, compra in compras.iterrows():
        for mes_parcela, valor in _parcelas_da_compra(compra):
            if mes_parcela == mes_referencia:
                total += valor
    return round(total, 2)


def proximas_faturas(n_meses: int = 6, a_partir_de: date | None = None) -> pd.DataFrame:
    """Projeta a fatura dos próximos N meses (a partir do mês atual, inclusive)."""
    a_partir_de = a_partir_de or date.today()
    linhas = []
    for i in range(n_meses):
        mes_alvo = utils.mes_referencia(utils.somar_meses(a_partir_de, i))
        linhas.append({
            "mes_referencia": mes_alvo,
            "mes_nome": utils.nome_mes(mes_alvo),
            "valor": fatura_do_mes(mes_alvo),
        })
    return pd.DataFrame(linhas)


def total_comprometido_cartao(a_partir_de: date | None = None) -> float:
    """Soma de todas as parcelas futuras (mês atual em diante) ainda não vencidas."""
    a_partir_de = a_partir_de or date.today()
    mes_atual = utils.mes_referencia(a_partir_de)
    compras = models.listar_compras_cartao()
    total = 0.0
    for _, compra in compras.iterrows():
        for mes_parcela, valor in _parcelas_da_compra(compra):
            if mes_parcela >= mes_atual:
                total += valor
    return round(total, 2)


def percentual_limite_cartao(fatura_atual: float, renda_mensal: float) -> dict:
    """Calcula o quanto da fatura atual representa do limite recomendado."""
    limite_recomendado = renda_mensal * PERCENTUAL_LIMITE_RECOMENDADO_CARTAO
    percentual = (fatura_atual / limite_recomendado * 100) if limite_recomendado > 0 else 0.0

    if percentual >= 100:
        nivel, mensagem = "critico", f"Você ultrapassou o limite recomendado ({utils.formatar_moeda(limite_recomendado)})."
    elif percentual >= 80:
        nivel, mensagem = "alerta", f"Você já comprometeu {percentual:.0f}% do limite recomendado."
    elif percentual >= 50:
        nivel, mensagem = "atencao", f"Você comprometeu {percentual:.0f}% do limite recomendado."
    else:
        nivel, mensagem = "ok", f"Comprometimento saudável: {percentual:.0f}% do limite recomendado."

    return {
        "limite_recomendado": round(limite_recomendado, 2),
        "percentual": round(percentual, 1),
        "nivel": nivel,
        "mensagem": mensagem,
    }


def detalhe_compras_cartao(hoje: date | None = None) -> pd.DataFrame:
    """Lista as compras do cartão com parcela mensal e quantas já foram pagas."""
    hoje = hoje or date.today()
    mes_atual = utils.mes_referencia(hoje)
    compras = models.listar_compras_cartao()
    if compras.empty:
        return compras.assign(valor_parcela=[], parcelas_pagas=[], parcelas_restantes=[])

    linhas = []
    for _, compra in compras.iterrows():
        parcelas_meses = _parcelas_da_compra(compra)
        parcelas_pagas = sum(1 for mes_p, _ in parcelas_meses if mes_p < mes_atual)
        linha = compra.to_dict()
        linha["valor_parcela"] = round(compra["valor_total"] / compra["parcelas"], 2)
        linha["parcelas_pagas"] = parcelas_pagas
        linha["parcelas_restantes"] = compra["parcelas"] - parcelas_pagas
        linhas.append(linha)
    return pd.DataFrame(linhas)


def projecao_fatura_atual(hoje: date | None = None) -> float:
    """Projeta o total da fatura do mês corrente com base no ritmo de gastos
    no crédito até hoje (extrapolação linear simples)."""
    hoje = hoje or date.today()
    mes_referencia = utils.mes_referencia(hoje)
    inicio, fim = utils.intervalo_mes(mes_referencia)
    gastos = models.listar_gastos(data_inicio=inicio, data_fim=fim)
    gastos_credito = gastos[gastos["forma_pagamento"] == "Crédito"]["valor"].sum()

    dias_passados = hoje.day
    dias_no_mes = (utils.somar_meses(hoje.replace(day=1), 1) - hoje.replace(day=1)).days
    if dias_passados == 0:
        return round(gastos_credito, 2)

    ritmo_diario = gastos_credito / dias_passados
    projecao = ritmo_diario * dias_no_mes
    # A fatura projetada nunca é menor que o já gasto.
    return round(max(projecao, gastos_credito), 2)


# ---------------------------------------------------------------------------
# Gastos do dia a dia
# ---------------------------------------------------------------------------

def gasto_total_mes(mes_referencia: str | None = None) -> float:
    mes_referencia = mes_referencia or utils.mes_referencia()
    inicio, fim = utils.intervalo_mes(mes_referencia)
    gastos = models.listar_gastos(data_inicio=inicio, data_fim=fim)
    return round(gastos["valor"].sum(), 2) if not gastos.empty else 0.0


def gasto_por_categoria(mes_referencia: str | None = None) -> pd.DataFrame:
    mes_referencia = mes_referencia or utils.mes_referencia()
    inicio, fim = utils.intervalo_mes(mes_referencia)
    gastos = models.listar_gastos(data_inicio=inicio, data_fim=fim)
    if gastos.empty:
        return pd.DataFrame(columns=["categoria", "valor"])
    return (
        gastos.groupby("categoria", as_index=False)["valor"]
        .sum()
        .sort_values("valor", ascending=False)
        .reset_index(drop=True)
    )


def evolucao_mensal(n_meses: int = 6, hoje: date | None = None) -> pd.DataFrame:
    """Total gasto (fora cartão) por mês, últimos N meses, para gráfico de evolução."""
    hoje = hoje or date.today()
    linhas = []
    for i in range(n_meses - 1, -1, -1):
        mes_alvo_data = utils.somar_meses(hoje.replace(day=1), -i)
        mes_alvo = utils.mes_referencia(mes_alvo_data)
        linhas.append({
            "mes_referencia": mes_alvo,
            "mes_nome": utils.nome_mes(mes_alvo),
            "valor": gasto_total_mes(mes_alvo),
        })
    return pd.DataFrame(linhas)


def comparativo_mes_anterior(hoje: date | None = None) -> dict:
    hoje = hoje or date.today()
    mes_atual = utils.mes_referencia(hoje)
    mes_anterior = utils.mes_referencia(utils.somar_meses(hoje.replace(day=1), -1))

    gasto_atual = gasto_total_mes(mes_atual)
    gasto_passado = gasto_total_mes(mes_anterior)
    diferenca = gasto_atual - gasto_passado

    return {
        "mes_atual": gasto_atual,
        "mes_anterior": gasto_passado,
        "diferenca": round(diferenca, 2),
        "maior": diferenca > 0,
    }


def maior_categoria(mes_referencia: str | None = None) -> tuple[str, float] | None:
    df = gasto_por_categoria(mes_referencia)
    if df.empty:
        return None
    linha = df.iloc[0]
    return linha["categoria"], linha["valor"]


def gastos_periodo(dias: int = 180, hoje: date | None = None) -> pd.DataFrame:
    """Todos os gastos lançados nos últimos N dias."""
    hoje = hoje or date.today()
    inicio = hoje - timedelta(days=dias)
    return models.listar_gastos(data_inicio=inicio.isoformat())


DIAS_SEMANA_PT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
PARTES_MES = ["Início (1-10)", "Meio (11-20)", "Fim (21-31)"]


def gasto_por_dia_semana(dias: int = 180, hoje: date | None = None) -> pd.DataFrame:
    """Total gasto em cada dia da semana (ex.: 'gasto mais no fim de semana?')."""
    gastos = gastos_periodo(dias, hoje)
    if gastos.empty:
        return pd.DataFrame(columns=["dia_semana", "valor"])

    indice = pd.to_datetime(gastos["data"]).dt.dayofweek
    agrupado = gastos.groupby(indice)["valor"].sum().reindex(range(7), fill_value=0.0)
    return pd.DataFrame({"dia_semana": DIAS_SEMANA_PT, "valor": agrupado.values})


def gasto_por_parte_mes(dias: int = 180, hoje: date | None = None) -> pd.DataFrame:
    """Total gasto agrupado por início/meio/fim do mês (ex.: 'aperto mais perto do pagamento?')."""
    gastos = gastos_periodo(dias, hoje)
    if gastos.empty:
        return pd.DataFrame(columns=["parte", "valor"])

    dia_do_mes = pd.to_datetime(gastos["data"]).dt.day
    parte = pd.cut(dia_do_mes, bins=[0, 10, 20, 31], labels=PARTES_MES)
    agrupado = gastos.groupby(parte, observed=False)["valor"].sum().reindex(PARTES_MES, fill_value=0.0)
    return pd.DataFrame({"parte": PARTES_MES, "valor": agrupado.values})


def _agrupar_por_hora(gastos: pd.DataFrame) -> pd.DataFrame:
    """Total gasto por hora do dia, com base no campo opcional 'hora' de cada lançamento."""
    if gastos.empty or "hora" not in gastos.columns:
        return pd.DataFrame(columns=["hora", "valor"])

    com_hora = gastos[gastos["hora"].fillna("").str.strip() != ""]
    if com_hora.empty:
        return pd.DataFrame(columns=["hora", "valor"])

    hora_num = com_hora["hora"].str.slice(0, 2).astype(int)
    agrupado = com_hora.groupby(hora_num)["valor"].sum().reindex(range(24), fill_value=0.0)
    return pd.DataFrame({"hora": [f"{h:02d}h" for h in range(24)], "valor": agrupado.values})


def gasto_por_hora(dias: int = 180, hoje: date | None = None) -> pd.DataFrame:
    """Total gasto por hora do dia, numa janela rolante dos últimos N dias (uso no Dashboard)."""
    return _agrupar_por_hora(gastos_periodo(dias, hoje))


def gasto_por_hora_mes(mes_referencia: str | None = None) -> pd.DataFrame:
    """Total gasto por hora do dia, dentro de um mês específico (uso no relatório em PDF)."""
    mes_referencia = mes_referencia or utils.mes_referencia()
    inicio, fim = utils.intervalo_mes(mes_referencia)
    gastos = models.listar_gastos(data_inicio=inicio, data_fim=fim)
    return _agrupar_por_hora(gastos)


def tendencia_diaria(dias: int = 60, hoje: date | None = None) -> pd.DataFrame:
    """Gasto diário (todos os dias do período, mesmo sem lançamento) + média móvel de 7 dias."""
    hoje = hoje or date.today()
    inicio = hoje - timedelta(days=dias)
    todas_datas = pd.date_range(inicio, hoje, freq="D")

    gastos = models.listar_gastos(data_inicio=inicio.isoformat())
    if gastos.empty:
        diario = pd.DataFrame({"data": todas_datas, "valor": 0.0})
    else:
        agrupado = gastos.groupby("data")["valor"].sum()
        agrupado.index = pd.to_datetime(agrupado.index)
        diario = agrupado.reindex(todas_datas, fill_value=0.0).rename_axis("data").reset_index(name="valor")

    diario["media_movel_7d"] = diario["valor"].rolling(7, min_periods=1).mean()
    return diario


# ---------------------------------------------------------------------------
# Planejamento mensal (orçado x realizado)
# ---------------------------------------------------------------------------

def planejamento_vs_realizado(mes_referencia: str | None = None) -> pd.DataFrame:
    mes_referencia = mes_referencia or utils.mes_referencia()
    planejado = models.listar_planejamento(mes_referencia)[["categoria", "valor_planejado"]]
    realizado = gasto_por_categoria(mes_referencia).rename(columns={"valor": "valor_realizado"})

    df = planejado.merge(realizado, on="categoria", how="outer").fillna(0.0)
    df["valor_restante"] = df["valor_planejado"] - df["valor_realizado"]
    df["percentual_usado"] = df.apply(
        lambda r: (r["valor_realizado"] / r["valor_planejado"] * 100) if r["valor_planejado"] > 0 else None,
        axis=1,
    )
    return df.sort_values("categoria").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Reserva financeira
# ---------------------------------------------------------------------------

def saldo_reserva() -> float:
    movimentos = models.listar_movimentos_reserva()
    if movimentos.empty:
        return 0.0
    sinal = movimentos["tipo"].map({"Aporte": 1, "Retirada": -1})
    return round((movimentos["valor"] * sinal).sum(), 2)


def evolucao_reserva() -> pd.DataFrame:
    movimentos = models.listar_movimentos_reserva()
    if movimentos.empty:
        return pd.DataFrame(columns=["data", "saldo_acumulado"])
    sinal = movimentos["tipo"].map({"Aporte": 1, "Retirada": -1})
    movimentos = movimentos.copy()
    movimentos["valor_com_sinal"] = movimentos["valor"] * sinal
    movimentos["saldo_acumulado"] = movimentos["valor_com_sinal"].cumsum()
    return movimentos[["data", "saldo_acumulado"]]


def tempo_para_meta(meta: float, aporte_mensal: float) -> int | None:
    """Meses restantes para atingir a meta, dado um aporte mensal constante."""
    faltante = meta - saldo_reserva()
    if faltante <= 0:
        return 0
    if aporte_mensal <= 0:
        return None
    from math import ceil
    return ceil(faltante / aporte_mensal)


# ---------------------------------------------------------------------------
# Dia do pagamento: dinheiro real disponível e divisão por período
# ---------------------------------------------------------------------------

def dinheiro_disponivel_mes(salario: float, vale_alimentacao: float, contas_fixas_total: float,
                             fatura_cartao: float, aporte_reserva: float) -> dict:
    """Quanto sobra de dinheiro "livre" (fora o VA) depois de fixas, cartão e reserva.

    O VA é reportado à parte porque só cobre a categoria Alimentação/forma
    "Vale alimentação" — não deve inflar o valor livre para qualquer gasto.
    """
    livre = salario - contas_fixas_total - fatura_cartao - aporte_reserva
    return {
        "salario": salario,
        "vale_alimentacao": vale_alimentacao,
        "contas_fixas": contas_fixas_total,
        "fatura_cartao": fatura_cartao,
        "aporte_reserva": aporte_reserva,
        "dinheiro_livre": round(livre, 2),
    }


def dividir_por_periodo(valor: float, hoje: date | None = None, dia_util_pagamento: int = 5) -> dict:
    """Divide um valor pelos dias/semanas restantes até o próximo pagamento."""
    hoje = hoje or date.today()
    data_pagamento = utils.proximo_pagamento(hoje, dia_util_pagamento)
    dias_restantes = utils.dias_ate(data_pagamento, hoje)
    semanas_restantes = max(dias_restantes / 7, 1 / 7)

    return {
        "proximo_pagamento": data_pagamento,
        "dias_restantes": dias_restantes,
        "por_dia": round(valor / dias_restantes, 2) if dias_restantes else valor,
        "por_semana": round(valor / semanas_restantes, 2),
    }


def saldo_vale_alimentacao(mes_referencia: str | None = None) -> dict:
    """Quanto do vale alimentação já foi gasto e quanto ainda resta no mês."""
    mes_referencia = mes_referencia or utils.mes_referencia()
    config = models.get_config()
    inicio, fim = utils.intervalo_mes(mes_referencia)
    gastos = models.listar_gastos(data_inicio=inicio, data_fim=fim)
    gasto_va = gastos[gastos["forma_pagamento"] == "Vale alimentação"]["valor"].sum() if not gastos.empty else 0.0

    return {
        "total": config["vale_alimentacao"],
        "gasto": round(gasto_va, 2),
        "saldo": round(config["vale_alimentacao"] - gasto_va, 2),
    }


def saldo_disponivel_hoje(hoje: date | None = None) -> dict:
    """Junta config + contas fixas + fatura calculada + gasto já realizado no
    mês para responder: quanto ainda posso gastar até o próximo pagamento?
    """
    hoje = hoje or date.today()
    config = models.get_config()
    contas_fixas_total = models.listar_contas_fixas()["valor"].sum()

    # O ciclo financeiro real é pagamento-a-pagamento, não o mês civil — pode
    # virar o mês (ex.: virar agosto) antes do próximo pagamento acontecer.
    # Por isso a fatura e o "já gasto" usam o mês em que o ciclo COMEÇOU,
    # e não o mês civil de "hoje" — assim o valor não pula no meio do ciclo.
    inicio_ciclo = utils.pagamento_anterior(hoje, config["dia_util_pagamento"])
    mes_referencia_ciclo = utils.mes_referencia(inicio_ciclo)
    fatura = fatura_do_mes(mes_referencia_ciclo)

    disponivel = dinheiro_disponivel_mes(
        salario=config["salario"],
        vale_alimentacao=config["vale_alimentacao"],
        contas_fixas_total=contas_fixas_total,
        fatura_cartao=fatura,
        aporte_reserva=config["reserva_aporte_padrao"],
    )

    gastos_ciclo = models.listar_gastos(data_inicio=inicio_ciclo.isoformat(), data_fim=hoje.isoformat())
    gasto_ja_feito = round(gastos_ciclo["valor"].sum(), 2) if not gastos_ciclo.empty else 0.0
    # Gastos em "Vale alimentação" e "Crédito" já saem de outro bolso
    # (VA e fatura, respectivamente) — não descontar duas vezes do dinheiro livre.
    gasto_impacta_livre = gastos_ciclo[
        ~gastos_ciclo["forma_pagamento"].isin(["Vale alimentação", "Crédito"])
    ]["valor"].sum() if not gastos_ciclo.empty else 0.0

    saldo_restante = disponivel["dinheiro_livre"] - gasto_impacta_livre
    divisao = dividir_por_periodo(saldo_restante, hoje, config["dia_util_pagamento"])

    # Se o usuário marcou uma data de início de controle (ex.: "só valho a
    # partir do próximo pagamento, ainda não tenho o dinheiro do ciclo
    # anterior em mãos"), zera os valores em R$ até essa data chegar — sem
    # isso, dias_restantes/próximo pagamento seguem informativos.
    inicio_controle_str = config.get("inicio_controle") or ""
    controle_ativo = not inicio_controle_str or hoje >= date.fromisoformat(inicio_controle_str)
    if not controle_ativo:
        disponivel["dinheiro_livre"] = 0.0
        saldo_restante = 0.0
        divisao["por_dia"] = 0.0
        divisao["por_semana"] = 0.0

    return {
        **disponivel,
        "inicio_ciclo": inicio_ciclo,
        "gasto_ciclo": gasto_ja_feito,
        "gasto_impacta_livre": round(gasto_impacta_livre, 2),
        "saldo_restante": round(saldo_restante, 2),
        "controle_ativo": controle_ativo,
        "inicio_controle": inicio_controle_str,
        **divisao,
    }


# ---------------------------------------------------------------------------
# Inteligência financeira (insights automáticos)
# ---------------------------------------------------------------------------

def gerar_insights(hoje: date | None = None) -> list[str]:
    hoje = hoje or date.today()
    insights = []

    comparativo = comparativo_mes_anterior(hoje)
    if comparativo["mes_anterior"] > 0:
        if comparativo["maior"]:
            insights.append(
                f"Você gastou {utils.formatar_moeda(abs(comparativo['diferenca']))} "
                f"a mais que no mês passado."
            )
        elif comparativo["diferenca"] < 0:
            insights.append(
                f"Você economizou {utils.formatar_moeda(abs(comparativo['diferenca']))} "
                f"em relação ao mês passado."
            )

    maior = maior_categoria(utils.mes_referencia(hoje))
    if maior:
        insights.append(f"Sua maior categoria de gasto este mês foi {maior[0]} ({utils.formatar_moeda(maior[1])}).")

    projecao = projecao_fatura_atual(hoje)
    if projecao > 0:
        insights.append(f"Se continuar nesse ritmo, sua fatura do cartão deve fechar em torno de {utils.formatar_moeda(projecao)}.")

    fatura_atual = fatura_do_mes(utils.mes_referencia(hoje))
    config = models.get_config()
    limite_info = percentual_limite_cartao(fatura_atual, config["salario"] + config["vale_alimentacao"])
    if limite_info["percentual"] >= 80:
        insights.append(limite_info["mensagem"])

    return insights


# ---------------------------------------------------------------------------
# Nota do mês (veredito para o relatório mensal)
# ---------------------------------------------------------------------------

def nota_do_mes(mes_referencia: str | None = None) -> dict:
    """Nota de 0 a 10 pro mês, com detalhamento transparente de cada critério
    (nunca um número mágico sem explicação)."""
    mes_referencia = mes_referencia or utils.mes_referencia()
    hoje = date.fromisoformat(f"{mes_referencia}-01")
    nota = 10.0
    detalhes = []

    orcamento = planejamento_vs_realizado(mes_referencia)
    com_planejamento = orcamento[orcamento["valor_planejado"] > 0]
    estouradas = com_planejamento[com_planejamento["percentual_usado"] >= 100]
    if not com_planejamento.empty:
        if len(estouradas) > 0:
            penalidade = min(len(estouradas), 3)
            nota -= penalidade
            categorias = ", ".join(estouradas["categoria"])
            detalhes.append(f"Orçamento estourado em {len(estouradas)} categoria(s) ({categorias}): -{penalidade}")
        else:
            detalhes.append("Nenhuma categoria estourou o orçamento planejado: +0")

    fatura = fatura_do_mes(mes_referencia)
    config = models.get_config()
    limite_info = percentual_limite_cartao(fatura, config["salario"] + config["vale_alimentacao"])
    if limite_info["percentual"] >= 100:
        nota -= 2
        detalhes.append(f"Fatura do cartão passou do limite recomendado ({limite_info['percentual']:.0f}%): -2")
    elif limite_info["percentual"] >= 80:
        nota -= 1
        detalhes.append(f"Fatura do cartão perto do limite recomendado ({limite_info['percentual']:.0f}%): -1")

    movimentos = models.listar_movimentos_reserva()
    do_mes = movimentos[movimentos["data"].str.startswith(mes_referencia)] if not movimentos.empty else movimentos
    if not do_mes.empty:
        sinal = do_mes["tipo"].map({"Aporte": 1, "Retirada": -1})
        saldo_mes = (do_mes["valor"] * sinal).sum()
        if saldo_mes > 0:
            nota += 1
            detalhes.append(f"Reserva cresceu {utils.formatar_moeda(saldo_mes)} no mês: +1")
        elif saldo_mes < 0:
            nota -= 1
            detalhes.append(f"Reserva diminuiu {utils.formatar_moeda(abs(saldo_mes))} no mês: -1")

    comparativo = comparativo_mes_anterior(hoje)
    if comparativo["mes_anterior"] > 0:
        if comparativo["diferenca"] < 0:
            nota += 1
            detalhes.append(f"Gastou {utils.formatar_moeda(abs(comparativo['diferenca']))} a menos que no mês anterior: +1")
        elif comparativo["diferenca"] > comparativo["mes_anterior"] * 0.2:
            nota -= 1
            detalhes.append("Gastou bem mais (+20%) que no mês anterior: -1")

    nota = max(0.0, min(10.0, nota))

    if nota >= 9:
        veredito = "Mês exemplar — controle total."
    elif nota >= 7:
        veredito = "Mês sob controle."
    elif nota >= 5:
        veredito = "Mês ok, mas dá pra apertar em algumas categorias."
    elif nota >= 3:
        veredito = "Mês apertado — vale revisar o que pesou."
    else:
        veredito = "Mês difícil — hora de repensar prioridades."

    if not detalhes:
        detalhes.append("Sem dados suficientes para avaliar todos os critérios ainda.")

    return {"nota": round(nota, 1), "veredito": veredito, "detalhes": detalhes}
