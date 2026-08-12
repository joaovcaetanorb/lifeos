"""Integração com a API do Groq — port do padrão de webapp/musica/groq_service.py,
adaptado pra comentar UM dia da timeline: cruza o que a pessoa fez com os
registros de humor daquele dia, em vez de estatística de período."""

from groq import Groq

from core.config import settings

MODELO = "groq/compound"
MODELO_FALLBACK = "llama-3.3-70b-versatile"

_SISTEMA = (
    "Você é um assistente pessoal dentro do LifeOS, comentando um dia "
    "específico da timeline do usuário (hábitos, humor, financeiro, livros, "
    "música, projetos e outros registros). Responda em português do Brasil, "
    "em tom direto, curto e informal — nada de linguagem corporativa.\n\n"
    "Sua tarefa é relacionar o que a pessoa FEZ nesse dia com o que ela "
    "SENTIU (registros de humor, se houver) — por exemplo, se o humor caiu "
    "ou subiu perto de algum evento específico, ou se um padrão de "
    "atividade parece ligado ao estado dela. Não apenas liste os eventos de "
    "novo, aponte a conexão (ou a falta dela). Baseie-se SOMENTE nos dados "
    "fornecidos — nunca invente evento ou nota que não esteja no contexto. "
    "Se não houver registro de humor nesse dia, comente só as atividades e "
    "diga que não há humor registrado. Responda em no máximo 3-4 frases "
    "corridas, sem lista, sem markdown."
)

_client_singleton: Groq | None = None
_client_tentado = False


def _get_client() -> Groq | None:
    global _client_singleton, _client_tentado
    if _client_tentado:
        return _client_singleton
    _client_tentado = True
    if settings.groq_api_key:
        _client_singleton = Groq(api_key=settings.groq_api_key)
    return _client_singleton


def disponivel() -> bool:
    return _get_client() is not None


def gerar_leitura_dia(contexto: str) -> str | None:
    cliente = _get_client()
    if cliente is None:
        return None
    mensagens = [
        {"role": "system", "content": _SISTEMA},
        {"role": "user", "content": f"Timeline do dia:\n\n{contexto}"},
    ]
    for modelo in (MODELO, MODELO_FALLBACK):
        try:
            resposta = cliente.chat.completions.create(
                model=modelo, messages=mensagens, temperature=0.6, max_tokens=260,
            )
            texto = (resposta.choices[0].message.content or "").strip()
            if texto:
                return texto
        except Exception:
            continue
    return None
