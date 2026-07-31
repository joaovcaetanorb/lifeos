"""Integração com a API do Groq — geração da saudação do Dashboard Geral a
partir do contexto de HOJE (nunca histórico/tendência, isso é do Analytics).

Qualquer falha aqui (sem credencial configurada, erro de rede, timeout)
degrada pra "recurso indisponível" em vez de quebrar a página — a saudação
é um complemento opcional, os cards continuam funcionando sem ela.
"""

import streamlit as st
from groq import Groq

MODELO = "llama-3.3-70b-versatile"

_SISTEMA = (
    "Você é um assistente pessoal dentro do LifeOS, um app de acompanhamento "
    "de vida do usuário. Sua única tarefa aqui é escrever UMA saudação curta "
    "(1-2 frases, no máximo) resumindo como está o dia do usuário AGORA. "
    "Não tente encaixar todos os blocos de dados — escolha só 1 ou 2 que "
    "sejam mais notáveis hoje (um prazo apertado, um saldo curto, um livro "
    "quase terminando, uma tarefa específica, etc.) e varie esse foco de um "
    "dia pro outro. Evite cair sempre na fórmula 'humor + hábitos "
    "pendentes' — trate humor e hábitos como só mais dois blocos entre os "
    "outros, não como ponto de partida padrão. Nunca mencione meses "
    "passados, tendências ou comparações históricas, isso não é seu papel "
    "aqui. Tom caloroso mas direto, em português do Brasil. Baseie-se "
    "SOMENTE nos dados fornecidos — nunca invente números. Se não houver "
    "dado nenhum, diga algo breve e simpático incentivando a começar a usar "
    "os módulos."
)


@st.cache_resource(show_spinner=False)
def _get_client() -> Groq | None:
    try:
        api_key = st.secrets["GROQ_API_KEY"]
    except (KeyError, FileNotFoundError):
        return None
    return Groq(api_key=api_key)


def disponivel() -> bool:
    return _get_client() is not None


def gerar_saudacao(contexto: str) -> str | None:
    cliente = _get_client()
    if cliente is None:
        return None
    try:
        resposta = cliente.chat.completions.create(
            model=MODELO,
            messages=[
                {"role": "system", "content": _SISTEMA},
                {"role": "user", "content": f"Dados de hoje:\n\n{contexto}"},
            ],
            temperature=0.5,
            max_tokens=150,
        )
        return resposta.choices[0].message.content.strip()
    except Exception:
        return None
