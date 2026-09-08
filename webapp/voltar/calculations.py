"""Regras de negócio do módulo voltar. Deliberadamente simples e sem
'nota'/streak — ver o pedido original do usuário: pequenas promessas
cumpridas > grandes planos abandonados, sem cobrança de perfeição."""

from datetime import date, timedelta

import pandas as pd

from . import repo as models

FASES = [
    {"numero": 1, "nome": "Base", "foco": "Sono, água, pequenas responsabilidades, leitura e uma coisa boa por dia.", "dia_ate": 9},
    {"numero": 2, "nome": "Corpo", "foco": "Academia segunda, quarta e sexta. Não precisa ser perfeito — só ir.", "dia_ate": 24},
    {"numero": 3, "nome": "Aparência", "foco": "Cabelo, barba, unhas, pele, roupa, postura — devagar, sem virar obsessão.", "dia_ate": 39},
    {"numero": 4, "nome": "Alimentação", "foco": "Uma refeição melhor por dia. Só isso, por enquanto.", "dia_ate": 54},
    {"numero": 5, "nome": "Dinheiro", "foco": "Organizar o salário, segurar o impulso, guardar um pouco.", "dia_ate": 69},
    {"numero": 6, "nome": "Cigarro e Cannabis", "foco": "Observar gatilhos, atrasar o primeiro cigarro do dia, uso mais consciente.", "dia_ate": 84},
    {"numero": 7, "nome": "Vida", "foco": "Lazer, música, jogos, basquete, amigos, família — escolher, não fugir.", "dia_ate": None},
]

_LABEL_PEQUENO = {
    "agua": "Beber um copo de água.",
    "leitura": "Ler só uma página, nem precisa ser mais.",
    "responsabilidades": "Resolver uma coisinha pequena que está pesando.",
    "sono": "Tentar deitar um pouco mais cedo hoje.",
}


def dias_desde_inicio(hoje: date, data_inicio_iso: str) -> int:
    inicio = date.fromisoformat(data_inicio_iso)
    return max(1, (hoje - inicio).days + 1)


def fase_atual(dias: int) -> dict:
    for f in FASES:
        if f["dia_ate"] is None or dias <= f["dia_ate"]:
            return {**f, "dia_do_projeto": dias}
    return {**FASES[-1], "dia_do_projeto": dias}


def _feito(registro: dict | None, campo: str) -> bool:
    return bool(registro) and registro.get(campo) in (1, True)


def _dormiu(registro: dict | None) -> bool:
    """Sono não é sim/não — é a hora que foi deitar na noite anterior
    (ver _LABEL_PEQUENO). 'feito' aqui significa só 'já registrou'."""
    return bool(registro) and bool(registro.get("hora_dormir"))


def _campo_feito(registro: dict | None, campo: str) -> bool:
    return _dormiu(registro) if campo == "sono" else _feito(registro, campo)


def sugerir_prioridade(fase_numero: int, weekday: int, registro_hoje: dict | None) -> dict:
    """weekday: 0=segunda ... 4=sexta (Python date.weekday())."""
    if fase_numero >= 2 and weekday in (0, 2, 4):
        academia_feita = bool(registro_hoje) and registro_hoje.get("academia") == "sim"
        if not academia_feita:
            return {
                "campo": "academia",
                "texto": "Ir para a academia. Não precisa ser o treino perfeito — só colocar a roupa e ir.",
            }

    for campo in ("responsabilidades", "agua", "sono", "leitura"):
        if not _campo_feito(registro_hoje, campo):
            return {"campo": campo, "texto": _LABEL_PEQUENO.get(campo) or campo}

    return {"campo": None, "texto": "Hoje não precisa resolver nada grande. Só continuar existindo já é suficiente."}


def sugerir_pequeno(registro_hoje: dict | None, campo_prioridade: str | None) -> str:
    for campo in ("agua", "leitura", "responsabilidades"):
        if campo == campo_prioridade:
            continue
        if not _feito(registro_hoje, campo):
            return _LABEL_PEQUENO[campo]
    return "Beber um copo de água a mais, só isso."


def sugestao_coisa_boa(hoje: date) -> str:
    tags = models.listar_tags_coisa_boa()
    if tags.empty:
        return "Escolha alguma coisa boa pra você hoje."
    idx = hoje.toordinal() % len(tags)
    return tags.iloc[idx]["rotulo"]


def badges_identidade(df_30d: pd.DataFrame) -> list[str]:
    if df_30d.empty:
        return []

    def conta(col: str, val=1) -> int:
        return int((df_30d[col] == val).sum())

    badges = []
    if conta("responsabilidades") >= 15:
        badges.append("Você é alguém que cumpre pequenas promessas.")
    if int((df_30d["academia"] == "sim").sum()) >= 8:
        badges.append("Você é alguém que vai à academia.")
    if int((df_30d["hora_dormir"].fillna("") != "").sum()) >= 15:
        badges.append("Você é alguém que presta atenção no próprio sono.")
    if conta("leitura") >= 10:
        badges.append("Você é alguém que voltou a ler.")
    if conta("agua") >= 15:
        badges.append("Você é alguém que cuida do próprio corpo.")
    dentro, fora = int((df_30d["dinheiro"] == "dentro").sum()), int((df_30d["dinheiro"] == "fora").sum())
    if dentro >= 5 and dentro > fora:
        badges.append("Você é alguém que consegue guardar dinheiro.")
    if int((df_30d["maconha"] == "usei_cuidei").sum()) >= 10:
        badges.append("Você é alguém que resolve suas obrigações antes do lazer.")
    return badges


def frase_do_momento(fase: dict, weekday: int, dias_do_projeto: int, registrados_semana: int, badges: list[str]) -> str:
    """Uma frase de contexto pro topo do dia — muda com a situação em vez
    de ser sempre a mesma. Regra simples e determinística (sem IA), na
    ordem de prioridade abaixo."""
    if fase["numero"] >= 2 and weekday not in (0, 2, 4):
        return "Hoje não é dia de academia. Aproveita pra viver um pouco também."
    if dias_do_projeto > 3 and registrados_semana == 0:
        return "Ontem não define hoje. Dá pra voltar."
    if len(badges) >= 2:
        return "Olha só... você está começando a cumprir o que promete pra si."
    return "Você não precisa resolver sua vida hoje."


def painel(hoje: date | None = None) -> dict:
    hoje = hoje or date.today()
    meta = models.obter_meta()
    dias = dias_desde_inicio(hoje, meta["data_inicio"])
    fase = fase_atual(dias)
    registro_hoje = models.obter_registro(hoje.isoformat())

    prioridade = sugerir_prioridade(fase["numero"], hoje.weekday(), registro_hoje)
    pequeno = sugerir_pequeno(registro_hoje, prioridade["campo"])
    coisa_boa_sugerida = sugestao_coisa_boa(hoje)

    df30 = models.listar_registros(data_inicio=(hoje - timedelta(days=29)).isoformat())
    badges = badges_identidade(df30)
    registrados_semana = 0
    if not df30.empty:
        inicio_semana = (hoje - timedelta(days=6)).isoformat()
        registrados_semana = int((df30["data"] >= inicio_semana).sum())

    frase = frase_do_momento(fase, hoje.weekday(), dias, registrados_semana, badges)

    return {
        "hoje": hoje.isoformat(),
        "registro_hoje": registro_hoje,
        "fase": fase,
        "frase": frase,
        "sugestao": {
            "prioridade": prioridade["texto"],
            "pequeno": pequeno,
            "coisa_boa": coisa_boa_sugerida,
        },
        "badges": badges,
        "semana": {"registrados": registrados_semana, "total": 7},
    }
