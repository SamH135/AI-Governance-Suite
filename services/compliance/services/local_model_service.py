"""
Local HuggingFace Model Service
Comprehensive service for managing and executing local HuggingFace models
"""

import os
import time
import asyncio
import uuid
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import threading
import psutil
import structlog

try:
    import torch
    import transformers
    from transformers import (
        AutoTokenizer, AutoModelForCausalLM, AutoModelForSequenceClassification,
        AutoModelForQuestionAnswering, pipeline, BitsAndBytesConfig
    )
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    torch = None
    transformers = None

try:
    import accelerate
    ACCELERATE_AVAILABLE = True
except ImportError:
    ACCELERATE_AVAILABLE = False

from ...shared.exceptions import ValidationError, ExternalServiceError

logger = structlog.get_logger()

class LocalModelService:
    """Service for managing local HuggingFace models with GPU optimization."""
    
    def __init__(self):
        self.loaded_models: Dict[str, Dict[str, Any]] = {}
        self.model_cache: Dict[str, Any] = {}
        self.model_lock = threading.Lock()
        self.initialized = False
        
        # Model type mappings
        self.model_task_mapping = {
            "text-generation": AutoModelForCausalLM,
            "text-classification": AutoModelForSequenceClassification,
            "question-answering": AutoModelForQuestionAnswering,
            "feature-extraction": "AutoModel",
            "fill-mask": "AutoModelForMaskedLM",
            "token-classification": "AutoModelForTokenClassification"
        }
        
        # Popular models for AI compliance testing
        self.recommended_models = {
            "small": [
                "microsoft/DialoGPT-small",
                "distilbert-base-uncased",
                "microsoft/DialoGPT-medium"
            ],
            "medium": [
                "microsoft/DialoGPT-large",
                "EleutherAI/gpt-neo-1.3B",
                "facebook/opt-1.3b"
            ],
            "large": [
                "EleutherAI/gpt-neo-2.7B",
                "facebook/opt-2.7b",
                "bigscience/bloom-1b7"
            ],
            "classification": [
                "unitary/toxic-bert",
                "martin-ha/toxic-comment-model",
                "textattack/bert-base-uncased-hateful-speech"
            ]
        }
    
    async def initialize(self):
        """Initialize the local model service."""
        if self.initialized:
            return
        
        if not TRANSFORMERS_AVAILABLE:
            logger.warning("Transformers not available - local models disabled")
            raise ExternalServiceError(
                "HuggingFace", 
                "Transformers library not installed. Run: pip install transformers torch"
            )
        
        try:
            # Check GPU availability
            self.device_info = await self._get_device_info()
            logger.info("Local model service initialized", 
                       devices=self.device_info["available_devices"])
            
            self.initialized = True
            
        except Exception as e:
            logger.error("Failed to initialize local model service", error=str(e))
            raise ExternalServiceError("LocalModelService", f"Initialization failed: {str(e)}")
    
    async def get_available_models(self) -> List[str]:
        """Get list of recommended models for AI compliance testing."""
        if not self.initialized:
            await self.initialize()
        
        all_models = []
        for category, models in self.recommended_models.items():
            all_models.extend(models)
        
        return all_models
    
    async def get_loaded_models(self) -> List[Dict[str, Any]]:
        """Get list of currently loaded models."""
        if not self.initialized:
            await self.initialize()
        
        models = []
        with self.model_lock:
            for model_id, model_info in self.loaded_models.items():
                models.append({
                    "model_id": model_id,
                    "model_name": model_info["model_name"],
                    "model_type": model_info["model_type"],
                    "device": model_info["device"],
                    "precision": model_info["precision"],
                    "memory_usage": model_info.get("memory_usage", {}),
                    "is_loaded": True,
                    "load_time": model_info.get("load_time"),
                    "last_used": model_info.get("last_used")
                })
        
        return models
    
    async def load_model(
        self,
        model_name: str,
        model_type: str = "text-generation",
        device: str = "auto",
        precision: str = "float16",
        max_memory: Optional[Dict[str, str]] = None,
        cache_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """Load a HuggingFace model for local execution."""
        if not self.initialized:
            await self.initialize()
        
        start_time = time.time()
        model_id = str(uuid.uuid4())
        
        try:
            logger.info("Loading model", model_name=model_name, model_type=model_type)
            
            # Determine optimal device
            target_device = await self._determine_device(device)
            
            # Configure model loading parameters
            model_kwargs = await self._prepare_model_kwargs(
                precision, target_device, max_memory
            )
            
            # Load tokenizer
            logger.info("Loading tokenizer", model_name=model_name)
            tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                cache_dir=cache_dir,
                trust_remote_code=True
            )
            
            # Handle tokenizer pad token
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
            
            # Load model based on type
            logger.info("Loading model weights", model_name=model_name, device=target_device)
            model = await self._load_model_by_type(
                model_name, model_type, model_kwargs, cache_dir
            )
            
            # Move model to device if needed
            if hasattr(model, 'to') and target_device != "auto":
                model = model.to(target_device)
            
            # Get memory usage
            memory_usage = await self._get_memory_usage(target_device)
            
            # Store model info
            model_info = {
                "model_id": model_id,
                "model_name": model_name,
                "model_type": model_type,
                "model": model,
                "tokenizer": tokenizer,
                "device": target_device,
                "precision": precision,
                "memory_usage": memory_usage,
                "load_time": time.time() - start_time,
                "last_used": datetime.utcnow().isoformat(),
                "loaded_at": datetime.utcnow().isoformat()
            }
            
            with self.model_lock:
                self.loaded_models[model_id] = model_info
            
            logger.info("Model loaded successfully", 
                       model_id=model_id,
                       load_time=model_info["load_time"],
                       device=target_device)
            
            # Return response without actual model/tokenizer objects
            response_info = {k: v for k, v in model_info.items() 
                           if k not in ["model", "tokenizer"]}
            
            return response_info
            
        except Exception as e:
            logger.error("Model loading failed", 
                        model_name=model_name, error=str(e))
            raise ExternalServiceError("ModelLoading", f"Failed to load {model_name}: {str(e)}")
    
    async def run_inference(
        self,
        model_id: str,
        input_text: str,
        generation_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run inference on a loaded model."""
        if not self.initialized:
            await self.initialize()
        
        if model_id not in self.loaded_models:
            raise ValidationError(f"Model {model_id} not loaded")
        
        start_time = time.time()
        
        try:
            with self.model_lock:
                model_info = self.loaded_models[model_id]
                model = model_info["model"]
                tokenizer = model_info["tokenizer"]
                model_type = model_info["model_type"]
            
            logger.info("Running inference", model_id=model_id, model_type=model_type)
            
            # Update last used
            model_info["last_used"] = datetime.utcnow().isoformat()
            
            # Run inference based on model type
            if model_type == "text-generation":
                result = await self._run_text_generation(
                    model, tokenizer, input_text, generation_params
                )
            elif model_type == "text-classification":
                result = await self._run_text_classification(
                    model, tokenizer, input_text, generation_params
                )
            elif model_type == "question-answering":
                result = await self._run_question_answering(
                    model, tokenizer, input_text, generation_params
                )
            else:
                # Use pipeline for other tasks
                result = await self._run_pipeline_inference(
                    model_info["model_name"], model_type, input_text, generation_params
                )
            
            inference_time = time.time() - start_time
            
            response = {
                "model_id": model_id,
                "generated_text": result.get("generated_text", ""),
                "input_text": input_text,
                "generation_info": result.get("generation_info", {}),
                "inference_time": inference_time,
                "tokens_generated": result.get("tokens_generated", 0)
            }
            
            logger.info("Inference completed", 
                       model_id=model_id,
                       inference_time=inference_time,
                       tokens_generated=response["tokens_generated"])
            
            return response
            
        except Exception as e:
            logger.error("Inference failed", model_id=model_id, error=str(e))
            raise ExternalServiceError("ModelInference", f"Inference failed: {str(e)}")
    
    async def unload_model(self, model_id: str) -> bool:
        """Unload a model from memory."""
        if model_id not in self.loaded_models:
            return False
        
        try:
            logger.info("Unloading model", model_id=model_id)
            
            with self.model_lock:
                model_info = self.loaded_models.pop(model_id)
            
            # Clear GPU cache if using CUDA
            if torch and torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info("Model unloaded successfully", model_id=model_id)
            return True
            
        except Exception as e:
            logger.error("Model unload failed", model_id=model_id, error=str(e))
            return False
    
    async def get_system_info(self) -> Dict[str, Any]:
        """Get system information for model execution."""
        if not self.initialized:
            await self.initialize()
        
        info = {
            "transformers_available": TRANSFORMERS_AVAILABLE,
            "accelerate_available": ACCELERATE_AVAILABLE,
            "device_info": self.device_info,
            "memory_info": await self._get_system_memory_info(),
            "loaded_models_count": len(self.loaded_models),
            "python_version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}"
        }
        
        if torch:
            info["torch_version"] = torch.__version__
            info["cuda_available"] = torch.cuda.is_available()
            if torch.cuda.is_available():
                info["cuda_version"] = torch.version.cuda
                info["gpu_count"] = torch.cuda.device_count()
        
        if transformers:
            info["transformers_version"] = transformers.__version__
        
        return info
    
    async def get_model_info(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific model."""
        if model_id not in self.loaded_models:
            return None
        
        with self.model_lock:
            model_info = self.loaded_models[model_id].copy()
        
        # Remove actual model objects from response
        response_info = {k: v for k, v in model_info.items() 
                        if k not in ["model", "tokenizer"]}
        
        # Add current memory usage
        response_info["current_memory_usage"] = await self._get_memory_usage(
            model_info["device"]
        )
        
        return response_info
    
    async def optimize_model(self, model_id: str, optimization_type: str) -> Dict[str, Any]:
        """Optimize a loaded model."""
        if model_id not in self.loaded_models:
            raise ValidationError(f"Model {model_id} not loaded")
        
        try:
            logger.info("Optimizing model", model_id=model_id, optimization_type=optimization_type)
            
            with self.model_lock:
                model_info = self.loaded_models[model_id]
            
            if optimization_type == "memory":
                # Clear cache and optimize memory usage
                if torch and torch.cuda.is_available():
                    torch.cuda.empty_cache()
                
                result = {
                    "optimization_type": "memory",
                    "status": "completed",
                    "memory_after": await self._get_memory_usage(model_info["device"])
                }
            
            elif optimization_type == "speed":
                # Compile model for speed (PyTorch 2.0+)
                if hasattr(torch, "compile") and hasattr(model_info["model"], "to"):
                    try:
                        model_info["model"] = torch.compile(model_info["model"])
                        result = {
                            "optimization_type": "speed", 
                            "status": "compiled",
                            "note": "Model compiled for faster inference"
                        }
                    except Exception as e:
                        result = {
                            "optimization_type": "speed",
                            "status": "failed",
                            "error": str(e)
                        }
                else:
                    result = {
                        "optimization_type": "speed",
                        "status": "not_available",
                        "note": "PyTorch compile not available"
                    }
            
            else:
                raise ValidationError(f"Unknown optimization type: {optimization_type}")
            
            logger.info("Model optimization completed", model_id=model_id, result=result)
            return result
            
        except Exception as e:
            logger.error("Model optimization failed", model_id=model_id, error=str(e))
            raise ExternalServiceError("ModelOptimization", f"Optimization failed: {str(e)}")
    
    async def benchmark_model(self, model_id: str, num_samples: int = 10) -> Dict[str, Any]:
        """Run performance benchmark on a model."""
        if model_id not in self.loaded_models:
            raise ValidationError(f"Model {model_id} not loaded")
        
        try:
            logger.info("Benchmarking model", model_id=model_id, num_samples=num_samples)
            
            model_info = self.loaded_models[model_id]
            
            # Sample test inputs
            test_inputs = [
                "This is a test prompt for benchmarking.",
                "Generate a response to evaluate performance.",
                "How fast can this model process text?",
                "Benchmark test with different length input text to measure latency.",
                "Short test.",
                "Medium length test input for comprehensive benchmarking analysis.",
            ] * (num_samples // 6 + 1)
            
            test_inputs = test_inputs[:num_samples]
            
            times = []
            token_counts = []
            
            for i, test_input in enumerate(test_inputs):
                start_time = time.time()
                
                result = await self.run_inference(
                    model_id, 
                    test_input, 
                    {"max_length": 50, "temperature": 0.7}
                )
                
                inference_time = time.time() - start_time
                times.append(inference_time)
                token_counts.append(result.get("tokens_generated", 0))
                
                logger.debug(f"Benchmark sample {i+1}/{num_samples}", 
                           time=inference_time)
            
            # Calculate statistics
            avg_time = sum(times) / len(times)
            min_time = min(times)
            max_time = max(times)
            avg_tokens = sum(token_counts) / len(token_counts) if token_counts else 0
            tokens_per_second = avg_tokens / avg_time if avg_time > 0 else 0
            
            benchmark_results = {
                "model_id": model_id,
                "num_samples": num_samples,
                "average_time": avg_time,
                "min_time": min_time,
                "max_time": max_time,
                "average_tokens_generated": avg_tokens,
                "tokens_per_second": tokens_per_second,
                "device": model_info["device"],
                "precision": model_info["precision"],
                "timestamp": datetime.utcnow().isoformat()
            }
            
            logger.info("Benchmark completed", 
                       model_id=model_id,
                       avg_time=avg_time,
                       tokens_per_second=tokens_per_second)
            
            return benchmark_results
            
        except Exception as e:
            logger.error("Benchmark failed", model_id=model_id, error=str(e))
            raise ExternalServiceError("ModelBenchmark", f"Benchmark failed: {str(e)}")
    
    # Helper methods
    async def _get_device_info(self) -> Dict[str, Any]:
        """Get available device information."""
        device_info = {
            "cpu_available": True,
            "cuda_available": False,
            "available_devices": ["cpu"],
            "gpu_devices": []
        }
        
        if torch and torch.cuda.is_available():
            device_info["cuda_available"] = True
            device_info["gpu_count"] = torch.cuda.device_count()
            
            for i in range(torch.cuda.device_count()):
                gpu_info = {
                    "id": i,
                    "name": torch.cuda.get_device_name(i),
                    "memory_total": torch.cuda.get_device_properties(i).total_memory,
                    "memory_allocated": torch.cuda.memory_allocated(i),
                    "memory_cached": torch.cuda.memory_reserved(i)
                }
                device_info["gpu_devices"].append(gpu_info)
                device_info["available_devices"].append(f"cuda:{i}")
        
        return device_info
    
    async def _determine_device(self, device: str) -> str:
        """Determine the optimal device for model execution."""
        if device == "auto":
            if torch and torch.cuda.is_available():
                return "cuda:0"
            else:
                return "cpu"
        
        if device.startswith("cuda") and torch and torch.cuda.is_available():
            device_id = int(device.split(":")[1]) if ":" in device else 0
            if device_id < torch.cuda.device_count():
                return device
            else:
                logger.warning(f"CUDA device {device} not available, using CPU")
                return "cpu"
        
        return device
    
    async def _prepare_model_kwargs(
        self, 
        precision: str, 
        device: str, 
        max_memory: Optional[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Prepare model loading arguments."""
        kwargs = {"device_map": "auto" if device.startswith("cuda") else None}
        
        # Set precision
        if precision == "float16" and device.startswith("cuda"):
            kwargs["torch_dtype"] = torch.float16
        elif precision == "float32":
            kwargs["torch_dtype"] = torch.float32
        elif precision in ["int8", "int4"] and device.startswith("cuda"):
            # Use BitsAndBytesConfig for quantization
            if precision == "int8":
                kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
            elif precision == "int4":
                kwargs["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True)
        
        # Set max memory if specified
        if max_memory:
            kwargs["max_memory"] = max_memory
        
        return kwargs
    
    async def _load_model_by_type(
        self,
        model_name: str,
        model_type: str,
        model_kwargs: Dict[str, Any],
        cache_dir: Optional[str]
    ):
        """Load model based on its type."""
        if model_type in self.model_task_mapping:
            model_class = self.model_task_mapping[model_type]
            if isinstance(model_class, type):
                return model_class.from_pretrained(
                    model_name,
                    cache_dir=cache_dir,
                    trust_remote_code=True,
                    **model_kwargs
                )
        
        # Fallback to AutoModel
        from transformers import AutoModel
        return AutoModel.from_pretrained(
            model_name,
            cache_dir=cache_dir,
            trust_remote_code=True,
            **model_kwargs
        )
    
    async def _get_memory_usage(self, device: str) -> Dict[str, Any]:
        """Get memory usage information."""
        memory_info = {}
        
        if device.startswith("cuda") and torch and torch.cuda.is_available():
            device_id = int(device.split(":")[1]) if ":" in device else 0
            memory_info = {
                "allocated": torch.cuda.memory_allocated(device_id),
                "cached": torch.cuda.memory_reserved(device_id),
                "total": torch.cuda.get_device_properties(device_id).total_memory
            }
        else:
            # CPU memory
            memory = psutil.virtual_memory()
            memory_info = {
                "used": memory.used,
                "available": memory.available,
                "total": memory.total,
                "percent": memory.percent
            }
        
        return memory_info
    
    async def _get_system_memory_info(self) -> Dict[str, Any]:
        """Get system memory information."""
        memory = psutil.virtual_memory()
        return {
            "total": memory.total,
            "available": memory.available,
            "used": memory.used,
            "percent": memory.percent
        }
    
    async def _run_text_generation(
        self,
        model,
        tokenizer,
        input_text: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run text generation inference."""
        # Tokenize input
        inputs = tokenizer.encode(input_text, return_tensors="pt")
        if hasattr(model, 'device'):
            inputs = inputs.to(model.device)
        
        # Generate
        with torch.no_grad():
            outputs = model.generate(
                inputs,
                max_length=params.get("max_length", 100),
                temperature=params.get("temperature", 0.7),
                top_p=params.get("top_p", 0.9),
                top_k=params.get("top_k", 50),
                do_sample=params.get("do_sample", True),
                num_return_sequences=params.get("num_return_sequences", 1),
                pad_token_id=tokenizer.eos_token_id
            )
        
        # Decode output
        generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Remove input text from output
        if generated_text.startswith(input_text):
            generated_text = generated_text[len(input_text):].strip()
        
        return {
            "generated_text": generated_text,
            "tokens_generated": len(outputs[0]) - len(inputs[0]),
            "generation_info": {
                "input_length": len(inputs[0]),
                "output_length": len(outputs[0]),
                "parameters_used": params
            }
        }
    
    async def _run_text_classification(
        self,
        model,
        tokenizer,
        input_text: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run text classification inference."""
        inputs = tokenizer(input_text, return_tensors="pt", truncation=True, padding=True)
        if hasattr(model, 'device'):
            inputs = {k: v.to(model.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = model(**inputs)
        
        # Get predictions
        predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
        predicted_class = torch.argmax(predictions, dim=-1).item()
        confidence = predictions[0][predicted_class].item()
        
        return {
            "generated_text": f"Classification: {predicted_class} (confidence: {confidence:.3f})",
            "tokens_generated": 0,
            "generation_info": {
                "predicted_class": predicted_class,
                "confidence": confidence,
                "all_scores": predictions[0].tolist()
            }
        }
    
    async def _run_question_answering(
        self,
        model,
        tokenizer,
        input_text: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run question answering inference."""
        # Assume input format: "Question: ... Context: ..."
        parts = input_text.split("Context:")
        if len(parts) != 2:
            question = input_text
            context = "No context provided."
        else:
            question = parts[0].replace("Question:", "").strip()
            context = parts[1].strip()
        
        inputs = tokenizer(question, context, return_tensors="pt", truncation=True)
        if hasattr(model, 'device'):
            inputs = {k: v.to(model.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = model(**inputs)
        
        # Get answer span
        start_scores = outputs.start_logits
        end_scores = outputs.end_logits
        
        start_idx = torch.argmax(start_scores)
        end_idx = torch.argmax(end_scores)
        
        if end_idx < start_idx:
            answer = "Unable to find answer"
        else:
            answer_tokens = inputs["input_ids"][0][start_idx:end_idx+1]
            answer = tokenizer.decode(answer_tokens, skip_special_tokens=True)
        
        return {
            "generated_text": answer,
            "tokens_generated": len(answer.split()),
            "generation_info": {
                "question": question,
                "context": context,
                "start_score": start_scores[0][start_idx].item(),
                "end_score": end_scores[0][end_idx].item()
            }
        }
    
    async def _run_pipeline_inference(
        self,
        model_name: str,
        task: str,
        input_text: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run inference using HuggingFace pipeline."""
        pipe = pipeline(task, model=model_name)
        
        # Adjust parameters based on task
        if task == "text-generation":
            result = pipe(input_text, max_length=params.get("max_length", 100))
            generated = result[0]["generated_text"]
            if generated.startswith(input_text):
                generated = generated[len(input_text):].strip()
        else:
            result = pipe(input_text)
            generated = str(result)
        
        return {
            "generated_text": generated,
            "tokens_generated": len(generated.split()),
            "generation_info": {"pipeline_result": result}
        }

# Global service instance
local_model_service = LocalModelService()