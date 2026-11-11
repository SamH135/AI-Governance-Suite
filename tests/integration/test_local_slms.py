#!/usr/bin/env python3
"""
Comprehensive test script for local Small Language Models (SLMs).
Tests all downloaded models in HuggingFace cache.
"""

import asyncio
import sys
import torch
from pathlib import Path
from datetime import datetime
import json
import os

# Add project paths
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

# Check available models
hf_cache_path = Path(os.environ.get("HF_CACHE_PATH", Path.home() / ".cache" / "huggingface" / "hub"))

# Clean up model names
downloaded_models = []
if hf_cache_path.exists():
    model_dirs = sorted([d for d in hf_cache_path.iterdir() if d.is_dir() and d.name.startswith("models--")])
    for model_dir in model_dirs:
        model_name = model_dir.name.replace("models--", "").replace("--", "/")
        downloaded_models.append(model_name)

print(f"✅ Found {len(downloaded_models)} downloaded models:")
for i, model in enumerate(downloaded_models, 1):
    print(f"   {i}. {model}")
print()

# Define model categories and capabilities
MODEL_INFO = {
    "TinyLlama/TinyLlama-1.1B-Chat-v1.0": {
        "type": "generative",
        "params": "1.1B",
        "context_length": 2048,
        "license": "Apache 2.0",
        "test_prompt": "Write a haiku about artificial intelligence.",
        "capabilities": ["chat", "reasoning", "code generation"],
        "requirements": {"min_ram_gb": 4, "min_vram_gb": 2}
    },
    "google/gemma-2b-it": {
        "type": "generative",
        "params": "2B",
        "context_length": 8192,
        "license": "gemma",
        "test_prompt": "What are three benefits of renewable energy?",
        "capabilities": ["chat", "instruction following", "reasoning"],
        "requirements": {"min_ram_gb": 6, "min_vram_gb": 4}
    },
    "google/gemma-3-1b-it": {
        "type": "generative",
        "params": "1B",
        "context_length": 8192,
        "license": "gemma",
        "test_prompt": "Explain machine learning in simple terms.",
        "capabilities": ["chat", "instruction following", "reasoning"],
        "requirements": {"min_ram_gb": 4, "min_vram_gb": 2}
    },
    "microsoft/phi-2": {
        "type": "generative",
        "params": "2.7B",
        "context_length": 2048,
        "license": "MIT",
        "test_prompt": "Why is Python a popular programming language?",
        "capabilities": ["reasoning", "code generation", "math"],
        "requirements": {"min_ram_gb": 6, "min_vram_gb": 4}
    },
    "microsoft/phi-1_5": {
        "type": "generative",
        "params": "1.3B",
        "context_length": 2048,
        "license": "MIT",
        "test_prompt": "What is the capital of France?",
        "capabilities": ["chat", "code generation", "reasoning"],
        "requirements": {"min_ram_gb": 4, "min_vram_gb": 2}
    },
    "facebook/opt-125m": {
        "type": "generative",
        "params": "125M",
        "context_length": 2048,
        "license": "MIT",
        "test_prompt": "Complete the sentence: The future of AI is",
        "capabilities": ["text generation"],
        "requirements": {"min_ram_gb": 2, "min_vram_gb": 1}
    },
    "google/flan-t5-large": {
        "type": "encoder-decoder",
        "params": "780M",
        "context_length": 512,
        "license": "Apache 2.0",
        "test_prompt": "Translate to Spanish: Hello, how are you?",
        "capabilities": ["instruction following", "translation", "summarization"],
        "requirements": {"min_ram_gb": 4, "min_vram_gb": 2}
    },
    "sentence-transformers/all-mpnet-base-v2": {
        "type": "embedding",
        "params": "110M",
        "embedding_dim": 768,
        "license": "Apache 2.0",
        "test_texts": ["Hello world", "Machine learning is fascinating"],
        "capabilities": ["embeddings", "semantic search"],
        "requirements": {"min_ram_gb": 2, "min_vram_gb": 1}
    },
    "distilbert/distilbert-base-uncased-finetuned-sst-2-english": {
        "type": "classification",
        "params": "66M",
        "license": "Apache 2.0",
        "test_text": "I absolutely love this product!",
        "capabilities": ["sentiment analysis", "classification"],
        "requirements": {"min_ram_gb": 2, "min_vram_gb": 1}
    },
    "cross-encoder/nli-deberta-v3-small": {
        "type": "reranking",
        "params": "103M",
        "license": "Apache 2.0",
        "test_pairs": [("What is AI?", "Artificial Intelligence is a field of computer science.")],
        "capabilities": ["reranking", "NLI"],
        "requirements": {"min_ram_gb": 2, "min_vram_gb": 1}
    }
}

# Check system resources
print("💻 System Resources:")
print(f"   PyTorch Version: {torch.__version__}")
print(f"   CUDA Available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"   CUDA Version: {torch.version.cuda}")
    print(f"   GPU Count: {torch.cuda.device_count()}")
    for i in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(i)
        print(f"   GPU {i}: {props.name} ({props.total_memory / 1024**3:.1f} GB)")
else:
    print("   GPU: Not available (using CPU)")
print()

import psutil
mem = psutil.virtual_memory()
print(f"   System RAM: {mem.total / 1024**3:.1f} GB (Available: {mem.available / 1024**3:.1f} GB)")
print()

# Test models
test_results = {
    "successful": [],
    "failed": [],
    "skipped": []
}

print("=" * 80)
print("TESTING MODELS")
print("=" * 80)
print()

async def test_generative_model(model_name, model_info):
    """Test a generative model."""
    print(f"🧪 Testing: {model_name}")
    print(f"   Type: {model_info['type']} | Parameters: {model_info['params']}")

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer

        print("   ⏳ Loading model...")
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto" if torch.cuda.is_available() else None,
            trust_remote_code=True
        )

        tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)

        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        device = "cuda" if torch.cuda.is_available() else "cpu"
        if not torch.cuda.is_available():
            model = model.to(device)

        print(f"   ✅ Model loaded on {device}")

        # Test generation
        prompt = model_info['test_prompt']
        print(f"   📝 Test prompt: {prompt}")

        inputs = tokenizer(prompt, return_tensors="pt").to(device)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=50,
                temperature=0.7,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id
            )

        response = tokenizer.decode(outputs[0], skip_special_tokens=True)
        response = response.replace(prompt, "").strip()

        print(f"   💬 Response: {response[:150]}{'...' if len(response) > 150 else ''}")

        # Clean up
        del model
        del tokenizer
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        print("   ✅ Test passed!")
        print()

        return {
            "model": model_name,
            "status": "success",
            "response": response[:200],
            "device": device
        }

    except Exception as e:
        error_msg = str(e)[:100]
        print(f"   ❌ Test failed: {error_msg}")
        print()

        return {
            "model": model_name,
            "status": "failed",
            "error": error_msg
        }

async def test_embedding_model(model_name, model_info):
    """Test an embedding model."""
    print(f"🧪 Testing: {model_name}")
    print(f"   Type: {model_info['type']} | Parameters: {model_info['params']}")

    try:
        from sentence_transformers import SentenceTransformer

        print("   ⏳ Loading model...")
        model = SentenceTransformer(model_name)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model.to(device)

        print(f"   ✅ Model loaded on {device}")

        # Test embeddings
        texts = model_info['test_texts']
        print(f"   📝 Test texts: {texts}")

        embeddings = model.encode(texts)

        print(f"   📊 Embedding shape: {embeddings.shape}")
        print(f"   📊 Embedding dimension: {len(embeddings[0])}")

        # Test similarity
        from sklearn.metrics.pairwise import cosine_similarity
        import numpy as np

        similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
        print(f"   📊 Similarity score: {similarity:.4f}")

        # Clean up
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        print("   ✅ Test passed!")
        print()

        return {
            "model": model_name,
            "status": "success",
            "embedding_dim": len(embeddings[0]),
            "similarity": float(similarity),
            "device": device
        }

    except Exception as e:
        error_msg = str(e)[:100]
        print(f"   ❌ Test failed: {error_msg}")
        print()

        return {
            "model": model_name,
            "status": "failed",
            "error": error_msg
        }

async def test_classification_model(model_name, model_info):
    """Test a classification model."""
    print(f"🧪 Testing: {model_name}")
    print(f"   Type: {model_info['type']} | Parameters: {model_info['params']}")

    try:
        from transformers import pipeline

        print("   ⏳ Loading model...")
        classifier = pipeline("sentiment-analysis", model=model_name, device=0 if torch.cuda.is_available() else -1)

        print(f"   ✅ Model loaded")

        # Test classification
        text = model_info['test_text']
        print(f"   📝 Test text: {text}")

        result = classifier(text)[0]

        print(f"   📊 Label: {result['label']}")
        print(f"   📊 Score: {result['score']:.4f}")

        # Clean up
        del classifier
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        print("   ✅ Test passed!")
        print()

        return {
            "model": model_name,
            "status": "success",
            "label": result['label'],
            "score": float(result['score'])
        }

    except Exception as e:
        error_msg = str(e)[:100]
        print(f"   ❌ Test failed: {error_msg}")
        print()

        return {
            "model": model_name,
            "status": "failed",
            "error": error_msg
        }

# Run tests
async def run_tests():
    for model_name in downloaded_models:
        if model_name not in MODEL_INFO:
            print(f"⏭️  Skipping: {model_name} (no test configuration)")
            test_results["skipped"].append(model_name)
            print()
            continue

        model_info = MODEL_INFO[model_name]

        # Check if model should be tested based on type
        if model_info['type'] == "generative" and model_name not in ["google/flan-t5-large"]:
            result = await test_generative_model(model_name, model_info)

        elif model_info['type'] == "embedding":
            result = await test_embedding_model(model_name, model_info)

        elif model_info['type'] in ["classification", "reranking"]:
            result = await test_classification_model(model_name, model_info)

        else:
            print(f"⏭️  Skipping: {model_name} (unsupported type: {model_info['type']})")
            test_results["skipped"].append(model_name)
            print()
            continue

        # Track results
        if result['status'] == 'success':
            test_results['successful'].append(result)
        else:
            test_results['failed'].append(result)

# Execute tests
try:
    asyncio.run(run_tests())
except KeyboardInterrupt:
    print("\n⚠️  Tests interrupted by user")
except Exception as e:
    print(f"\n❌ Fatal error: {str(e)}")

# Summary
print("=" * 80)
print("TEST SUMMARY")
print("=" * 80)
print()

print(f"✅ Successful: {len(test_results['successful'])}")
for result in test_results['successful']:
    print(f"   ✓ {result['model']}")

print(f"\n❌ Failed: {len(test_results['failed'])}")
for result in test_results['failed']:
    print(f"   ✗ {result['model']}: {result.get('error', 'Unknown error')}")

print(f"\n⏭️  Skipped: {len(test_results['skipped'])}")
for model in test_results['skipped']:
    print(f"   - {model}")

print()
print("=" * 80)
print("RECOMMENDATIONS")
print("=" * 80)
print()

if test_results['successful']:
    print("✅ Recommended models for production use:")
    for result in test_results['successful']:
        model_name = result['model']
        model_info = MODEL_INFO.get(model_name, {})
        capabilities = model_info.get('capabilities', [])
        print(f"   • {model_name}")
        print(f"     Capabilities: {', '.join(capabilities)}")
        print()

print("💡 To use local models in your application:")
print("   1. Load models via: /api/compliance/local-models/load")
print("   2. Generate text: POST /api/compliance/local-models/generate")
print("   3. Create embeddings: POST /api/compliance/local-models/embeddings")
print("   4. View loaded models: GET /api/compliance/local-models/loaded")
print()

print(f"Test Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()
