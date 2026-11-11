"""Local model management with HuggingFace integration and GPU acceleration."""

import os
import asyncio
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
import structlog
import torch
from transformers import (
    AutoTokenizer, AutoModel, AutoModelForCausalLM, 
    pipeline, Pipeline, BitsAndBytesConfig
)
from sentence_transformers import SentenceTransformer
import psutil
import GPUtil

from .exceptions import ExternalServiceError, ValidationError

logger = structlog.get_logger()

class LocalModelManager:
    """Manager for local AI models with GPU acceleration and optimization."""
    
    def __init__(self):
        self.models: Dict[str, Any] = {}
        self.tokenizers: Dict[str, Any] = {}
        self.pipelines: Dict[str, Pipeline] = {}
        self.embedding_models: Dict[str, SentenceTransformer] = {}
        self.device_info = None
        self.model_cache_dir = Path(os.getenv("MODEL_CACHE_DIR", "./models"))
        self.initialized = False
        
    async def initialize(self):
        """Initialize the local model manager."""
        
        if self.initialized:
            return
            
        try:
            # Create model cache directory
            self.model_cache_dir.mkdir(parents=True, exist_ok=True)
            
            # Detect available hardware
            self.device_info = await self._detect_hardware()
            
            # Set up model configurations
            self._setup_model_configs()
            
            self.initialized = True
            logger.info("Local model manager initialized", 
                       device_info=self.device_info)
            
        except Exception as e:
            logger.error("Failed to initialize local model manager", error=str(e))
            raise ExternalServiceError("LocalModelManager", f"Initialization failed: {str(e)}")
    
    async def _detect_hardware(self) -> Dict[str, Any]:
        """Detect available hardware for model execution."""
        
        device_info = {
            "cpu_count": psutil.cpu_count(),
            "memory_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "cuda_available": torch.cuda.is_available(),
            "cuda_devices": [],
            "mps_available": torch.backends.mps.is_available() if hasattr(torch.backends, 'mps') else False,
            "recommended_device": "cpu"
        }
        
        # Check CUDA GPUs
        if device_info["cuda_available"]:
            try:
                gpus = GPUtil.getGPUs()
                for gpu in gpus:
                    device_info["cuda_devices"].append({
                        "id": gpu.id,
                        "name": gpu.name,
                        "memory_total": gpu.memoryTotal,
                        "memory_free": gpu.memoryFree,
                        "memory_used": gpu.memoryUsed,
                        "load": gpu.load
                    })
                
                if gpus:
                    device_info["recommended_device"] = f"cuda:{gpus[0].id}"
                    
            except Exception as e:
                logger.warning("Failed to get GPU information", error=str(e))
        
        # Check MPS (Apple Silicon)
        elif device_info["mps_available"]:
            device_info["recommended_device"] = "mps"
        
        return device_info
    
    def _setup_model_configs(self):
        """Set up model configurations based on available hardware."""
        
        self.model_configs = {
            "small": {
                "max_memory_gb": 4,
                "quantization": "8bit",
                "models": [
                    "microsoft/DialoGPT-small",
                    "distilbert-base-uncased",
                    "sentence-transformers/all-MiniLM-L6-v2"
                ]
            },
            "medium": {
                "max_memory_gb": 8,
                "quantization": "8bit",
                "models": [
                    "microsoft/DialoGPT-medium",
                    "bert-base-uncased",
                    "sentence-transformers/all-mpnet-base-v2"
                ]
            },
            "large": {
                "max_memory_gb": 16,
                "quantization": "4bit",
                "models": [
                    "microsoft/DialoGPT-large",
                    "bert-large-uncased",
                    "sentence-transformers/all-roberta-large-v1"
                ]
            }
        }
    
    async def load_model(
        self, 
        model_name: str, 
        model_type: str = "causal_lm",
        quantization: Optional[str] = None,
        device: Optional[str] = None
    ) -> str:
        """Load a model with optimization."""
        
        if not self.initialized:
            await self.initialize()
        
        model_key = f"{model_name}_{model_type}"
        
        if model_key in self.models:
            logger.info("Model already loaded", model_name=model_name)
            return model_key
        
        try:
            device = device or self.device_info["recommended_device"]
            
            logger.info("Loading model", 
                       model_name=model_name, 
                       model_type=model_type,
                       device=device)
            
            # Configure quantization if specified
            quantization_config = None
            if quantization:
                quantization_config = self._get_quantization_config(quantization)
            
            # Load tokenizer
            tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                cache_dir=str(self.model_cache_dir),
                trust_remote_code=True
            )
            
            # Add padding token if missing
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
            
            # Load model based on type
            if model_type == "causal_lm":
                model = AutoModelForCausalLM.from_pretrained(
                    model_name,
                    cache_dir=str(self.model_cache_dir),
                    quantization_config=quantization_config,
                    device_map="auto" if device.startswith("cuda") else None,
                    trust_remote_code=True,
                    torch_dtype=torch.float16 if device != "cpu" else torch.float32
                )
            elif model_type == "embedding":
                model = SentenceTransformer(
                    model_name,
                    cache_folder=str(self.model_cache_dir),
                    device=device
                )
                self.embedding_models[model_key] = model
                return model_key
            else:
                model = AutoModel.from_pretrained(
                    model_name,
                    cache_dir=str(self.model_cache_dir),
                    quantization_config=quantization_config,
                    device_map="auto" if device.startswith("cuda") else None,
                    trust_remote_code=True
                )
            
            # Move model to device if not using device_map
            if not device.startswith("cuda") or quantization_config is None:
                model = model.to(device)
            
            # Store model and tokenizer
            self.models[model_key] = model
            self.tokenizers[model_key] = tokenizer
            
            logger.info("Model loaded successfully", 
                       model_name=model_name,
                       model_key=model_key,
                       device=device)
            
            return model_key
            
        except Exception as e:
            logger.error("Failed to load model", 
                        model_name=model_name, error=str(e))
            raise ExternalServiceError("LocalModelManager", f"Model loading failed: {str(e)}")
    
    def _get_quantization_config(self, quantization: str) -> Optional[BitsAndBytesConfig]:
        """Get quantization configuration."""
        
        if quantization == "4bit":
            return BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True
            )
        elif quantization == "8bit":
            return BitsAndBytesConfig(
                load_in_8bit=True,
                llm_int8_threshold=6.0
            )
        
        return None
    
    async def create_pipeline(
        self,
        model_key: str,
        task: str,
        **kwargs
    ) -> str:
        """Create a pipeline for a loaded model."""
        
        if model_key not in self.models:
            raise ValidationError(f"Model {model_key} not loaded")
        
        pipeline_key = f"{model_key}_{task}"
        
        if pipeline_key in self.pipelines:
            return pipeline_key
        
        try:
            model = self.models[model_key]
            tokenizer = self.tokenizers[model_key]
            
            pipe = pipeline(
                task,
                model=model,
                tokenizer=tokenizer,
                **kwargs
            )
            
            self.pipelines[pipeline_key] = pipe
            
            logger.info("Pipeline created", 
                       model_key=model_key,
                       task=task,
                       pipeline_key=pipeline_key)
            
            return pipeline_key
            
        except Exception as e:
            logger.error("Failed to create pipeline", 
                        model_key=model_key, task=task, error=str(e))
            raise ExternalServiceError("LocalModelManager", f"Pipeline creation failed: {str(e)}")
    
    async def generate_text(
        self,
        model_key: str,
        prompt: str,
        max_length: int = 100,
        temperature: float = 0.7,
        do_sample: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate text using a loaded model."""
        
        if model_key not in self.models:
            raise ValidationError(f"Model {model_key} not loaded")
        
        try:
            model = self.models[model_key]
            tokenizer = self.tokenizers[model_key]
            
            # Tokenize input
            inputs = tokenizer.encode(prompt, return_tensors="pt")
            inputs = inputs.to(model.device)
            
            # Generate
            with torch.no_grad():
                outputs = model.generate(
                    inputs,
                    max_length=max_length,
                    temperature=temperature,
                    do_sample=do_sample,
                    pad_token_id=tokenizer.eos_token_id,
                    **kwargs
                )
            
            # Decode output
            generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Remove input prompt from output
            if generated_text.startswith(prompt):
                generated_text = generated_text[len(prompt):].strip()
            
            return {
                "generated_text": generated_text,
                "input_length": len(inputs[0]),
                "output_length": len(outputs[0]),
                "model_key": model_key
            }
            
        except Exception as e:
            logger.error("Text generation failed", 
                        model_key=model_key, error=str(e))
            raise ExternalServiceError("LocalModelManager", f"Text generation failed: {str(e)}")
    
    async def generate_embeddings(
        self,
        model_key: str,
        texts: Union[str, List[str]]
    ) -> Dict[str, Any]:
        """Generate embeddings using a loaded embedding model."""
        
        if model_key not in self.embedding_models:
            raise ValidationError(f"Embedding model {model_key} not loaded")
        
        try:
            model = self.embedding_models[model_key]
            
            # Ensure texts is a list
            if isinstance(texts, str):
                texts = [texts]
            
            # Generate embeddings
            embeddings = model.encode(texts, convert_to_tensor=True)
            
            # Convert to list for JSON serialization
            embeddings_list = embeddings.cpu().numpy().tolist()
            
            return {
                "embeddings": embeddings_list,
                "dimension": len(embeddings_list[0]) if embeddings_list else 0,
                "count": len(embeddings_list),
                "model_key": model_key
            }
            
        except Exception as e:
            logger.error("Embedding generation failed", 
                        model_key=model_key, error=str(e))
            raise ExternalServiceError("LocalModelManager", f"Embedding generation failed: {str(e)}")
    
    async def run_pipeline(
        self,
        pipeline_key: str,
        inputs: Any,
        **kwargs
    ) -> Dict[str, Any]:
        """Run a pipeline with given inputs."""
        
        if pipeline_key not in self.pipelines:
            raise ValidationError(f"Pipeline {pipeline_key} not found")
        
        try:
            pipe = self.pipelines[pipeline_key]
            
            # Run pipeline
            results = pipe(inputs, **kwargs)
            
            return {
                "results": results,
                "pipeline_key": pipeline_key,
                "input_type": type(inputs).__name__
            }
            
        except Exception as e:
            logger.error("Pipeline execution failed", 
                        pipeline_key=pipeline_key, error=str(e))
            raise ExternalServiceError("LocalModelManager", f"Pipeline execution failed: {str(e)}")
    
    async def unload_model(self, model_key: str) -> bool:
        """Unload a model to free memory."""
        
        try:
            # Remove from models
            if model_key in self.models:
                del self.models[model_key]
            
            # Remove tokenizer
            if model_key in self.tokenizers:
                del self.tokenizers[model_key]
            
            # Remove embedding model
            if model_key in self.embedding_models:
                del self.embedding_models[model_key]
            
            # Remove related pipelines
            pipelines_to_remove = [
                key for key in self.pipelines.keys() 
                if key.startswith(model_key)
            ]
            
            for pipeline_key in pipelines_to_remove:
                del self.pipelines[pipeline_key]
            
            # Clear GPU cache if using CUDA
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info("Model unloaded", model_key=model_key)
            return True
            
        except Exception as e:
            logger.error("Failed to unload model", 
                        model_key=model_key, error=str(e))
            return False
    
    async def get_model_info(self, model_key: str) -> Dict[str, Any]:
        """Get information about a loaded model."""
        
        info = {
            "model_key": model_key,
            "loaded": False,
            "type": "unknown",
            "device": "unknown",
            "memory_usage": 0
        }
        
        if model_key in self.models:
            model = self.models[model_key]
            info.update({
                "loaded": True,
                "type": "transformer",
                "device": str(model.device),
                "parameters": sum(p.numel() for p in model.parameters()),
                "trainable_parameters": sum(p.numel() for p in model.parameters() if p.requires_grad)
            })
        
        elif model_key in self.embedding_models:
            model = self.embedding_models[model_key]
            info.update({
                "loaded": True,
                "type": "embedding",
                "device": str(model.device),
                "max_seq_length": getattr(model, 'max_seq_length', 'unknown')
            })
        
        return info
    
    async def list_loaded_models(self) -> Dict[str, Any]:
        """List all loaded models and their information."""
        
        loaded_models = {
            "transformer_models": list(self.models.keys()),
            "embedding_models": list(self.embedding_models.keys()),
            "pipelines": list(self.pipelines.keys()),
            "total_models": len(self.models) + len(self.embedding_models),
            "device_info": self.device_info
        }
        
        return loaded_models
    
    async def get_memory_usage(self) -> Dict[str, Any]:
        """Get current memory usage information."""
        
        memory_info = {
            "system_memory": {
                "total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
                "available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
                "used_percent": psutil.virtual_memory().percent
            }
        }
        
        # Add GPU memory info if available
        if torch.cuda.is_available():
            gpu_memory = {}
            for i in range(torch.cuda.device_count()):
                gpu_memory[f"cuda:{i}"] = {
                    "allocated_gb": round(torch.cuda.memory_allocated(i) / (1024**3), 2),
                    "reserved_gb": round(torch.cuda.memory_reserved(i) / (1024**3), 2),
                    "max_allocated_gb": round(torch.cuda.max_memory_allocated(i) / (1024**3), 2)
                }
            memory_info["gpu_memory"] = gpu_memory
        
        return memory_info
    
    async def optimize_model_loading(self, available_memory_gb: float) -> List[str]:
        """Recommend models based on available memory."""
        
        recommendations = []
        
        for size, config in self.model_configs.items():
            if available_memory_gb >= config["max_memory_gb"]:
                recommendations.extend([
                    {
                        "model": model,
                        "size": size,
                        "estimated_memory": config["max_memory_gb"],
                        "quantization": config["quantization"]
                    }
                    for model in config["models"]
                ])
        
        return recommendations

# Global local model manager instance
local_model_manager = LocalModelManager()