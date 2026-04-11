# ArchDocAI

> Documentação automática de arquitetura de software e dados com IA.
> Suporta Claude (Anthropic) e GPT (OpenAI) — traga seu próprio token.

---

## O que é

Engenheiros de dados e arquitetos perdem horas documentando arquiteturas manualmente.
O **ArchDocAI** lê o seu projeto, entende a estrutura em camadas, valida com você e gera:

- Diagrama de arquitetura visual (PNG + Mermaid)
- Documento técnico `.docx`
- PDF com documentação completa

---

## Arquitetura do Produto (3 Camadas)

```
┌─────────────────────────────────────────┐
│  CAMADA 1 — Ingestion                   │
│  scanner.py + context.py               │
│  Lê arquivos do projeto, monta contexto │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│  CAMADA 2 — Analysis                    │
│  llm_client.py + analyzer.py + diagram  │
│  LLM analisa, gera JSON + diagrama PNG  │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│  CAMADA 3 — Output                      │
│  docx_gen.py + pdf_gen.py               │
│  Gera documentação técnica completa     │
└─────────────────────────────────────────┘
```

---

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edite .env com seu LLM_PROVIDER e LLM_API_KEY
```

---

## Uso — CLI

```bash
# Analisar um projeto (modo interativo com validação)
python cli.py analyze ./meu-projeto

# Especificar nome e idioma
python cli.py analyze ./meu-projeto --name "DataPlatform v2" --lang en

# Sem validação interativa (modo automático)
python cli.py analyze ./meu-projeto --yes

# Sem PDF (só .docx e diagrama)
python cli.py analyze ./meu-projeto --no-pdf
```

---

## Uso — Interface Web

```bash
python cli.py serve
# Acesse http://localhost:8080
```

Na interface web:
1. Escolha o provedor (OpenAI ou Anthropic)
2. Informe seu API key
3. Envie o projeto como `.zip`
4. Responda as perguntas de validação do AI
5. Baixe `.docx`, PDF e diagrama PNG

---

## Suporte a LLMs

| Provedor | Modelos testados |
|---|---|
| OpenAI | `gpt-4o`, `gpt-4-turbo`, `gpt-3.5-turbo` |
| Anthropic | `claude-opus-4-6`, `claude-sonnet-4-6` |
| Custom | Qualquer modelo compatível com a API OpenAI (Ollama, etc.) |

Configuração via `.env`:
```env
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-...
LLM_MODEL=claude-sonnet-4-6
```

---

## Saídas Geradas

| Arquivo | Descrição |
|---|---|
| `output/architecture.png` | Diagrama visual em camadas |
| `output/PROJECT_architecture.docx` | Documentação técnica Word |
| `output/PROJECT_architecture.pdf` | Documentação técnica PDF |
| `output/PROJECT_diagram.mmd` | Markup Mermaid para edição |

---

## Estrutura do Repositório

```
archdocai/
├── src/
│   ├── ingestion/          # Camada 1 — lê e entende o projeto
│   │   ├── scanner.py      # Varre arquivos do projeto
│   │   └── context.py      # Monta contexto para o LLM
│   ├── analysis/           # Camada 2 — analisa com LLM
│   │   ├── llm_client.py   # Cliente LLM agnóstico
│   │   ├── analyzer.py     # Analisa arquitetura, valida com usuário
│   │   └── diagram.py      # Gera PNG e Mermaid
│   └── output/             # Camada 3 — gera documentos
│       ├── docx_gen.py     # Gera .docx
│       └── pdf_gen.py      # Gera PDF
├── web/
│   ├── app.py              # FastAPI web interface
│   └── templates/
│       └── index.html      # Frontend web
├── cli.py                  # CLI principal
├── requirements.txt
└── .env.example
```
