"""Integração com a API do Groq — mesmo scaffolding de
webapp/musica/groq_service.py (cliente singleton, sem cache do Streamlit),
com três tarefas: escrever uma leitura corrida do período cruzando os
módulos, narrar os cruzamentos já calculados em
webapp/analytics/calculations.py (a IA nunca inventa um número, só
interpreta o que já foi computado em código), e responder perguntas
livres sobre os dados agregados."""

from groq import Groq

from core.config import settings

MODELO = "groq/compound"
MODELO_FALLBACK = "llama-3.3-70b-versatile"

_SISTEMA_LEITURA = (
    "Você é um assistente pessoal dentro do LifeOS, escrevendo uma leitura "
    "corrida do período pro usuário — não uma lista de estatísticas por "
    "módulo, e sim um texto curto (2-4 frases) que amarra o que se destacou "
    "entre financeiro, hábitos, humor, livros, música e projetos nesse "
    "período, como se fosse uma observação de alguém que olhou tudo junto. "
    "Priorize relações entre módulos quando fizerem sentido (ex.: gastar "
    "mais coincidindo com humor mais baixo), mas não force uma conexão que "
    "não esteja nos dados. Português do Brasil, tom direto e caloroso, sem "
    "markdown, sem listas. Baseie-se SOMENTE nos dados fornecidos — nunca "
    "invente números. Se o contexto tiver pouco dado, diga isso em vez de "
    "encher linguiça."
)

_SISTEMA_PERGUNTAS = (
    "Você é um assistente pessoal dentro do LifeOS, respondendo perguntas "
    "sobre os dados agregados do usuário cruzando todos os módulos "
    "(financeiro, hábitos, humor, livros, música, projetos). Responda em "
    "português do Brasil, em tom direto e curto (no máximo um parágrafo "
    "curto, ou uma lista de 2-4 itens quando fizer mais sentido). "
    "Baseie-se SOMENTE nos dados fornecidos no contexto — nunca invente "
    "números. Se o contexto não tiver dado suficiente pra responder algo "
    "com confiança, diga isso claramente em vez de especular."
)

_SISTEMA_CORRELACOES = (
    "Você é um assistente pessoal dentro do LifeOS. Vai receber uma lista "
    "de cruzamentos JÁ CALCULADOS entre módulos (ex.: nota média de humor "
    "em dias com hábito cumprido vs. sem, cada um com o tamanho da "
    "amostra). Sua única tarefa é narrar o que esses números já prontos "
    "sugerem, em português do Brasil, tom direto e curto — 1 frase curta "
    "por cruzamento, ou um parágrafo curto se preferir amarrar tudo. NUNCA "
    "invente ou recalcule um número — use exatamente os valores dados. Se "
    "a diferença entre os grupos for pequena, diga que é inconclusiva em "
    "vez de forçar uma conclusão."
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


def _chamar(mensagens: list[dict], temperature: float, max_tokens: int) -> str | None:
    cliente = _get_client()
    if cliente is None:
        return None
    for modelo in (MODELO, MODELO_FALLBACK):
        try:
            resposta = cliente.chat.completions.create(
                model=modelo, messages=mensagens, temperature=temperature, max_tokens=max_tokens,
            )
            texto = (resposta.choices[0].message.content or "").strip()
            if texto:
                return texto
        except Exception:
            continue
    return None


def gerar_leitura_periodo(contexto: str) -> str | None:
    mensagens = [
        {"role": "system", "content": _SISTEMA_LEITURA},
        {"role": "user", "content": f"Dados do período, agregados por módulo:\n\n{contexto}"},
    ]
    return _chamar(mensagens, temperature=0.6, max_tokens=280)


def responder_pergunta(pergunta: str, contexto: str) -> str | None:
    mensagens = [
        {"role": "system", "content": _SISTEMA_PERGUNTAS},
        {"role": "user", "content": f"Dados do usuário, agregados por módulo:\n\n{contexto}\n\nPergunta do usuário: {pergunta}"},
    ]
    return _chamar(mensagens, temperature=0.5, max_tokens=400)


def narrar_correlacoes(pares: list[dict]) -> str | None:
    linhas = [
        f"- {p['titulo']} ({p['metrica']}): {p['label_a']} (n={p['n_a']}) teve média {p['media_a']}; "
        f"{p['label_b']} (n={p['n_b']}) teve média {p['media_b']}."
        for p in pares
    ]
    mensagens = [
        {"role": "system", "content": _SISTEMA_CORRELACOES},
        {"role": "user", "content": "Cruzamentos calculados:\n\n" + "\n".join(linhas)},
    ]
    return _chamar(mensagens, temperature=0.4, max_tokens=300)
