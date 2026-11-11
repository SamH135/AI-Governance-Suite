
# Project Structure Comparison

This document compares the structure of the individual legacy projects with the unified project.

## 1. AI-Compliance-NodeJS-Server-main vs. Unified Project

The `AI-Compliance-NodeJS-Server-main` project appears to have been replaced by the `gateway` service and parts of the `services` in the unified project.

| Feature | AI-Compliance-NodeJS-Server-main | Unified Project | Analysis |
|---|---|---|---|
| **Core Functionality** | Monolithic Node.js server | FastAPI gateway + Python microservices | The unified project adopts a microservices architecture, with a Python-based gateway. This is a significant architectural shift. |
| **Routing** | `routes` directory | `gateway/src/routes` and `services/*/routers` | Routing is now distributed among the gateway and individual services. |
| **Controllers** | `controllers` directory | N/A (logic is within services) | The controller logic from the Node.js application is likely migrated into the Python services. |
| **Middleware** | `middleware` directory | N/A (handled by FastAPI middleware) | FastAPI's middleware system replaces the custom middleware from the Node.js server. |

## 2. AI-Compliance-UI-main vs. Unified `frontend`

The `AI-Compliance-UI-main` project has been migrated to the `frontend` directory in the unified project, likely with some refactoring.

| Feature | AI-Compliance-UI-main | Unified `frontend` | Analysis |
|---|---|---|---|
| **Framework** | React (likely) | React (Vite) | Both use React, but the unified project uses Vite for a faster development experience. |
| **Structure** | `llm-testing-ui/src` | `frontend/src` | The core application structure seems similar, with `src` containing the main source code. |
| **Styling** | Tailwind CSS | Tailwind CSS | Both projects use Tailwind CSS for styling. |

## 3. AI-Compliance-Python-Backend-master vs. Unified `services`

The `AI-Compliance-Python-Backend-master` project seems to be the foundation for the various microservices in the unified project's `services` directory.

| Feature | AI-Compliance-Python-Backend-master | Unified `services` | Analysis |
|---|---|---|---|
| **Architecture** | Monolithic Python backend | Python microservices | The monolithic backend has been broken down into smaller, more manageable microservices. |
| **API Server** | `api_server.py` | `services/*/main.py` | Each microservice has its own entry point, typically `main.py`. |
| **Framework** | Flask (assumed) | FastAPI | The unified project uses FastAPI, a modern, high-performance Python web framework. |

## 4. ai-prompt-generator-main vs. Unified `services/prompts`

The `ai-prompt-generator-main` project has been integrated as the `prompts` microservice in the unified project.

| Feature | ai-prompt-generator-main | Unified `services/prompts` | Analysis |
|---|---|---|---|
| **Core Logic** | `backend` and `run.py` | `services/prompts/main.py` and `services/prompts/services` | The core logic for prompt generation has been encapsulated within the `prompts` microservice. |
| **Frontend** | `frontend` directory | Integrated into the main `frontend` | The UI for prompt generation is now part of the unified frontend. |

## 5. ml-llm-documentation-generator-main vs. Unified `services`

The `ml-llm-documentation-generator-main` project's functionality is likely integrated into one or more of the microservices, possibly the `documents` service.

| Feature | ml-llm-documentation-generator-main | Unified `services` | Analysis |
|---|---|---|---|
| **Core Logic** | `backend` directory | Likely in `services/documents` or a new service | The documentation generation logic is now a microservice, promoting separation of concerns. |
| **Frontend** | `frontend` directory | Integrated into the main `frontend` | The UI for documentation is part of the unified frontend. |

## Summary of Changes

The unified project represents a significant architectural evolution from the individual legacy projects. The key changes are:

*   **Microservices Architecture:** The monolithic backends have been replaced with a set of focused microservices. This improves scalability, maintainability, and allows for independent development and deployment.
*   **Technology Stack:** The unified project standardizes on a Python-based backend with FastAPI and a React-based frontend with Vite.
*   **Centralized Gateway:** An API gateway is introduced to handle incoming requests and route them to the appropriate microservices.
*   **Unified Frontend:** All UI components are consolidated into a single, coherent frontend application.

This new architecture provides a more robust and scalable foundation for the AI Compliance Platform.
