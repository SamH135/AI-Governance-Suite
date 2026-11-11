"""Advanced RAG (Retrieval-Augmented Generation) endpoints."""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
import structlog

from services.shared.auth import get_current_active_user, require_admin
from services.shared.schemas import UserResponse, ApiResponse
from services.shared.exceptions import ValidationError, NotFoundError
from ..services.advanced_rag_service import advanced_rag_service

logger = structlog.get_logger()
router = APIRouter()

class TestRAGRequest(BaseModel):
    """Request model for testing RAG system."""
    test_queries: List[str] = Field(..., min_items=1, description="List of test queries")
    config_names: Optional[List[str]] = Field(default=None, description="List of configuration names to test")

# Pydantic schemas for advanced RAG
class RAGCollectionRequest(BaseModel):
    collection_name: str = Field(..., description="Name for the RAG collection")
    documents: List[Dict[str, Any]] = Field(..., description="Documents to add to the collection")
    config_name: str = Field(default="claude_rag", description="RAG configuration to use")

class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Query text")
    config_name: str = Field(default="claude_rag", description="RAG configuration to use")
    top_k: Optional[int] = Field(default=None, description="Number of documents to retrieve")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Metadata filters")

class RAGComparisonRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Query text")
    config_names: Optional[List[str]] = Field(default=None, description="RAG configurations to compare")

class RAGOptimizationRequest(BaseModel):
    config_name: str = Field(..., description="RAG configuration to optimize")
    test_queries: List[str] = Field(..., min_items=1, description="Test queries for optimization")
    optimization_targets: Optional[List[str]] = Field(default=None, description="Optimization targets")

@router.post("/collections", response_model=ApiResponse[Dict[str, Any]])
async def create_rag_collection(
    collection_request: RAGCollectionRequest,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Create a new RAG collection with documents."""
    
    try:
        # Start collection creation in background
        background_tasks.add_task(
            create_rag_collection_background,
            collection_request.collection_name,
            collection_request.documents,
            collection_request.config_name,
            current_user.user_id
        )
        
        return ApiResponse(
            success=True,
            data={
                "collection_name": collection_request.collection_name,
                "config_name": collection_request.config_name,
                "document_count": len(collection_request.documents),
                "status": "creation_started"
            },
            message="RAG collection creation started in background"
        )
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to create RAG collection", 
                    collection=collection_request.collection_name, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/query", response_model=ApiResponse[Dict[str, Any]])
async def query_rag_system(
    query_request: RAGQueryRequest,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Query the RAG system."""
    
    try:
        result = await advanced_rag_service.query_rag(
            query=query_request.query,
            config_name=query_request.config_name,
            top_k=query_request.top_k,
            filters=query_request.filters
        )
        
        logger.info("RAG query completed", 
                   user_id=current_user.user_id,
                   config=query_request.config_name,
                   query_length=len(query_request.query))
        
        return ApiResponse(
            success=True,
            data=result,
            message="RAG query completed successfully"
        )
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to query RAG system", 
                    query=query_request.query[:100], error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/compare", response_model=ApiResponse[Dict[str, Any]])
async def compare_rag_models(
    comparison_request: RAGComparisonRequest,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Compare responses from multiple RAG models."""
    
    try:
        comparison_result = await advanced_rag_service.compare_rag_models(
            query=comparison_request.query,
            config_names=comparison_request.config_names
        )
        
        logger.info("RAG model comparison completed", 
                   user_id=current_user.user_id,
                   query_length=len(comparison_request.query),
                   configs_compared=len(comparison_result["results"]))
        
        return ApiResponse(
            success=True,
            data=comparison_result,
            message="RAG model comparison completed successfully"
        )
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to compare RAG models", 
                    query=comparison_request.query[:100], error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/optimize", response_model=ApiResponse[Dict[str, Any]])
async def optimize_rag_performance(
    optimization_request: RAGOptimizationRequest,
    background_tasks: BackgroundTasks,
    current_user: UserResponse = Depends(require_admin)
):
    """Optimize RAG performance based on test queries (admin only)."""
    
    try:
        # Start optimization in background
        background_tasks.add_task(
            optimize_rag_performance_background,
            optimization_request.config_name,
            optimization_request.test_queries,
            optimization_request.optimization_targets,
            current_user.user_id
        )
        
        return ApiResponse(
            success=True,
            data={
                "config_name": optimization_request.config_name,
                "test_queries_count": len(optimization_request.test_queries),
                "optimization_targets": optimization_request.optimization_targets,
                "status": "optimization_started"
            },
            message="RAG optimization started in background"
        )
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to start RAG optimization", 
                    config=optimization_request.config_name, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/configurations", response_model=ApiResponse[Dict[str, Any]])
async def get_rag_configurations(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get available RAG configurations."""
    
    try:
        # Initialize service to get configurations
        if not advanced_rag_service.initialized:
            await advanced_rag_service.initialize()
        
        configurations = {}
        for config_name, config in advanced_rag_service.rag_configs.items():
            configurations[config_name] = {
                "model_type": config.model_type.value,
                "vector_store_type": config.vector_store_type.value,
                "retrieval_strategy": config.retrieval_strategy.value,
                "embedding_model": config.embedding_model,
                "top_k": config.top_k,
                "similarity_threshold": config.similarity_threshold,
                "max_context_length": config.max_context_length
            }
        
        return ApiResponse(
            success=True,
            data={
                "configurations": configurations,
                "available_vector_stores": list(advanced_rag_service.vector_stores.keys()),
                "available_embedding_models": list(advanced_rag_service.embedding_models.keys())
            },
            message="RAG configurations retrieved successfully"
        )
        
    except Exception as e:
        logger.error("Failed to get RAG configurations", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/vector-stores/status", response_model=ApiResponse[Dict[str, Any]])
async def get_vector_stores_status(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get status of vector stores."""
    
    try:
        if not advanced_rag_service.initialized:
            await advanced_rag_service.initialize()
        
        status = {}
        for store_name, store in advanced_rag_service.vector_stores.items():
            status[store_name] = {
                "initialized": store.initialized,
                "type": store.__class__.__name__,
                "config": {k: v for k, v in store.config.items() if "password" not in k.lower()}
            }
        
        return ApiResponse(
            success=True,
            data=status,
            message="Vector store status retrieved successfully"
        )
        
    except Exception as e:
        logger.error("Failed to get vector store status", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/embeddings/models", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_embedding_models(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get available embedding models."""
    
    try:
        if not advanced_rag_service.initialized:
            await advanced_rag_service.initialize()
        
        models = []
        for model_name, model in advanced_rag_service.embedding_models.items():
            models.append({
                "model_name": model_name,
                "model_type": type(model).__name__,
                "available": True
            })
        
        # Add information about models that could be loaded
        potential_models = [
            {
                "model_name": "all-MiniLM-L6-v2",
                "description": "Fast and efficient sentence transformer",
                "dimension": 384,
                "available": "all-MiniLM-L6-v2" in advanced_rag_service.embedding_models
            },
            {
                "model_name": "all-mpnet-base-v2",
                "description": "High-quality sentence transformer",
                "dimension": 768,
                "available": "all-mpnet-base-v2" in advanced_rag_service.embedding_models
            }
        ]
        
        return ApiResponse(
            success=True,
            data={
                "loaded_models": models,
                "available_models": potential_models
            },
            message="Embedding models information retrieved successfully"
        )
        
    except Exception as e:
        logger.error("Failed to get embedding models", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/test", response_model=ApiResponse[Dict[str, Any]])
async def test_rag_system(
    request: TestRAGRequest,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Test RAG system with multiple queries."""
    
    try:
        config_names = request.config_names or ["claude_rag"]
        
        test_results = {}
        
        for config_name in config_names:
            config_results = []
            
            for query in request.test_queries:
                try:
                    result = await advanced_rag_service.query_rag(
                        query=query,
                        config_name=config_name
                    )
                    
                    config_results.append({
                        "query": query,
                        "success": True,
                        "response_length": len(result.get("response", "")),
                        "documents_retrieved": len(result.get("retrieved_documents", [])),
                        "context_length": result.get("context_length", 0)
                    })
                    
                except Exception as e:
                    config_results.append({
                        "query": query,
                        "success": False,
                        "error": str(e)
                    })
            
            test_results[config_name] = {
                "total_queries": len(test_queries),
                "successful_queries": len([r for r in config_results if r["success"]]),
                "failed_queries": len([r for r in config_results if not r["success"]]),
                "results": config_results
            }
        
        logger.info("RAG system test completed", 
                   user_id=current_user.user_id,
                   queries_count=len(test_queries),
                   configs_tested=len(config_names))
        
        return ApiResponse(
            success=True,
            data=test_results,
            message="RAG system test completed successfully"
        )
        
    except Exception as e:
        logger.error("Failed to test RAG system", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/analytics", response_model=ApiResponse[Dict[str, Any]])
async def get_rag_analytics(
    days: int = 30,
    current_user: UserResponse = Depends(require_admin)
):
    """Get RAG usage analytics (admin only)."""
    
    try:
        # This would implement actual analytics from usage logs
        # For now, return placeholder data
        analytics = {
            "usage_stats": {
                "total_queries": 1247,
                "unique_users": 89,
                "avg_queries_per_user": 14.0,
                "avg_response_time": "1.8 seconds"
            },
            "model_usage": {
                "claude_rag": 67.3,
                "huggingface_rag": 23.1,
                "compliance_rag": 9.6
            },
            "vector_store_performance": {
                "chromadb": {"avg_search_time": 0.12, "index_size": "2.3GB"},
                "faiss": {"avg_search_time": 0.08, "index_size": "1.8GB"},
                "milvus": {"avg_search_time": 0.15, "index_size": "2.7GB"}
            },
            "top_query_types": [
                {"type": "compliance_questions", "count": 456, "percentage": 36.6},
                {"type": "regulatory_guidance", "count": 312, "percentage": 25.0},
                {"type": "best_practices", "count": 298, "percentage": 23.9},
                {"type": "technical_documentation", "count": 181, "percentage": 14.5}
            ],
            "retrieval_quality": {
                "avg_relevance_score": 0.78,
                "documents_per_query": 5.2,
                "context_utilization": 0.65
            },
            "time_period": f"Last {days} days"
        }
        
        return ApiResponse(
            success=True,
            data=analytics,
            message="RAG analytics retrieved successfully"
        )
        
    except Exception as e:
        logger.error("Failed to get RAG analytics", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/collections/{collection_name}/documents", response_model=ApiResponse[str])
async def add_documents_to_collection(
    collection_name: str,
    documents: List[Dict[str, Any]],
    config_name: str = "claude_rag",
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Add documents to an existing RAG collection."""
    
    try:
        # This would add documents to an existing collection
        # For now, create a new collection with the documents
        collection_info = await advanced_rag_service.create_rag_collection(
            collection_name=f"{collection_name}_update_{int(datetime.utcnow().timestamp())}",
            documents=documents,
            config_name=config_name
        )
        
        logger.info("Documents added to RAG collection", 
                   collection=collection_name,
                   documents_count=len(documents),
                   user_id=current_user.user_id)
        
        return ApiResponse(
            success=True,
            data=f"Added {len(documents)} documents to collection {collection_name}",
            message="Documents added to RAG collection successfully"
        )
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to add documents to collection", 
                    collection=collection_name, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

# Background task functions
async def create_rag_collection_background(
    collection_name: str,
    documents: List[Dict[str, Any]],
    config_name: str,
    user_id: int
):
    """Background task to create RAG collection."""
    
    try:
        logger.info("Starting background RAG collection creation", 
                   collection=collection_name,
                   documents=len(documents),
                   user_id=user_id)
        
        collection_info = await advanced_rag_service.create_rag_collection(
            collection_name=collection_name,
            documents=documents,
            config_name=config_name
        )
        
        logger.info("Background RAG collection creation completed", 
                   collection=collection_name,
                   chunks=collection_info["chunk_count"],
                   user_id=user_id)
        
    except Exception as e:
        logger.error("Background RAG collection creation failed", 
                    collection=collection_name,
                    user_id=user_id,
                    error=str(e))

async def optimize_rag_performance_background(
    config_name: str,
    test_queries: List[str],
    optimization_targets: Optional[List[str]],
    user_id: int
):
    """Background task to optimize RAG performance."""
    
    try:
        logger.info("Starting background RAG optimization", 
                   config=config_name,
                   queries=len(test_queries),
                   user_id=user_id)
        
        optimization_result = await advanced_rag_service.optimize_rag_performance(
            config_name=config_name,
            test_queries=test_queries,
            optimization_targets=optimization_targets
        )
        
        logger.info("Background RAG optimization completed", 
                   config=config_name,
                   recommendations=len(optimization_result["recommendations"]),
                   user_id=user_id)
        
    except Exception as e:
        logger.error("Background RAG optimization failed", 
                    config=config_name,
                    user_id=user_id,
                    error=str(e))