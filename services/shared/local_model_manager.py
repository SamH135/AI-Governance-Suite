"""Local Model Manager for HuggingFace and GPU-accelerated models."""

import asyncio
import os
import json
import torch
import psutil
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from enum import Enum
import structlog
import numpy as np
from pathlib import Path

# HuggingFace imports
try:
    from transformers import (
        AutoTokenizer, AutoModel, AutoModelForCausalLM, 
        AutoModelForSequenceClassification, pipeline,
        BitsAndBytesConfig
    )
    from sentence_transformers import SentenceTransformer
    import accelerate
    HUGGINGFACE_AVAILABLE = True
except ImportError:
    HUGGINGFACE_AVAILABLE = False

from .redis_client import redis_client
from .exceptions import ValidationError, ExternalServiceError

logger = structlog.get_logger()

class ModelType(Enum):
    """Types of models supported."""
    EMBEDDING = "embedding"
    CLASSIFICATION = "classification"
    GENERATION = "generation"
    RERANKING = "reranking"
    FEATURE_EXTRACTION = "feature_extraction"

class QuantizationType(Enum):
    """Model quantization types."""
    NONE = "none"
    INT8 = "int8"
    INT4 = "int4"
    FP16 = "fp16"
    BF16 = "bf16"

class LocalModelManager:
    """Manager for local HuggingFace models with GPU acceleration."""
    
    def __init__(self):
        self.initialized = False
        self.models = {}
        self.tokenizers = {}
        self.pipelines = {}
        self.device_info = {}
        self.model_cache_dir = Path("./model_cache")
        
    async def initialize(self):
        """Initialize the local model manager."""
        if self.initialized:
            return
            
        try:
            if not HUGGINGFACE_AVAILABLE:
                logger.warning("HuggingFace transformers not available - local models disabled")
                return
            
            # Create model cache directory
            self.model_cache_dir.mkdir(exist_ok=True)
            
            # Detect GPU capabilities
            await self._detect_gpu_capabilities()
            
            # Initialize default models
            await self._initialize_default_models()
            
            self.initialized = True
            logger.info("Local Model Manager initialized successfully", 
                       gpu_available=self.device_info.get("cuda_available", False))
            
        except Exception as e:
            logger.error("Local Model Manager initialization failed", error=str(e))
            raise ExternalServiceError("LocalModelManager", f"Initialization failed: {str(e)}")
    
    async def load_model(
        self,
        model_name: str,
        model_type: ModelType,
        quantization: QuantizationType = QuantizationType.NONE,
        use_gpu: bool = True,
        custom_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """Load a HuggingFace model."""
        
        if not self.initialized:
            await self.initialize()
            
        if not HUGGINGFACE_AVAILABLE:
            raise ExternalServiceError("LocalModelManager", "HuggingFace transformers not available")
        
        try:
            model_key = f"{model_name}_{model_type.value}_{quantization.value}"
            
            if model_key in self.models:
                logger.info("Model already loaded", model_key=model_key)
                return model_key
            
            logger.info("Loading model", model_name=model_name, model_type=model_type.value)
            
            # Determine device
            device = self._get_optimal_device(use_gpu)
            
            # Configure quantization
            quantization_config = self._get_quantization_config(quantization)
            
            # Load model based on type
            if model_type == ModelType.EMBEDDING:
                model = await self._load_embedding_model(model_name, device, quantization_config)
            
            elif model_type == ModelType.CLASSIFICATION:
                model = await self._load_classification_model(model_name, device, quantization_config)
            
            elif model_type == ModelType.GENERATION:
                model = await self._load_generation_model(model_name, device, quantization_config)
            
            elif model_type == ModelType.RERANKING:
                model = await self._load_reranking_model(model_name, device, quantization_config)
            
            else:
                model = await self._load_generic_model(model_name, device, quantization_config)
            
            # Load tokenizer
            tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                cache_dir=str(self.model_cache_dir)
            )
            
            # Store model and tokenizer
            self.models[model_key] = {
                "model": model,
                "model_name": model_name,
                "model_type": model_type,
                "device": device,
                "quantization": quantization,
                "loaded_at": datetime.utcnow(),
                "memory_usage": self._get_model_memory_usage(model)
            }
            
            self.tokenizers[model_key] = tokenizer
            
            # Create pipeline if applicable
            if model_type in [ModelType.CLASSIFICATION, ModelType.GENERATION]:
                pipeline_task = self._get_pipeline_task(model_type)
                if pipeline_task:
                    pipe = pipeline(
                        pipeline_task,
                        model=model,
                        tokenizer=tokenizer,
                        device=device if device != "cpu" else -1
                    )
                    self.pipelines[model_key] = pipe
            
            logger.info("Model loaded successfully", 
                       model_key=model_key,
                       device=device,
                       memory_usage=self.models[model_key]["memory_usage"])
            
            return model_key
            
        except Exception as e:
            logger.error("Model loading failed", model_name=model_name, error=str(e))
            raise ExternalServiceError("LocalModelManager", f"Model loading failed: {str(e)}")
    
    async def generate_embeddings(
        self,
        model_key: str,
        texts: List[str],
        batch_size: int = 32
    ) -> Dict[str, Any]:
        """Generate embeddings using a loaded model."""
        
        if model_key not in self.models:
            raise ValidationError(f"Model {model_key} not loaded")
        
        model_info = self.models[model_key]
        
        if model_info["model_type"] != ModelType.EMBEDDING:
            raise ValidationError(f"Model {model_key} is not an embedding model")
        
        try:
            model = model_info["model"]
            tokenizer = self.tokenizers[model_key]
            device = model_info["device"]
            
            embeddings = []
            
            # Process in batches
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                
                # Tokenize
                inputs = tokenizer(
                    batch_texts,
                    padding=True,
                    truncation=True,
                    return_tensors="pt",
                    max_length=512
                )
                
                # Move to device
                inputs = {k: v.to(device) for k, v in inputs.items()}
                
                # Generate embeddings
                with torch.no_grad():
                    outputs = model(**inputs)
                    
                    # Get embeddings (usually from last_hidden_state)
                    if hasattr(outputs, 'last_hidden_state'):
                        # Mean pooling
                        attention_mask = inputs['attention_mask']
                        token_embeddings = outputs.last_hidden_state
                        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
                        batch_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)
                    else:
                        batch_embeddings = outputs.pooler_output
                    
                    # Normalize embeddings
                    batch_embeddings = torch.nn.functional.normalize(batch_embeddings, p=2, dim=1)
                    
                    embeddings.extend(batch_embeddings.cpu().numpy().tolist())
            
            return {
                "embeddings": embeddings,
                "model_key": model_key,
                "num_texts": len(texts),
                "embedding_dim": len(embeddings[0]) if embeddings else 0
            }
            
        except Exception as e:
            logger.error("Embedding generation failed", model_key=model_key, error=str(e))
            raise ExternalServiceError("LocalModelManager", f"Embedding generation failed: {str(e)}")
    
    async def classify_text(
        self,
        model_key: str,
        texts: List[str],
        return_all_scores: bool = False
    ) -> Dict[str, Any]:
        """Classify text using a loaded classification model."""
        
        if model_key not in self.pipelines:
            raise ValidationError(f"Classification pipeline {model_key} not available")
        
        try:
            pipeline = self.pipelines[model_key]
            
            # Run classification
            results = pipeline(texts, return_all_scores=return_all_scores)
            
            return {
                "results": results,
                "model_key": model_key,
                "num_texts": len(texts)
            }
            
        except Exception as e:
            logger.error("Text classification failed", model_key=model_key, error=str(e))
            raise ExternalServiceError("LocalModelManager", f"Text classification failed: {str(e)}")
    
    async def generate_text(
        self,
        model_key: str,
        prompts: List[str],
        max_length: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        do_sample: bool = True
    ) -> Dict[str, Any]:
        """Generate text using a loaded generation model."""
        
        if model_key not in self.models:
            raise ValidationError(f"Model {model_key} not loaded")
        
        model_info = self.models[model_key]
        
        if model_info["model_type"] != ModelType.GENERATION:
            raise ValidationError(f"Model {model_key} is not a generation model")
        
        try:
            model = model_info["model"]
            tokenizer = self.tokenizers[model_key]
            device = model_info["device"]
            
            generated_texts = []
            
            for prompt in prompts:
                # Tokenize input
                inputs = tokenizer(prompt, return_tensors="pt").to(device)
                
                # Generate
                with torch.no_grad():
                    outputs = model.generate(
                        **inputs,
                        max_length=max_length,
                        temperature=temperature,
                        top_p=top_p,
                        do_sample=do_sample,
                        pad_token_id=tokenizer.eos_token_id
                    )
                
                # Decode output
                generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
                
                # Remove input prompt from output
                if generated_text.startswith(prompt):
                    generated_text = generated_text[len(prompt):].strip()
                
                generated_texts.append(generated_text)
            
            return {
                "generated_texts": generated_texts,
                "model_key": model_key,
                "num_prompts": len(prompts)
            }
            
        except Exception as e:
            logger.error("Text generation failed", model_key=model_key, error=str(e))
            raise ExternalServiceError("LocalModelManager", f"Text generation failed: {str(e)}")
    
    async def rerank_documents(
        self,
        model_key: str,
        query_doc_pairs: List[Tuple[str, str]]
    ) -> Dict[str, Any]:
        """Rerank documents using a cross-encoder model."""
        
        if model_key not in self.models:
            raise ValidationError(f"Model {model_key} not loaded")
        
        model_info = self.models[model_key]
        
        try:
            model = model_info["model"]
            tokenizer = self.tokenizers[model_key]
            device = model_info["device"]
            
            scores = []
            
            for query, doc in query_doc_pairs:
                # Tokenize query-document pair
                inputs = tokenizer(
                    query, doc,
                    padding=True,
                    truncation=True,
                    return_tensors="pt",
                    max_length=512
                ).to(device)
                
                # Get relevance score
                with torch.no_grad():
                    outputs = model(**inputs)
                    score = torch.sigmoid(outputs.logits).cpu().item()
                    scores.append(score)
            
            return {
                "scores": scores,
                "model_key": model_key,
                "num_pairs": len(query_doc_pairs)
            }
            
        except Exception as e:
            logger.error("Document reranking failed", model_key=model_key, error=str(e))
            raise ExternalServiceError("LocalModelManager", f"Document reranking failed: {str(e)}")
    
    async def unload_model(self, model_key: str) -> Dict[str, Any]:
        """Unload a model to free memory."""
        
        try:
            if model_key in self.models:
                model_info = self.models[model_key]
                memory_freed = model_info.get("memory_usage", 0)
                
                # Clear from GPU memory
                if model_info["device"] != "cpu":
                    torch.cuda.empty_cache()
                
                # Remove from memory
                del self.models[model_key]
                
                if model_key in self.tokenizers:
                    del self.tokenizers[model_key]
                
                if model_key in self.pipelines:
                    del self.pipelines[model_key]
                
                logger.info("Model unloaded", model_key=model_key, memory_freed=memory_freed)
                
                return {
                    "success": True,
                    "model_key": model_key,
                    "memory_freed": memory_freed
                }
            else:
                return {"success": False, "message": "Model not found"}
                
        except Exception as e:
            logger.error("Model unloading failed", model_key=model_key, error=str(e))
            return {"success": False, "error": str(e)}
    
    async def get_model_info(self, model_key: Optional[str] = None) -> Dict[str, Any]:
        """Get information about loaded models."""
        
        if model_key:
            if model_key not in self.models:
                raise ValidationError(f"Model {model_key} not loaded")
            
            model_info = self.models[model_key].copy()
            model_info["loaded_at"] = model_info["loaded_at"].isoformat()
            del model_info["model"]  # Don't serialize the actual model
            
            return model_info
        else:
            # Return info for all models
            all_models = {}
            for key, info in self.models.items():
                model_info = info.copy()
                model_info["loaded_at"] = model_info["loaded_at"].isoformat()
                del model_info["model"]
                all_models[key] = model_info
            
            return {
                "loaded_models": all_models,
                "total_models": len(all_models),
                "device_info": self.device_info,
                "total_memory_usage": sum(info.get("memory_usage", 0) for info in self.models.values())
            }
    
    async def get_system_resources(self) -> Dict[str, Any]:
        """Get current system resource usage."""
        
        try:
            # CPU info
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Memory info
            memory = psutil.virtual_memory()
            
            # GPU info
            gpu_info = {}
            if torch.cuda.is_available():
                for i in range(torch.cuda.device_count()):
                    gpu_info[f"gpu_{i}"] = {
                        "name": torch.cuda.get_device_name(i),
                        "memory_allocated": torch.cuda.memory_allocated(i),
                        "memory_reserved": torch.cuda.memory_reserved(i),
                        "memory_total": torch.cuda.get_device_properties(i).total_memory
                    }
            
            return {
                "cpu": {
                    "usage_percent": cpu_percent,
                    "count": cpu_count
                },
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "used": memory.used,
                    "percent": memory.percent
                },
                "gpu": gpu_info,
                "loaded_models": len(self.models)
            }
            
        except Exception as e:
            logger.error("Failed to get system resources", error=str(e))
            return {"error": str(e)}
    
    async def _detect_gpu_capabilities(self):
        """Detect GPU capabilities and configuration."""
        
        self.device_info = {
            "cuda_available": torch.cuda.is_available(),
            "cuda_version": torch.version.cuda if torch.cuda.is_available() else None,
            "device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
            "devices": []
        }
        
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                device_props = torch.cuda.get_device_properties(i)
                self.device_info["devices"].append({
                    "id": i,
                    "name": device_props.name,
                    "total_memory": device_props.total_memory,
                    "major": device_props.major,
                    "minor": device_props.minor,
                    "multi_processor_count": device_props.multi_processor_count
                })
        
        logger.info("GPU capabilities detected", device_info=self.device_info)
    
    def _get_optimal_device(self, use_gpu: bool = True) -> str:
        """Get optimal device for model loading."""
        
        if use_gpu and torch.cuda.is_available():
            # Use GPU with most free memory
            max_free_memory = 0
            best_device = 0
            
            for i in range(torch.cuda.device_count()):
                free_memory = torch.cuda.get_device_properties(i).total_memory - torch.cuda.memory_allocated(i)
                if free_memory > max_free_memory:
                    max_free_memory = free_memory
                    best_device = i
            
            return f"cuda:{best_device}"
        else:
            return "cpu"
    
    def _get_quantization_config(self, quantization: QuantizationType) -> Optional[Any]:
        """Get quantization configuration."""
        
        if quantization == QuantizationType.INT8:
            return BitsAndBytesConfig(load_in_8bit=True)
        elif quantization == QuantizationType.INT4:
            return BitsAndBytesConfig(load_in_4bit=True)
        else:
            return None
    
    async def _load_embedding_model(self, model_name: str, device: str, quantization_config: Any):
        """Load an embedding model."""
        
        try:
            # Try SentenceTransformer first
            model = SentenceTransformer(model_name, cache_folder=str(self.model_cache_dir))
            model.to(device)
            return model
        except:
            # Fallback to AutoModel
            model = AutoModel.from_pretrained(
                model_name,
                cache_dir=str(self.model_cache_dir),
                quantization_config=quantization_config,
                torch_dtype=torch.float16 if device != "cpu" else torch.float32
            )
            model.to(device)
            return model
    
    async def _load_classification_model(self, model_name: str, device: str, quantization_config: Any):
        """Load a classification model."""
        
        model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            cache_dir=str(self.model_cache_dir),
            quantization_config=quantization_config,
            torch_dtype=torch.float16 if device != "cpu" else torch.float32
        )
        model.to(device)
        return model
    
    async def _load_generation_model(self, model_name: str, device: str, quantization_config: Any):
        """Load a text generation model."""
        
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            cache_dir=str(self.model_cache_dir),
            quantization_config=quantization_config,
            torch_dtype=torch.float16 if device != "cpu" else torch.float32
        )
        model.to(device)
        return model
    
    async def _load_reranking_model(self, model_name: str, device: str, quantization_config: Any):
        """Load a reranking model."""
        
        model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            cache_dir=str(self.model_cache_dir),
            quantization_config=quantization_config,
            torch_dtype=torch.float16 if device != "cpu" else torch.float32
        )
        model.to(device)
        return model
    
    async def _load_generic_model(self, model_name: str, device: str, quantization_config: Any):
        """Load a generic model."""
        
        model = AutoModel.from_pretrained(
            model_name,
            cache_dir=str(self.model_cache_dir),
            quantization_config=quantization_config,
            torch_dtype=torch.float16 if device != "cpu" else torch.float32
        )
        model.to(device)
        return model
    
    def _get_pipeline_task(self, model_type: ModelType) -> Optional[str]:
        """Get pipeline task for model type."""
        
        task_map = {
            ModelType.CLASSIFICATION: "text-classification",
            ModelType.GENERATION: "text-generation"
        }
        
        return task_map.get(model_type)
    
    def _get_model_memory_usage(self, model) -> int:
        """Estimate model memory usage."""
        
        try:
            param_count = sum(p.numel() for p in model.parameters())
            # Rough estimate: 4 bytes per parameter for float32, 2 for float16
            return param_count * 2  # Assume float16
        except:
            return 0
    
    async def _initialize_default_models(self):
        """Initialize commonly used default models."""
        
        default_models = [
            {
                "name": "sentence-transformers/all-MiniLM-L6-v2",
                "type": ModelType.EMBEDDING,
                "quantization": QuantizationType.NONE
            }
        ]
        
        for model_config in default_models:
            try:
                await self.load_model(
                    model_name=model_config["name"],
                    model_type=model_config["type"],
                    quantization=model_config["quantization"],
                    use_gpu=True
                )
            except Exception as e:
                logger.warning("Failed to load default model", 
                             model=model_config["name"], error=str(e))
    
    async def close(self):
        """Close the local model manager and free resources."""
        
        try:
            # Unload all models
            for model_key in list(self.models.keys()):
                await self.unload_model(model_key)
            
            # Clear GPU cache
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info("Local Model Manager closed")
            
        except Exception as e:
            logger.error("Local Model Manager close failed", error=str(e))

# Global instance
local_model_manager = LocalModelManager()