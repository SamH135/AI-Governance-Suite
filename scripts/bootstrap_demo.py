#!/usr/bin/env python3
"""
Bootstrap a working demo: model config -> AI system -> one sanity eval.

Run after `docker compose up -d` on a fresh clone:

    python scripts/bootstrap_demo.py

Reads provider keys from .env (GEMINI_API_KEY, GROQ_API_KEY, or
DEEPSEEK_API_KEY — first found wins). Prints the system_id and the
exact eval call when done. DEVELOPMENT ONLY.
"""

import os
import sys
import time

import requests

API = os.getenv("DEMO_API_URL", "http://localhost:8000/api")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "admin123")

PROVIDERS = [
    # (env var, provider name, default model)
    ("GROQ_API_KEY", "groq", "openai/gpt-oss-120b"),
    ("GEMINI_API_KEY", "google", "gemini-2.0-flash-lite"),
    ("DEEPSEEK_API_KEY", "openai", "deepseek-chat"),
]
PROVIDER_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "openai": "https://api.deepseek.com",
}


def load_env(path=".env"):
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


def wait_for_gateway(timeout=90):
    base = API.rsplit("/api", 1)[0]
    for _ in range(timeout):
        try:
            if requests.get(f"{base}/health/", timeout=2).status_code == 200:
                return True
        except requests.ConnectionError:
            time.sleep(1)
    return False


def main():
    load_env()

    print("Waiting for gateway...")
    if not wait_for_gateway():
        sys.exit("Gateway did not come up. Run `docker compose up -d` first.")

    login = requests.post(f"{API}/auth/login", json={"username": "admin", "password": DEMO_PASSWORD})
    if login.status_code != 200:
        sys.exit(f"Login failed ({login.status_code}): check DEMO_PASSWORD. "
                 f"Fresh clones seed admin/admin123.")
    token = login.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Logged in as admin")

    # Model config from whichever provider key exists
    key_env = next((e for e, _, _ in PROVIDERS if os.getenv(e)), None)
    if not key_env:
        sys.exit("No provider key in .env (need GEMINI_API_KEY, GROQ_API_KEY, or DEEPSEEK_API_KEY)")
    env_name, provider, model = next((e, p, m) for e, p, m in PROVIDERS if e == key_env)

    existing = requests.get(f"{API}/models/", headers=headers).json()
    if isinstance(existing, list) and existing:
        config_id = existing[0].get("config_id") or existing[0]["id"]
        print(f"Reusing existing model config {config_id}")
    else:
        body = {
            "name": f"Demo {provider}",
            "provider": provider,
            "model_id": model,
            "api_key": os.environ[key_env],
        }
        if provider in PROVIDER_URLS:
            body["api_url"] = PROVIDER_URLS[provider]
        resp = requests.post(f"{API}/models/", json=body, headers=headers)
        if resp.status_code not in (200, 201):
            sys.exit(f"Model config failed ({resp.status_code}): {resp.text[:200]}")
        created = resp.json()
        config_id = created.get("config_id") or created["id"]
        print(f"Created model config {config_id} ({provider}/{model})")

    # Demo system
    systems = requests.get(f"{API}/compliance/systems", headers=headers).json()
    systems = systems.get("data", systems) if isinstance(systems, dict) else systems
    if systems:
        system_id = systems[0]["system_id"]
        print(f"Reusing existing system {system_id}")
    else:
        resp = requests.post(f"{API}/systems/", headers=headers, json={
            "name": "Demo AI System",
            "description": "Bootstrap demo — replace with your own system",
            "system_type": "llm",
            "compliance_frameworks": ["owasp-llm", "owasp-asi"],
            "model_config_id": config_id,
        })
        if resp.status_code not in (200, 201):
            sys.exit(f"System creation failed ({resp.status_code}): {resp.text[:200]}")
        system_id = resp.json()["system_id"]
        print(f"Created demo system {system_id}")

    # One cheap eval to prove the loop works
    resp = requests.post(
        f"{API}/compliance/systems/{system_id}/test-unified",
        headers=headers,
        json={
            "evaluators": ["jailbreak_robustness"],
            "test_prompts": "quick bootstrap sanity check",
            "test_subject_model_id": config_id,
            "evaluator_model_id": config_id,
        },
        timeout=300,
    )
    if resp.status_code == 200:
        print("Sanity eval completed — results persisted")
    else:
        print(f"Sanity eval returned {resp.status_code} (config/system created — "
              f"run evals manually, this may be a provider quota issue)")

    print(f"""
Done. Demo system_id: {system_id}

Run an eval:
  curl -X POST http://localhost:8000/api/compliance/systems/{system_id}/test-unified \\
    -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \\
    -d '{{"evaluators": ["jailbreak_robustness", "tool_misuse"],
       "test_prompts": "demo", "test_subject_model_id": {config_id},
       "evaluator_model_id": {config_id}}}'

Coverage matrix:
  curl http://localhost:8000/api/compliance/coverage-matrix -H "Authorization: Bearer <token>"
""")


if __name__ == "__main__":
    main()
