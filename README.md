# README.md
# Radar de Finanças MVP

Portal e API do Radar Financeiro com Stream SSE em tempo real, autenticação JWT e
gráficos interativos (Chart.js). MVP custo zero, modular e pronto para deploy.

## Stack

- **FastAPI** + **uvicorn** (ASGI)
- **SQLite** via **aiosqlite** (WAL, retry/backoff)
- **JWT** (PyJWT) + **bcrypt** para autenticação
- **SSE** (sse-starlette) para tempo real
- **Jinja2** + **htmx/Alpine.js/Chart.js** no frontend
- Logger JSON rotativo e middleware de segurança

## Estrutura

```
app/
├── main.py                 # Entry point (FastAPI)
├── core/core.py            # Config (.env) + Logger JSON
├── shared/                 # database, security, middleware
├── modules/auth/           # Registro/login JWT + planos
├── modules/realtime/       # Stream SSE + manager
└── templates/index.html    # Portal (Alpine.js + Chart.js)
scripts/init_db.py          # Seed admin + métricas
tests/                      # Testes pytest
```

## Setup

```bash
# 1. Configuração (copie e ajuste)
cp .env.example .env

# 2. Ambiente com uv
uv sync --extra dev

# 3. Inicializa e popula o banco
uv run python -m scripts.init_db

# 4. Sobe a aplicação
uv run uvicorn app.main:app --reload --port 8000
```

Acesse `http://localhost:8000` (portal), `/docs` (API docs) e `/health`.

### Usuário demo (plano premium)

- Email: `admin@exemplo.com`
- Senha: `Admin@123`

## API

| Método | Rota                | Descrição                             |
|--------|---------------------|---------------------------------------|
| POST   | `/auth/register`    | Cadastro (e-mail/WhatsApp) + código de confirmação |
| POST   | `/auth/confirm`     | Confirma cadastro com o código recebido |
| POST   | `/auth/login`       | Login (exige cadastro confirmado), retorna JWT |
| POST   | `/auth/logout`      | Logout (descarta token)               |
| GET    | `/noticias/manchetes` | Headlines do dia (RSS Valor/InfoMoney/Exame/Bloomberg/FT) — exige login |
| POST   | `/plano/trial`    | Semana de demonstração grátis (7 dias, 1x por usuário) |
| POST   | `/plano/assinar`    | Assinatura mensal premium (checkout simulado) |
| GET    | `/plano/premium`    | Vitrine do plano mensal                |
| GET    | `/plano/meu`        | Status da assinatura do usuário        |
| GET    | `/realtime/stream`  | SSE de métricas (Bearer token premium) |
| GET    | `/realtime/status`  | Contagem de conexões ativas            |
| GET    | `/indicadores/resumo` | Indicadores reais (SELIC, IPCA, câmbio, IBOVESPA) |
| GET    | `/indicadores/serie/{selic\|ipca\|ipca_12m\|dolar}` | Série histórica (Bacen SGS) |
| GET    | `/espacos-publicidade` | Espaços publicitários disponíveis    |
| GET    | `/anuncio/{slug}`   | Página de negociação do espaço (anúncio) |
| POST   | `/anuncio/{slug}/contato` | Registra interesse em anunciar      |
| GET    | `/health`           | Healthcheck                           |

Fonte de dados: Banco Central do Brasil (API SGS) para SELIC, IPCA e câmbio, e
Yahoo Finance (B3) para o IBOVESPA. Dados com cache de 10 minutos e sem chave de API.

> **Confirmação**: em modo dev, o código de 6 dígitos é exibido na resposta do
> cadastro (`codigo_demo`) e registrado nos logs. Para plugar envio real, edite
> `AuthService._enviar_codigo` (SMTP ou WhatsApp Business API).
>
> **Pagamento**: `/plano/assinar` é um checkout simulado. Para integrar pagamento
> real, adicione Stripe/Mercado Pago no `PlanoService.assinar`.

## Testes

```bash
uv run pytest -v
```

## Deploy

- **Docker**: `docker compose up --build`
- **Fly.io**: `fly deploy` (config via `fly.toml`)

Variáveis de ambiente (`ALLOWED_ORIGINS`, `JWT_SECRET_KEY`, `DATABASE_URL`) devem
ser ajustadas em produção.