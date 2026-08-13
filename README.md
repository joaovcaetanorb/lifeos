# LifeOS

Sistema pessoal de acompanhamento de vida — não é um app de finanças, hábitos ou produtividade isolado, e sim um painel único para entender melhor a própria vida e tomar melhores decisões ao longo dos anos.

Toda funcionalidade precisa passar no teste: **isso me ajuda a entender melhor minha vida e tomar melhores decisões?** Se não, não entra.

## Princípios

- Simplicidade e clareza acima de dashboards complexos — a tela inicial deve ser compreendida em menos de 30 segundos.
- Construção incremental: um módulo por vez, nunca em paralelo.
- Mobile-first, sem excesso de métricas ou gráficos.

## Stack

FastAPI (backend + API REST) servindo um frontend estático (HTML/CSS/JS sem
build step), banco Turso (libSQL) por módulo.

## Estrutura

```
webapp/
  main.py            # monta a API e serve o frontend de cada módulo
  financeiro/         # controle financeiro pessoal
  projetos/            # metas e projetos com orçamento e checklist
  habitos/             # check-in diário de hábitos, streak e % cumprido
  humor/               # registro de humor ao longo do dia
  livros/              # estante e diário de leitura
  musica/              # catálogo e diário de escutas
  analytics/           # tendências cruzando os módulos acima
  timeline/            # linha do tempo consolidada dos eventos
  frontend/            # HTML/CSS/JS de cada módulo + assets compartilhados
```

Cada módulo tem seu próprio banco Turso (embedded replica) e vive isolado em
`webapp/<nome>/` (router FastAPI) + `webapp/frontend/<nome>/` (páginas).

## Como rodar

```
cd webapp
uvicorn main:app --reload
```

Abre em `http://localhost:8000`.

## Deploy

`render.yaml` na raiz sobe o `webapp/` no Render (`rootDir: webapp`,
`uvicorn main:app`).

## Roadmap

1. Fundação/arquitetura
2. **Financeiro** — pronto
3. **Projetos** — pronto
4. **Hábitos** — pronto
5. **Humor** — pronto
6. **Livros** — pronto
7. **Música** — pronto
8. **Analytics** — pronto
9. **Timeline** — pronto
10. IA e Insights
