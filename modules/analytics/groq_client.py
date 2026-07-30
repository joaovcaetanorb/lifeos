"""Integração com a API do Groq — geração de texto (respostas a perguntas
e sugestões automáticas) a partir do contexto agregado dos módulos.

Qualquer falha aqui (sem credencial configurada, erro de rede, timeout)
degrada pra "recurso indisponível" em vez de quebrar a página — a IA é um
complemento opcional, os gráficos e números continuam funcionando sem ela.
"""

import streamlit as st
from groq import Groq

MODELO = "llama-3.3-70b-versatile"

_SISTEMA = (
    "Você é um assistente pessoal dentro do LifeOS, um app de acompanhamento "
    "de vida do usuário. Responda em português do Brasil, em tom direto e "
    "curto (no máximo um parágrafo curto, ou uma lista de 2-4 itens curtos "
    "quando fizer mais sentido). Baseie-se SOMENTE nos dados fornecidos no "
    "contexto — nunca invente números. Se o contexto não tiver dado "
    "suficiente pra responder algo com confiança, diga isso claramente em "
    "vez de especular."
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


def _chamar(prompt_usuario: str) -> str | None:
    cliente = _get_client()
    if cliente is None:
        return None
    try:
        resposta = cliente.chat.completions.create(
            model=MODELO,
            messages=[
                {"role": "system", "content": _SISTEMA},
                {"role": "user", "content": prompt_usuario},
            ],
            temperature=0.4,
            max_tokens=500,
        )
        return resposta.choices[0].message.content.strip()
    except Exception:
        return None


def responder_pergunta(pergunta: str, contexto: str) -> str | None:
    prompt = (
        f"Dados do usuário (últimos meses, agregados por módulo):\n\n{contexto}\n\n"
        f"Pergunta do usuário: {pergunta}"
    )
    return _chamar(prompt)


def narrar_correlacao(descricao: str) -> str | None:
    """Traduz em 1-2 frases uma comparação estatística JÁ CALCULADA em
    Python (ver calculations.correlacoes_humor) — a IA nunca calcula nem
    inventa o número aqui, só explica o que ele sugere."""
    prompt = (
        f"Aqui está uma comparação estatística real, já calculada a partir dos dados "
        f"do usuário (não invente nada além do que está descrito abaixo):\n\n{descricao}\n\n"
        "Escreva 1-2 frases curtas, em tom direto, explicando o que essa diferença "
        "sugere. Se a diferença for pequena ou pouco conclusiva, diga isso em vez de "
        "forçar uma leitura forte."
    )
    return _chamar(prompt)


def gerar_sugestoes(contexto: str) -> str | None:
    prompt = (
        f"Dados do usuário (últimos meses, agregados por módulo):\n\n{contexto}\n\n"
        "Sem que o usuário tenha perguntado nada específico, olhe esses dados "
        "e aponte de 2 a 4 observações ou padrões que possam ser úteis pra ele "
        "entender melhor a própria vida (ex.: relações entre módulos, "
        "tendências, algo que se destaca). Formate como uma lista curta. Se "
        "não houver dado suficiente pra uma observação minimamente confiável, "
        "diga isso em vez de forçar uma conclusão fraca."
    )
    return _chamar(prompt)
