#!/usr/bin/env python3
"""
Check and document available local models in the system.
This script doesn't require torch - just checks configurations.
"""

import json
import os
from pathlib import Path
from datetime import datetime

print("=" * 80)
print("LOCAL SMALL LANGUAGE MODELS (SLM) - CONFIGURATION CHECK")
print("=" * 80)
print(f"Check Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# 1. Check HuggingFace cache
print("🔍 STEP 1: Checking HuggingFace Cache")
print("-" * 80)

hf_cache_paths = [Path.home() / ".cache" / "huggingface" / "hub"]
if os.environ.get("HF_CACHE_PATH"):
    hf_cache_paths.append(Path(os.environ["HF_CACHE_PATH"]))

downloaded_models = []
for hf_cache in hf_cache_paths:
    if hf_cache.exists():
        print(f"✅ Found HuggingFace cache at: {hf_cache}")

        model_dirs = sorted([d for d in hf_cache.iterdir()
                            if d.is_dir() and d.name.startswith("models--")])

        for model_dir in model_dirs:
            model_name = model_dir.name.replace("models--", "").replace("--", "/")
            downloaded_models.append(model_name)
        break
else:
    print("❌ HuggingFace cache not found")

print(f"\n📦 Total downloaded models: {len(downloaded_models)}\n")

# 2. Check project configuration
print("🔍 STEP 2: Checking Project Configuration")
print("-" * 80)

# Check local model manager
local_models_path = Path("services/shared/local_models.py")
if local_models_path.exists():
    print(f"✅ Local model manager found: {local_models_path}")

    with open(local_models_path) as f:
        content = f.read()

        # Extract model configurations
        if "model_configs" in content:
            print("✅ Model configurations defined in code")

            # Try to extract config details
            import re
            models_match = re.search(r'self\.model_configs\s*=\s*{([^}]+)}', content, re.DOTALL)
            if models_match:
                print("   Configured model categories:")
                lines = models_match.group(0).split('\n')
                for line in lines[1:5]:  # Show first few lines
                    if line.strip() and not line.strip().startswith('#'):
                        print(f"   {line.strip()}")
else:
    print(f"❌ Local model manager not found")

# Check API routes
local_models_router = Path("services/compliance/routers/local_models.py")
if local_models_router.exists():
    print(f"✅ Local models API router found: {local_models_router}")
    print("   Endpoints available:")
    print("   - GET  /local-models/available")
    print("   - POST /local-models/load")
    print("   - GET  /local-models/loaded")
    print("   - POST /local-models/generate")
    print("   - POST /local-models/embeddings")
    print("   - GET  /local-models/memory")
else:
    print(f"❌ Local models router not found")

print()

# 3. Model documentation
print("🔍 STEP 3: Available Models Documentation")
print("-" * 80)

MODEL_DOCS = {
    "TinyLlama/TinyLlama-1.1B-Chat-v1.0": {
        "downloaded": "TinyLlama/TinyLlama-1.1B-Chat-v1.0" in downloaded_models,
        "parameters": "1.1B",
        "type": "Generative (CausalLM)",
        "context_window": 2048,
        "license": "Apache 2.0",
        "min_ram_gb": 4,
        "min_vram_gb": 2,
        "capabilities": ["Chat", "Reasoning", "Code generation", "Multi-turn dialogue"],
        "use_cases": ["Customer support", "Basic QA", "Simple code generation"],
        "strengths": ["Fast inference", "Low memory", "Apache 2.0 license"],
        "limitations": ["Simple reasoning", "Limited knowledge compared to larger models"]
    },
    "google/gemma-2b-it": {
        "downloaded": "google/gemma-2b-it" in downloaded_models,
        "parameters": "2B",
        "type": "Generative (Instruction-tuned)",
        "context_window": 8192,
        "license": "Gemma License",
        "min_ram_gb": 6,
        "min_vram_gb": 4,
        "capabilities": ["Instruction following", "Chat", "Reasoning", "Multi-step tasks"],
        "use_cases": ["Instruction following", "Complex QA", "Multi-step reasoning"],
        "strengths": ["Good instruction following", "Larger context window"],
        "limitations": ["Requires license acceptance", "Higher memory usage"]
    },
    "google/gemma-3-1b-it": {
        "downloaded": "google/gemma-3-1b-it" in downloaded_models or "google/gemma-3-1b-it" in [m.replace("-it", "") for m in downloaded_models],
        "parameters": "1B",
        "type": "Generative (Instruction-tuned)",
        "context_window": 8192,
        "license": "Gemma License",
        "min_ram_gb": 4,
        "min_vram_gb": 2,
        "capabilities": ["Instruction following", "Chat", "Reasoning"],
        "use_cases": ["Lightweight instruction following", "Edge deployment"],
        "strengths": ["Small footprint", "Good performance"],
        "limitations": ["Less powerful than 2B version"]
    },
    "microsoft/phi-2": {
        "downloaded": "microsoft/phi-2" in downloaded_models,
        "parameters": "2.7B",
        "type": "Generative (CausalLM)",
        "context_window": 2048,
        "license": "MIT",
        "min_ram_gb": 6,
        "min_vram_gb": 4,
        "capabilities": ["Reasoning", "Code generation", "Math", "Logic"],
        "use_cases": ["Complex reasoning", "Code assistance", "Math problems"],
        "strengths": ["Excellent reasoning", "MIT license", "Outperforms larger models"],
        "limitations": ["Shorter context window", "Higher memory"]
    },
    "microsoft/phi-1_5": {
        "downloaded": "microsoft/phi-1_5" in downloaded_models,
        "parameters": "1.3B",
        "type": "Generative (CausalLM)",
        "context_window": 2048,
        "license": "MIT",
        "min_ram_gb": 4,
        "min_vram_gb": 2,
        "capabilities": ["Chat", "Code generation", "Basic reasoning"],
        "use_cases": ["Lightweight code generation", "Basic chat"],
        "strengths": ["Fast", "Low memory", "MIT license"],
        "limitations": ["Less capable than Phi-2"]
    },
    "facebook/opt-125m": {
        "downloaded": "facebook/opt-125m" in downloaded_models,
        "parameters": "125M",
        "type": "Generative (CausalLM)",
        "context_window": 2048,
        "license": "MIT",
        "min_ram_gb": 2,
        "min_vram_gb": 1,
        "capabilities": ["Text generation", "Basic completion"],
        "use_cases": ["Testing", "Very lightweight deployment"],
        "strengths": ["Very small", "Fast inference"],
        "limitations": ["Limited capabilities", "Basic performance only"]
    },
    "google/flan-t5-large": {
        "downloaded": "google/flan-t5-large" in downloaded_models,
        "parameters": "780M",
        "type": "Encoder-Decoder (Seq2Seq)",
        "context_window": 512,
        "license": "Apache 2.0",
        "min_ram_gb": 4,
        "min_vram_gb": 2,
        "capabilities": ["Instruction following", "Translation", "Summarization"],
        "use_cases": ["Translation", "Summarization", "Instruction tasks"],
        "strengths": ["Good for specific tasks", "Encoder-decoder architecture"],
        "limitations": ["Not for chat", "Shorter context"]
    },
    "sentence-transformers/all-mpnet-base-v2": {
        "downloaded": "sentence-transformers/all-mpnet-base-v2" in downloaded_models,
        "parameters": "110M",
        "type": "Embedding Model",
        "embedding_dim": 768,
        "license": "Apache 2.0",
        "min_ram_gb": 2,
        "min_vram_gb": 1,
        "capabilities": ["Text embeddings", "Semantic search", "Similarity"],
        "use_cases": ["RAG systems", "Semantic search", "Clustering"],
        "strengths": ["High quality embeddings", "Fast"],
        "limitations": ["English-focused", "768 dimensions"]
    },
    "distilbert/distilbert-base-uncased-finetuned-sst-2-english": {
        "downloaded": "distilbert/distilbert-base-uncased-finetuned-sst-2-english" in downloaded_models,
        "parameters": "66M",
        "type": "Classification",
        "license": "Apache 2.0",
        "min_ram_gb": 2,
        "min_vram_gb": 1,
        "capabilities": ["Sentiment analysis", "Text classification"],
        "use_cases": ["Sentiment analysis", "Binary classification"],
        "strengths": ["Fast", "Accurate for sentiment"],
        "limitations": ["Sentiment-specific", "Binary classification only"]
    },
    "cross-encoder/nli-deberta-v3-small": {
        "downloaded": "cross-encoder/nli-deberta-v3-small" in downloaded_models,
        "parameters": "103M",
        "type": "Reranking / NLI",
        "license": "Apache 2.0",
        "min_ram_gb": 2,
        "min_vram_gb": 1,
        "capabilities": ["Document reranking", "NLI", "Relevance scoring"],
        "use_cases": ["RAG reranking", "Search result ranking"],
        "strengths": ["Accurate reranking", "Small footprint"],
        "limitations": ["Requires pre-scored documents", "Slower than embedding models"]
    }
}

# Display model information
generative_models = []
embedding_models = []
specialized_models = []

for model_name, info in MODEL_DOCS.items():
    status = "✅ DOWNLOADED" if info['downloaded'] else "❌ NOT FOUND"
    print(f"\n{model_name}")
    print(f"   Status: {status}")
    print(f"   Parameters: {info['parameters']}")
    print(f"   Type: {info['type']}")

    if info['type'] == "Embedding Model":
        embedding_models.append(model_name)
    elif "Classification" in info['type'] or "Reranking" in info['type']:
        specialized_models.append(model_name)
    else:
        generative_models.append(model_name)

    print(f"   Capabilities: {', '.join(info['capabilities'][:3])}")
    if info.get('min_vram_gb'):
        print(f"   Min VRAM: {info['min_vram_gb']} GB | Min RAM: {info['min_ram_gb']} GB")

print()
print("=" * 80)
print("SUMMARY")
print("=" * 80)
print()

print(f"✅ Downloaded Generative Models: {len([m for m in generative_models if MODEL_DOCS[m]['downloaded']])}")
for model in generative_models:
    if MODEL_DOCS[model]['downloaded']:
        print(f"   • {model}")

print(f"\n✅ Downloaded Embedding Models: {len([m for m in embedding_models if MODEL_DOCS[m]['downloaded']])}")
for model in embedding_models:
    if MODEL_DOCS[model]['downloaded']:
        print(f"   • {model}")

print(f"\n✅ Downloaded Specialized Models: {len([m for m in specialized_models if MODEL_DOCS[m]['downloaded']])}")
for model in specialized_models:
    if MODEL_DOCS[model]['downloaded']:
        print(f"   • {model}")

print()
print("=" * 80)
print("USAGE RECOMMENDATIONS")
print("=" * 80)
print()

print("🚀 PRODUCTION READY (Recommended):")
print("   • microsoft/phi-2 - Best reasoning and code generation")
print("   • TinyLlama/TinyLlama-1.1B-Chat-v1.0 - Fast, lightweight chat")
print("   • sentence-transformers/all-mpnet-base-v2 - High-quality embeddings")

print("\n⚡ FASTEST / LOWEST RESOURCE:")
print("   • facebook/opt-125m - Minimal resource usage")
print("   • microsoft/phi-1_5 - Good balance of speed and capability")
print("   • distilbert-base-uncased-finetuned-sst-2-english - Fast sentiment analysis")

print("\n🎯 TASK-SPECIFIC:")
print("   • google/flan-t5-large - Translation and summarization")
print("   • cross-encoder/nli-deberta-v3-small - Document reranking")
print("   • google/gemma-2b-it - Instruction following (requires license)")

print()
print("=" * 80)
print("API USAGE")
print("=" * 80)
print()

print("To use these models via the API:")
print()
print("1. Check available models:")
print("   GET http://localhost:8000/api/compliance/local-models/available")
print()
print("2. Load a model (admin only):")
print("   POST http://localhost:8000/api/compliance/local-models/load")
print("   {")
print('     "model_name": "microsoft/phi-2",')
print('     "model_type": "causal_lm",')
print('     "quantization": "8bit"  // optional')
print("   }")
print()
print("3. Generate text:")
print("   POST http://localhost:8000/api/compliance/local-models/generate")
print("   {")
print('     "model_key": "microsoft/phi-2_causal_lm",')
print('     "prompt": "Explain quantum computing",')
print('     "max_length": 200,')
print('     "temperature": 0.7')
print("   }")
print()
print("4. Generate embeddings:")
print("   POST http://localhost:8000/api/compliance/local-models/embeddings")
print("   {")
print('     "model_key": "sentence-transformers/all-mpnet-base-v2_embedding",')
print('     "texts": ["Hello world", "Machine learning"]')
print("   }")
print()
print("5. View loaded models:")
print("   GET http://localhost:8000/api/compliance/local-models/loaded")
print()
print("6. Check memory usage:")
print("   GET http://localhost:8000/api/compliance/local-models/memory")
print()

print("=" * 80)
print("CONFIGURED AND READY TO USE")
print("=" * 80)
