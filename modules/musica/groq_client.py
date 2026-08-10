"""Integração com a API do Groq — insights curtos sobre as estatísticas de
música (Diário ou histórico real do Spotify), no mesmo espírito do
groq_client.py de Analytics.

Qualquer falha aqui (sem credencial configurada, erro de rede, timeout)
degrada pra "recurso indisponível" em vez de quebrar a página — a IA é um
complemento opcional, os gráficos e números continuam funcionando sem ela.
"""

import streamlit as st
from groq import Groq

MODELO = "llama-3.3-70b-versatile"

_SISTEMA = (
    "Você é um assistente pessoal dentro do LifeOS, comentando os hábitos "
    "musicais do usuário. Responda em português do Brasil, em tom direto, "
    "curto e informal — nada de linguagem corporativa. Baseie-se SOMENTE "
    "nos dados fornecidos no contexto — nunca invente números, artistas ou "
    "faixas que não estejam lá. Se o contexto não tiver dado suficiente "
    "pra uma observação minimamente confiável, diga isso em vez de forçar "
    "uma conclusão fraca."
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


def gerar_insights(contexto: str) -> str | None:
    """2-4 observações curtas sobre o `contexto` (números já calculados em
    Python — ver calculations.contexto_ia_diario/contexto_ia_real). None
    se a API não estiver disponível ou a chamada falhar."""
    cliente = _get_client()
    if cliente is None:
        return None
    prompt = (
        f"Dados reais do período selecionado:\n\n{contexto}\n\n"
        "Aponte de 2 a 4 observações curtas sobre o que esses dados sugerem "
        "sobre o gosto ou hábito musical do usuário nesse período (ex.: "
        "padrão de horário, gênero ou artista em alta, contraste entre "
        "épocas, algo que se destaca). Formate como lista curta, uma "
        "observação por linha."
    )
    try:
        resposta = cliente.chat.completions.create(
            model=MODELO,
            messages=[
                {"role": "system", "content": _SISTEMA},
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
            max_tokens=400,
        )
        return resposta.choices[0].message.content.strip()
    except Exception:
        return None
