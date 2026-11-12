# AI Governance Suite

Enterprise-grade AI compliance platform for testing, documenting, and managing regulatory requirements (GDPR, HIPAA, EU AI Act, bias/safety). Built as a Python FastAPI microservices backend with a React 18 + Vite frontend.

## Overview

The platform automates the full AI compliance lifecycle—from evaluation to report generation—via a pluggable, multi-tenant system. It integrates five specialized microservices: an API gateway, compliance evaluation engine, prompt optimization service, document generation service, and analytics service.

## Architecture

### System Components

```
Frontend (React/Vite) → API Gateway (FastAPI) → Microservices → Data Layer
```

**Services:**
- **gateway** (port 8000): FastAPI API gateway — auth, routing, rate-limiting, WebSocket
- **compliance** (port 8001): AI evaluation engine — runs evaluators, manages frameworks
- **prompts** (port 8002): RL-based prompt optimization & generation
- **documents** (port 8003): Template & compliance report generation
- **analytics** (port 8005): Metrics aggregation & dashboard data

**Data Layer:**
- PostgreSQL 15: Primary relational database
- Milvus 2.3: Vector database for RAG
- Redis 7: Caching and session management
- MinIO: Object storage for documents

### Evaluation Run Flow

How a single/multi-turn probe evaluation moves through the system:

```mermaid
flowchart LR
    subgraph Client
        UI["Frontend<br/>React :3000"]
        CLI["curl / API clients"]
    end

    GW["API Gateway :8000<br/>JWT auth · rate limit · proxy"]

    subgraph Services
        CS["Compliance :8001<br/>plugin registry · probe harness"]
        PS["Prompts :8002"]
        DS["Documents :8003"]
        AN["Analytics :8005"]
    end

    subgraph "Probe Harness (inside compliance)"
        CASE["ProbeCase<br/>turns · checks · canaries"]
        LOOP{"turn loop<br/>single or multi-turn"}
        TOOLS{"tool call?<br/>native_tools / simulated / mcp_server"}
        MCP["MCPToolset<br/>stdio MCP server<br/>tools/list · tools/call"]
        JUDGE["Judges<br/>canary · refusal ·<br/>StrongREJECT · exfil"]
    end

    subgraph "Unified API (shared/unified_api)"
        API["api.generate<br/>tools · tool_calls"]
        G["Google"]
        O["OpenAI-compatible<br/>OpenAI · Groq · DeepSeek"]
        A["Anthropic"]
    end

    DB[("PostgreSQL<br/>systems · model configs ·<br/>encrypted keys · results")]

    UI --> GW
    CLI --> GW
    GW -- "POST /api/systems/{id}/test-unified<br/>(Authorization: Bearer JWT)" --> CS

    CS --> DB
    CS --> CASE --> LOOP
    LOOP -- "model turn" --> API
    API --> G & O & A
    LOOP -- "tool_call" --> TOOLS
    TOOLS -- "MCP server case" --> MCP
    MCP --> LOOP
    TOOLS -- "fixture / native" --> LOOP
    LOOP -- "transcript" --> JUDGE
    JUDGE -- "judge calls" --> API
    JUDGE -- "score + evidence<br/>+ OWASP/ATLAS/NIST refs" --> CS
    CS -- "result (stored)" --> DB
    CS --> AN
    GW --> PS & DS
```

Key: the **target model** and the **judge model** are both reached through the same Unified API — configure them as separate model configs to avoid self-grading. Tool calls resolve three ways depending on the case: `native_tools` (provider function calling), the simulated JSON protocol, or a real `mcp_server` subprocess.

### Unified AI API

The platform uses a model-agnostic AI API system that provides a single interface for all AI providers (OpenAI, Anthropic, Google, HuggingFace, local models). This eliminates vendor lock-in and allows dynamic model configuration via the database.

Key features:
- Database-driven model configuration
- Encrypted API key storage with user isolation
- Automatic usage tracking and cost estimation
- Hot-pluggable provider architecture

### Plugin System

New compliance evaluators are implemented as plugins under `plugins/evaluators/`. The system provides:
- Hot-loading of custom evaluators
- YAML-based plugin configuration
- Base evaluator class with standardized interface
- Automatic plugin discovery and validation

The platform ships probe-based security evaluators that run multi-turn, tool-call, and RAG-context attacks against a target model and produce scored evidence with framework references:

| Evaluator | Maps to |
|---|---|
| `system_prompt_leakage` | OWASP LLM07 / ATLAS T0056 |
| `jailbreak_robustness` | OWASP LLM01 / ATLAS T0054 (includes over-refusal axis) |
| `indirect_prompt_injection` | OWASP LLM01 / ASI01 / ATLAS T0051.001 |
| `unbounded_consumption` | OWASP LLM10 / NIST MS-2.7-007 |
| `vector_embedding_security` | OWASP LLM08 |
| `tool_misuse` | OWASP LLM06 / ASI02 / ATLAS T0053, T0086 |
| `tool_poisoning` | ASI04 / ATLAS T0110 |
| `memory_poisoning` | ASI06 |
| `multi_turn_escalation` | OWASP LLM01 / ATLAS T0054 |
| `excessive_agency` | OWASP LLM06 / ASI02, ASI09 |

Plus passive text evaluators: `prompt_injection`, `pii_leakage`, `insecure_output`, `hallucination_checker`, `bias_detection`-style generic checks via `generic_compliance`/`g_eval_metric`.

Probe capabilities:
- **Multi-turn conversations, RAG document injection, simulated tool protocols** via `services/compliance/framework/probes/`
- **Native provider tool calling** — `ModelRequest.tools`/`ModelResponse.tool_calls` translated to Gemini function declarations, OpenAI `tools`, and Anthropic `tool_use`
- **MCP client layer** (`shared/unified_api/mcp_client.py`) — connects to real MCP servers over stdio, pulls live tool manifests, and executes real tool calls inside probes (dependency-free JSON-RPC; HTTP transport not yet implemented)
- Every result carries per-case evidence, transcripts, token usage, provenance, and OWASP/ATLAS/NIST references — designed for audit artifacts

> **Note:** The plugin system is the extension point: drop a custom evaluator into `plugins/evaluators/` and it's discovered and loaded automatically at startup. Shipped corpora are small (4–8 cases per evaluator) — `probes/benchmarks.py` loads HarmBench/JailbreakBench/XSTest/AgentDojo-style files for statistical power.

### Example live results

Full authenticated runs against three models (judge: Gemini; `n`=4–6 cases per evaluator, directional not statistical — raw data in `eval_results/`):

| Evaluator | Gemini 3.1 Flash-Lite | DeepSeek-Chat | Groq GPT-OSS-120B |
|---|---|---|---|
| System Prompt Leakage | **6.7** (93% leaked, incl. base64-encoded) | 80 | — |
| Indirect Prompt Injection | 100 | 90 | — |
| Tool Misuse | 90 | 80 | — |
| Tool Poisoning | — | — | **50** |
| Jailbreak Robustness | 87.5 | — | 87.5 |
| Multi-Turn Escalation | — | — | 75 |
| Memory Poisoning | 100 | — | — |
| Unbounded Consumption | 70.9 | — | — |

## Technology Stack

**Frontend:**
- React 18.3+
- Vite 6.4+
- Tailwind CSS 3.4+
- Material-UI 6.0+
- React Router 7
- Chart.js for visualizations

**Backend:**
- Python 3.9+
- FastAPI 0.162+
- PyJWT (auth)
- SQLAlchemy 2.0+
- Pydantic 2.0+
- Structlog for JSON logging

**Infrastructure:**
- Docker & Docker Compose
- PostgreSQL 15
- Milvus 2.3
- Redis 7
- MinIO

## Getting Started

### Prerequisites

- Docker 20+ and Docker Compose
- Node.js 22+ (for local frontend development)
- Python 3.9+ (for local service development)

### Quick Start

1. Clone the repository:
```bash
git clone <repository-url>
cd AI-Governance-Suite
```

2. Create environment file:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Start the full stack:
```bash
docker-compose up --build
```

4. Access the platform:
- Frontend: http://localhost:3000
- API Gateway docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### Alternative Start Options

**Lightweight (no vector DB):**
```bash
docker-compose -f docker-compose.simple.yml up --build
```

**Development mode (hot-reload):**
```bash
docker-compose -f docker-compose.dev.yml up --build
```

**Frontend only (local development):**
```bash
cd frontend
npm install
npm run dev
```

### Run Your First Evaluation

All evaluator plugins load automatically at startup. The eval flow is four API calls (compliance service on `:8001`, or via the gateway on `:8000`):

```bash
# 1. Login — dev seed account admin/admin123 (change before any real deployment;
#    scripts/create_test_user.py creates additional users)
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}' | jq -r .data.token)

# 2. Create a model config for the target model (your provider key)
curl -X POST http://localhost:8001/api/models \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "gemini-target", "provider": "google",
       "model_id": "gemini-3.1-flash-lite", "api_key": "'$GEMINI_API_KEY'"}'
# → returns config_id, e.g. 4. OpenAI-compatible endpoints (groq, deepseek,
#   vLLM) use "provider": "openai" plus "api_url": "https://api.groq.com/openai/v1"

# 3. Create an AI system wired to that config
curl -X POST http://localhost:8001/api/systems \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name": "Eval Target", "model_config_id": 4}'
# → returns system_id, e.g. 3

# 4. Run evaluators against it
curl -X POST http://localhost:8001/api/systems/3/test-unified \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"evaluators": ["system_prompt_leakage", "jailbreak_robustness"],
       "evaluator_model_id": 4}'
# → per-case evidence, transcripts, scores, and framework refs.
#   Use a different config_id for the judge so the target isn't grading itself.

# Coverage: which framework controls have evaluators + latest scores
curl http://localhost:8001/api/systems/3/coverage-matrix \
  -H "Authorization: Bearer $TOKEN"
```

Every completed run is persisted (`compliance_test_executions`) and feeds the coverage matrix. The gated suite `tests/integration/test_probe_live.py` runs the same flow against every probe evaluator (`RUN_LIVE_EVALS=1`).

### Environment Configuration

Key environment variables:

```yaml
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/ai_compliance
REDIS_URL=redis://localhost:6379/0

# AI Provider API Keys
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here
GROQ_API_KEY=your_key_here          # OpenAI-compatible (via api_url)
DEEPSEEK_API_KEY=your_key_here      # OpenAI-compatible (via api_url)

# Security
JWT_SECRET=your_jwt_secret_here     # required — no insecure default
JWT_ALGORITHM=HS256

# Service URLs (Docker internal)
COMPLIANCE_SERVICE_URL=http://compliance-service:8001
PROMPTS_SERVICE_URL=http://prompt-service:8002
DOCUMENTS_SERVICE_URL=http://document-service:8003
```

## Development

### Running Tests

**Unit tests:**
```bash
pytest tests/unit/ -v
```

**Integration tests:**
```bash
pytest tests/integration/ -v
```

**Frontend tests:**
```bash
cd frontend
npm run test
npm run test:coverage
```

### Code Quality

**Python:**
```bash
black services/ gateway/
isort services/ gateway/
flake8 services/ gateway/
mypy services/ gateway/
```

**Frontend:**
```bash
cd frontend
npm run lint
npm run format
```

### Adding New Evaluators

New compliance evaluators must be implemented as plugins:

1. Create plugin directory: `plugins/evaluators/<your_evaluator>/`
2. Implement the base evaluator class
3. Add plugin configuration YAML
4. Follow existing examples (e.g., `plugins/evaluators/hallucination_checker/`)

Do not hardcode evaluation logic directly into `services/compliance/`.

## Service Endpoints

| Service | URL | Documentation | Health Check |
|---------|-----|---------------|--------------|
| Frontend | http://localhost:3000 | Interactive UI | N/A |
| API Gateway | http://localhost:8000 | `/docs` | `/health` |
| Compliance | http://localhost:8001 | `/docs` | `/health` |
| Prompts | http://localhost:8002 | `/docs` | `/health` |
| Documents | http://localhost:8003 | `/docs` | `/health` |
| Analytics | http://localhost:8005 | `/docs` | `/health` |

## Deployment

### Docker Production

```bash
# Build production images
docker-compose -f docker-compose.prod.yml build

# Deploy
docker-compose -f docker-compose.prod.yml up -d

# Scale services
docker-compose -f docker-compose.prod.yml up -d --scale compliance-service=3
```

### Kubernetes

Apply configurations in order:
```bash
kubectl apply -f infrastructure/k8s/namespace.yaml
kubectl apply -f infrastructure/k8s/configmaps/
kubectl apply -f infrastructure/k8s/secrets/
kubectl apply -f infrastructure/k8s/deployments/
kubectl apply -f infrastructure/k8s/services/
kubectl apply -f infrastructure/k8s/ingress/
```

### Infrastructure Requirements

**Minimum:**
- CPU: 8 cores
- RAM: 16GB
- Storage: 100GB SSD
- Network: 1Gbps

**Recommended:**
- Application nodes: 3x (4 CPU, 8GB RAM)
- Database node: 1x (8 CPU, 16GB RAM, 200GB SSD)
- Vector DB node: 1x (4 CPU, 8GB RAM, 100GB SSD)
- Cache node: 1x (2 CPU, 4GB RAM)

## Repository Structure

```
gateway/              FastAPI API gateway
services/
  compliance/         AI evaluation engine
  prompts/            RL-based prompt optimization
  documents/          Template & report generation
  analytics/          Metrics aggregation
  shared/             Shared DB, Redis, exception utilities
plugins/
  evaluators/         Custom evaluator plugins
  configs/            Plugin configuration schemas
infrastructure/
  database/           SQL init scripts
tests/
  unit/               Pytest unit tests
  integration/        Integration tests
  manual/             Manual test scripts
eval_results/         Live evaluator run artifacts (chart-ready JSON)
frontend/src/
  pages/              Route views
  components/         Reusable UI components
  services/           Axios API clients
  hooks/              Custom React hooks
  contexts/           React context providers
```

## Compliance Frameworks

- GDPR: General Data Protection Regulation
- HIPAA: Healthcare Information Portability and Accountability Act
- EU AI Act: European Union AI regulation
- Bias Detection: Fairness and bias evaluation
- Safety Evaluation: Content safety and hallucination detection
- Custom Frameworks: Build your own compliance evaluators via plugins

## Documentation

- Unified AI API Guide: Complete AI integration documentation
- Plugin System Guide: Plugin development documentation
- RL Optimizer Guide: Reinforcement learning optimization
- API Documentation: Interactive API docs at `/docs` endpoints
- Frontend Components: React component library

## License

MIT — see [LICENSE](LICENSE).
