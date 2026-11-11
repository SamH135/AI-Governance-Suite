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

## Technology Stack

**Frontend:**
- React 18.3+
- Vite 5.1+
- Tailwind CSS 3.4+
- Material-UI 6.0+
- Chart.js for visualizations

**Backend:**
- Python 3.9+
- FastAPI 0.104+
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
- Node.js 18+ (for local frontend development)
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

### Environment Configuration

Key environment variables:

```yaml
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/ai_compliance
REDIS_URL=redis://localhost:6379/0

# AI Provider API Keys
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
GOOGLE_API_KEY=your_key_here

# Security
JWT_SECRET=your_jwt_secret_here
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

Proprietary. All rights reserved.
