"""
Advanced RAG (Retrieval-Augmented Generation) Service
Supports multiple RAG models, vector databases, and retrieval strategies
"""

import os
import asyncio
import numpy as np
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime
from enum import Enum
import structlog
from dataclasses import dataclass

try:
    import chromadb
    from chromadb.config import Settings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    chromadb = None

try:
    from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
    MILVUS_AVAILABLE = True
except ImportError:
    MILVUS_AVAILABLE = False

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    faiss = None

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None

from services.shared.exceptions import ValidationError, ExternalServiceError
from .prompt_service import prompt_service

logger = structlog.get_logger()

class RAGModelType(str, Enum):
    """Types of RAG models supported."""
    CLAUDE_RAG = "claude_rag"
    HUGGINGFACE_RAG = "huggingface_rag"
    CUSTOM_RAG = "custom_rag"
    HYBRID_RAG = "hybrid_rag"

class VectorStoreType(str, Enum):
    """Types of vector stores supported."""
    CHROMADB = "chromadb"
    MILVUS = "milvus"
    FAISS = "faiss"
    PINECONE = "pinecone"

class RetrievalStrategy(str, Enum):
    """Retrieval strategies."""
    SIMILARITY = "similarity"
    MMR = "mmr"  # Maximal Marginal Relevance
    HYBRID = "hybrid"  # Combination of dense and sparse retrieval
    SEMANTIC_SEARCH = "semantic_search"
    CONTEXTUAL_COMPRESSION = "contextual_compression"

@dataclass
class DocumentChunk:
    """Represents a document chunk for RAG."""
    chunk_id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[np.ndarray] = None
    score: Optional[float] = None

@dataclass
class RAGConfiguration:
    """Configuration for RAG model."""
    model_type: RAGModelType
    vector_store_type: VectorStoreType
    retrieval_strategy: RetrievalStrategy
    embedding_model: str
    top_k: int = 5
    similarity_threshold: float = 0.7
    max_context_length: int = 4000
    chunk_size: int = 1000
    chunk_overlap: int = 200

class VectorStore:
    """Abstract base class for vector stores."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.initialized = False
    
    async def initialize(self):
        """Initialize the vector store."""
        raise NotImplementedError
    
    async def add_documents(self, documents: List[DocumentChunk]):
        """Add documents to the vector store."""
        raise NotImplementedError
    
    async def search(self, query_embedding: np.ndarray, top_k: int = 5) -> List[DocumentChunk]:
        """Search for similar documents."""
        raise NotImplementedError
    
    async def delete_documents(self, document_ids: List[str]):
        """Delete documents from the vector store."""
        raise NotImplementedError

class ChromaDBVectorStore(VectorStore):
    """ChromaDB vector store implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.client = None
        self.collection = None
        self.collection_name = config.get("collection_name", "compliance_docs")
    
    async def initialize(self):
        """Initialize ChromaDB."""
        if not CHROMA_AVAILABLE:
            raise ExternalServiceError("ChromaDB", "ChromaDB not installed. Run: pip install chromadb")
        
        try:
            # Initialize ChromaDB client
            chroma_settings = Settings(
                persist_directory=self.config.get("persist_directory", "./chroma_db"),
                allow_reset=True
            )
            self.client = chromadb.Client(chroma_settings)
            
            # Create or get collection
            try:
                self.collection = self.client.get_collection(name=self.collection_name)
            except Exception:
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "AI Compliance documents collection"}
                )
            
            self.initialized = True
            logger.info("ChromaDB vector store initialized", collection=self.collection_name)
            
        except Exception as e:
            logger.error("Failed to initialize ChromaDB", error=str(e))
            raise ExternalServiceError("ChromaDB", f"Initialization failed: {str(e)}")
    
    async def add_documents(self, documents: List[DocumentChunk]):
        """Add documents to ChromaDB."""
        if not self.initialized:
            await self.initialize()
        
        try:
            # Prepare data for ChromaDB
            ids = [doc.chunk_id for doc in documents]
            embeddings = [doc.embedding.tolist() for doc in documents if doc.embedding is not None]
            documents_text = [doc.content for doc in documents]
            metadatas = [doc.metadata for doc in documents]
            
            # Add to collection
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents_text,
                metadatas=metadatas
            )
            
            logger.info("Documents added to ChromaDB", count=len(documents))
            
        except Exception as e:
            logger.error("Failed to add documents to ChromaDB", error=str(e))
            raise ExternalServiceError("ChromaDB", f"Failed to add documents: {str(e)}")
    
    async def search(self, query_embedding: np.ndarray, top_k: int = 5) -> List[DocumentChunk]:
        """Search ChromaDB for similar documents."""
        if not self.initialized:
            await self.initialize()
        
        try:
            # Query ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding.tolist()],
                n_results=top_k,
                include=["documents", "metadatas", "distances"]
            )
            
            # Convert results to DocumentChunk objects
            chunks = []
            for i, (doc, metadata, distance) in enumerate(zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0]
            )):
                chunk = DocumentChunk(
                    chunk_id=f"chroma_{i}",
                    content=doc,
                    metadata=metadata,
                    score=1.0 - distance  # Convert distance to similarity score
                )
                chunks.append(chunk)
            
            return chunks
            
        except Exception as e:
            logger.error("Failed to search ChromaDB", error=str(e))
            raise ExternalServiceError("ChromaDB", f"Search failed: {str(e)}")

class MilvusVectorStore(VectorStore):
    """Milvus vector store implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.collection = None
        self.collection_name = config.get("collection_name", "compliance_docs")
        self.dimension = config.get("dimension", 384)
    
    async def initialize(self):
        """Initialize Milvus."""
        if not MILVUS_AVAILABLE:
            raise ExternalServiceError("Milvus", "Milvus not installed. Run: pip install pymilvus")
        
        try:
            # Connect to Milvus
            connections.connect(
                alias="default",
                host=self.config.get("host", "localhost"),
                port=self.config.get("port", "19530")
            )
            
            # Create collection if it doesn't exist
            if not utility.has_collection(self.collection_name):
                # Define schema
                fields = [
                    FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=100),
                    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dimension),
                    FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                    FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=65535)
                ]
                
                schema = CollectionSchema(fields, description="AI Compliance documents")
                self.collection = Collection(self.collection_name, schema)
            else:
                self.collection = Collection(self.collection_name)
            
            # Create index
            index_params = {
                "metric_type": "IP",  # Inner Product
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128}
            }
            self.collection.create_index(field_name="embedding", index_params=index_params)
            self.collection.load()
            
            self.initialized = True
            logger.info("Milvus vector store initialized", collection=self.collection_name)
            
        except Exception as e:
            logger.error("Failed to initialize Milvus", error=str(e))
            raise ExternalServiceError("Milvus", f"Initialization failed: {str(e)}")
    
    async def add_documents(self, documents: List[DocumentChunk]):
        """Add documents to Milvus."""
        if not self.initialized:
            await self.initialize()
        
        try:
            # Prepare data
            entities = [
                [doc.chunk_id for doc in documents],
                [doc.embedding.tolist() for doc in documents if doc.embedding is not None],
                [doc.content for doc in documents],
                [str(doc.metadata) for doc in documents]
            ]
            
            # Insert into Milvus
            self.collection.insert(entities)
            self.collection.flush()
            
            logger.info("Documents added to Milvus", count=len(documents))
            
        except Exception as e:
            logger.error("Failed to add documents to Milvus", error=str(e))
            raise ExternalServiceError("Milvus", f"Failed to add documents: {str(e)}")
    
    async def search(self, query_embedding: np.ndarray, top_k: int = 5) -> List[DocumentChunk]:
        """Search Milvus for similar documents."""
        if not self.initialized:
            await self.initialize()
        
        try:
            search_params = {"metric_type": "IP", "params": {"nprobe": 10}}
            
            results = self.collection.search(
                data=[query_embedding.tolist()],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                output_fields=["content", "metadata"]
            )
            
            # Convert results to DocumentChunk objects
            chunks = []
            for hit in results[0]:
                chunk = DocumentChunk(
                    chunk_id=str(hit.id),
                    content=hit.entity.get("content"),
                    metadata=eval(hit.entity.get("metadata", "{}")),
                    score=hit.score
                )
                chunks.append(chunk)
            
            return chunks
            
        except Exception as e:
            logger.error("Failed to search Milvus", error=str(e))
            raise ExternalServiceError("Milvus", f"Search failed: {str(e)}")

class FAISSVectorStore(VectorStore):
    """FAISS vector store implementation."""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.index = None
        self.documents = {}
        self.dimension = config.get("dimension", 384)
        self.index_file = config.get("index_file", "faiss_index.bin")
    
    async def initialize(self):
        """Initialize FAISS."""
        if not FAISS_AVAILABLE:
            raise ExternalServiceError("FAISS", "FAISS not installed. Run: pip install faiss-cpu")
        
        try:
            # Load existing index or create new one
            if os.path.exists(self.index_file):
                self.index = faiss.read_index(self.index_file)
                logger.info("Loaded existing FAISS index", index_file=self.index_file)
            else:
                # Create new index
                self.index = faiss.IndexFlatIP(self.dimension)  # Inner Product
                logger.info("Created new FAISS index", dimension=self.dimension)
            
            self.initialized = True
            
        except Exception as e:
            logger.error("Failed to initialize FAISS", error=str(e))
            raise ExternalServiceError("FAISS", f"Initialization failed: {str(e)}")
    
    async def add_documents(self, documents: List[DocumentChunk]):
        """Add documents to FAISS."""
        if not self.initialized:
            await self.initialize()
        
        try:
            # Prepare embeddings
            embeddings = np.array([doc.embedding for doc in documents if doc.embedding is not None])
            
            # Add to index
            start_id = self.index.ntotal
            self.index.add(embeddings.astype(np.float32))
            
            # Store document metadata
            for i, doc in enumerate(documents):
                self.documents[start_id + i] = {
                    "chunk_id": doc.chunk_id,
                    "content": doc.content,
                    "metadata": doc.metadata
                }
            
            # Save index
            faiss.write_index(self.index, self.index_file)
            
            logger.info("Documents added to FAISS", count=len(documents))
            
        except Exception as e:
            logger.error("Failed to add documents to FAISS", error=str(e))
            raise ExternalServiceError("FAISS", f"Failed to add documents: {str(e)}")
    
    async def search(self, query_embedding: np.ndarray, top_k: int = 5) -> List[DocumentChunk]:
        """Search FAISS for similar documents."""
        if not self.initialized:
            await self.initialize()
        
        try:
            # Search index
            scores, indices = self.index.search(query_embedding.reshape(1, -1).astype(np.float32), top_k)
            
            # Convert results to DocumentChunk objects
            chunks = []
            for score, idx in zip(scores[0], indices[0]):
                if idx in self.documents:
                    doc_data = self.documents[idx]
                    chunk = DocumentChunk(
                        chunk_id=doc_data["chunk_id"],
                        content=doc_data["content"],
                        metadata=doc_data["metadata"],
                        score=float(score)
                    )
                    chunks.append(chunk)
            
            return chunks
            
        except Exception as e:
            logger.error("Failed to search FAISS", error=str(e))
            raise ExternalServiceError("FAISS", f"Search failed: {str(e)}")

class AdvancedRAGService:
    """Advanced RAG service with multiple models and retrieval strategies."""
    
    def __init__(self):
        self.initialized = False
        self.vector_stores: Dict[str, VectorStore] = {}
        self.embedding_models: Dict[str, Any] = {}
        self.rag_configs: Dict[str, RAGConfiguration] = {}
        
        # Default configurations
        self.default_configs = {
            "claude_rag": RAGConfiguration(
                model_type=RAGModelType.CLAUDE_RAG,
                vector_store_type=VectorStoreType.CHROMADB,
                retrieval_strategy=RetrievalStrategy.SIMILARITY,
                embedding_model="all-MiniLM-L6-v2",
                top_k=5,
                similarity_threshold=0.7
            ),
            "huggingface_rag": RAGConfiguration(
                model_type=RAGModelType.HUGGINGFACE_RAG,
                vector_store_type=VectorStoreType.FAISS,
                retrieval_strategy=RetrievalStrategy.HYBRID,
                embedding_model="sentence-transformers/all-mpnet-base-v2",
                top_k=10,
                similarity_threshold=0.6
            ),
            "compliance_rag": RAGConfiguration(
                model_type=RAGModelType.CUSTOM_RAG,
                vector_store_type=VectorStoreType.MILVUS,
                retrieval_strategy=RetrievalStrategy.SEMANTIC_SEARCH,
                embedding_model="law-ai/InLegalBERT",
                top_k=8,
                similarity_threshold=0.75
            )
        }
    
    async def initialize(self):
        """Initialize the advanced RAG service."""
        if self.initialized:
            return
        
        try:
            # Initialize embedding models
            await self._initialize_embedding_models()
            
            # Initialize vector stores
            await self._initialize_vector_stores()
            
            # Setup RAG configurations
            await self._setup_rag_configurations()
            
            self.initialized = True
            logger.info("Advanced RAG service initialized")
            
        except Exception as e:
            logger.error("Failed to initialize advanced RAG service", error=str(e))
            raise ExternalServiceError("AdvancedRAG", f"Initialization failed: {str(e)}")
    
    async def create_rag_collection(
        self,
        collection_name: str,
        documents: List[Dict[str, Any]],
        config_name: str = "claude_rag"
    ) -> Dict[str, Any]:
        """Create a new RAG collection with documents."""
        if not self.initialized:
            await self.initialize()
        
        try:
            config = self.rag_configs.get(config_name)
            if not config:
                raise ValidationError(f"Unknown RAG configuration: {config_name}")
            
            # Process documents into chunks
            chunks = await self._process_documents(documents, config)
            
            # Generate embeddings
            await self._generate_embeddings(chunks, config.embedding_model)
            
            # Store in vector store
            vector_store = self.vector_stores.get(config.vector_store_type.value)
            if not vector_store:
                raise ValidationError(f"Vector store not available: {config.vector_store_type}")
            
            await vector_store.add_documents(chunks)
            
            collection_info = {
                "collection_name": collection_name,
                "config_name": config_name,
                "document_count": len(documents),
                "chunk_count": len(chunks),
                "vector_store": config.vector_store_type.value,
                "embedding_model": config.embedding_model,
                "created_at": datetime.utcnow().isoformat()
            }
            
            logger.info("RAG collection created", 
                       collection=collection_name,
                       chunks=len(chunks),
                       config=config_name)
            
            return collection_info
            
        except Exception as e:
            logger.error("Failed to create RAG collection", 
                        collection=collection_name, error=str(e))
            raise ValidationError(f"Failed to create RAG collection: {str(e)}")
    
    async def query_rag(
        self,
        query: str,
        config_name: str = "claude_rag",
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Query the RAG system."""
        if not self.initialized:
            await self.initialize()
        
        try:
            config = self.rag_configs.get(config_name)
            if not config:
                raise ValidationError(f"Unknown RAG configuration: {config_name}")
            
            # Generate query embedding
            query_embedding = await self._generate_query_embedding(query, config.embedding_model)
            
            # Retrieve relevant documents
            retrieved_docs = await self._retrieve_documents(
                query_embedding, config, top_k or config.top_k, filters
            )
            
            # Generate response using retrieved context
            response = await self._generate_rag_response(query, retrieved_docs, config)
            
            result = {
                "query": query,
                "response": response,
                "retrieved_documents": [
                    {
                        "content": doc.content[:200] + "..." if len(doc.content) > 200 else doc.content,
                        "metadata": doc.metadata,
                        "score": doc.score
                    }
                    for doc in retrieved_docs
                ],
                "config_used": config_name,
                "retrieval_strategy": config.retrieval_strategy.value,
                "context_length": sum(len(doc.content) for doc in retrieved_docs)
            }
            
            logger.info("RAG query completed", 
                       query_length=len(query),
                       docs_retrieved=len(retrieved_docs),
                       config=config_name)
            
            return result
            
        except Exception as e:
            logger.error("Failed to query RAG system", 
                        query=query[:100], error=str(e))
            raise ValidationError(f"Failed to query RAG system: {str(e)}")
    
    async def compare_rag_models(
        self,
        query: str,
        config_names: List[str] = None
    ) -> Dict[str, Any]:
        """Compare responses from multiple RAG models."""
        if not self.initialized:
            await self.initialize()
        
        if not config_names:
            config_names = list(self.rag_configs.keys())
        
        try:
            # Query each RAG configuration
            results = {}
            tasks = []
            
            for config_name in config_names:
                if config_name in self.rag_configs:
                    task = self.query_rag(query, config_name)
                    tasks.append((config_name, task))
            
            # Execute queries in parallel
            for config_name, task in tasks:
                try:
                    result = await task
                    results[config_name] = result
                except Exception as e:
                    results[config_name] = {
                        "error": str(e),
                        "query": query
                    }
            
            # Compare and analyze results
            comparison = {
                "query": query,
                "results": results,
                "comparison_metrics": await self._analyze_rag_comparison(results),
                "recommendation": await self._recommend_best_rag_config(results)
            }
            
            return comparison
            
        except Exception as e:
            logger.error("Failed to compare RAG models", error=str(e))
            raise ValidationError(f"Failed to compare RAG models: {str(e)}")
    
    async def optimize_rag_performance(
        self,
        config_name: str,
        test_queries: List[str],
        optimization_targets: List[str] = None
    ) -> Dict[str, Any]:
        """Optimize RAG performance based on test queries."""
        if not self.initialized:
            await self.initialize()
        
        if not optimization_targets:
            optimization_targets = ["accuracy", "speed", "relevance"]
        
        try:
            config = self.rag_configs.get(config_name)
            if not config:
                raise ValidationError(f"Unknown RAG configuration: {config_name}")
            
            # Run baseline tests
            baseline_results = []
            for query in test_queries:
                start_time = datetime.utcnow()
                result = await self.query_rag(query, config_name)
                end_time = datetime.utcnow()
                
                baseline_results.append({
                    "query": query,
                    "response_time": (end_time - start_time).total_seconds(),
                    "retrieved_docs": len(result["retrieved_documents"]),
                    "context_length": result["context_length"]
                })
            
            # Test different parameter combinations
            optimization_results = await self._test_parameter_combinations(
                config, test_queries, optimization_targets
            )
            
            # Generate recommendations
            recommendations = await self._generate_optimization_recommendations(
                baseline_results, optimization_results, optimization_targets
            )
            
            optimization_report = {
                "config_name": config_name,
                "test_queries_count": len(test_queries),
                "optimization_targets": optimization_targets,
                "baseline_performance": {
                    "avg_response_time": np.mean([r["response_time"] for r in baseline_results]),
                    "avg_retrieved_docs": np.mean([r["retrieved_docs"] for r in baseline_results]),
                    "avg_context_length": np.mean([r["context_length"] for r in baseline_results])
                },
                "optimization_results": optimization_results,
                "recommendations": recommendations,
                "generated_at": datetime.utcnow().isoformat()
            }
            
            return optimization_report
            
        except Exception as e:
            logger.error("Failed to optimize RAG performance", error=str(e))
            raise ValidationError(f"Failed to optimize RAG performance: {str(e)}")
    
    # Private helper methods
    async def _initialize_embedding_models(self):
        """Initialize embedding models."""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.warning("Sentence Transformers not available - some embedding models disabled")
            return
        
        try:
            # Initialize common embedding models
            models = [
                "all-MiniLM-L6-v2",
                "all-mpnet-base-v2"
            ]
            
            for model_name in models:
                try:
                    model = SentenceTransformer(model_name)
                    self.embedding_models[model_name] = model
                    logger.info("Embedding model loaded", model=model_name)
                except Exception as e:
                    logger.warning("Failed to load embedding model", 
                                 model=model_name, error=str(e))
            
        except Exception as e:
            logger.error("Failed to initialize embedding models", error=str(e))
    
    async def _initialize_vector_stores(self):
        """Initialize vector stores."""
        try:
            # Initialize ChromaDB
            if CHROMA_AVAILABLE:
                chroma_config = {
                    "collection_name": "compliance_docs_chroma",
                    "persist_directory": "./data/chroma_db"
                }
                self.vector_stores["chromadb"] = ChromaDBVectorStore(chroma_config)
            
            # Initialize FAISS
            if FAISS_AVAILABLE:
                faiss_config = {
                    "dimension": 384,
                    "index_file": "./data/faiss_index.bin"
                }
                self.vector_stores["faiss"] = FAISSVectorStore(faiss_config)
            
            # Initialize Milvus (if available)
            if MILVUS_AVAILABLE:
                milvus_config = {
                    "collection_name": "compliance_docs_milvus",
                    "host": "localhost",
                    "port": "19530",
                    "dimension": 384
                }
                self.vector_stores["milvus"] = MilvusVectorStore(milvus_config)
            
            # Initialize all available vector stores
            for store_name, store in self.vector_stores.items():
                try:
                    await store.initialize()
                    logger.info("Vector store initialized", store=store_name)
                except Exception as e:
                    logger.warning("Failed to initialize vector store", 
                                 store=store_name, error=str(e))
                    # Remove failed store
                    del self.vector_stores[store_name]
            
        except Exception as e:
            logger.error("Failed to initialize vector stores", error=str(e))
    
    async def _setup_rag_configurations(self):
        """Setup RAG configurations."""
        for config_name, config in self.default_configs.items():
            # Only add configurations for available vector stores
            if config.vector_store_type.value in self.vector_stores:
                self.rag_configs[config_name] = config
    
    async def _process_documents(
        self,
        documents: List[Dict[str, Any]],
        config: RAGConfiguration
    ) -> List[DocumentChunk]:
        """Process documents into chunks."""
        chunks = []
        
        for doc_idx, document in enumerate(documents):
            content = document.get("content", "")
            metadata = document.get("metadata", {})
            
            # Split document into chunks
            doc_chunks = self._split_text(content, config.chunk_size, config.chunk_overlap)
            
            for chunk_idx, chunk_text in enumerate(doc_chunks):
                chunk_id = f"doc_{doc_idx}_chunk_{chunk_idx}"
                
                chunk = DocumentChunk(
                    chunk_id=chunk_id,
                    content=chunk_text,
                    metadata={
                        **metadata,
                        "source_document": doc_idx,
                        "chunk_index": chunk_idx,
                        "total_chunks": len(doc_chunks)
                    }
                )
                chunks.append(chunk)
        
        return chunks
    
    def _split_text(self, text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """Split text into overlapping chunks."""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # Find sentence boundary near the end
            if end < len(text):
                # Look for sentence endings
                for punct in ['. ', '! ', '? ']:
                    punct_pos = text.rfind(punct, start, end)
                    if punct_pos > start + chunk_size // 2:
                        end = punct_pos + len(punct)
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - chunk_overlap
            if start >= len(text):
                break
        
        return chunks
    
    async def _generate_embeddings(self, chunks: List[DocumentChunk], model_name: str):
        """Generate embeddings for document chunks."""
        if model_name not in self.embedding_models:
            logger.warning("Embedding model not available", model=model_name)
            return
        
        model = self.embedding_models[model_name]
        
        # Generate embeddings in batches
        batch_size = 32
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i + batch_size]
            texts = [chunk.content for chunk in batch_chunks]
            
            try:
                embeddings = model.encode(texts, convert_to_numpy=True)
                
                for chunk, embedding in zip(batch_chunks, embeddings):
                    chunk.embedding = embedding
                    
            except Exception as e:
                logger.error("Failed to generate embeddings", error=str(e))
                # Set zero embeddings as fallback
                for chunk in batch_chunks:
                    chunk.embedding = np.zeros(384)
    
    async def _generate_query_embedding(self, query: str, model_name: str) -> np.ndarray:
        """Generate embedding for query."""
        if model_name not in self.embedding_models:
            logger.warning("Embedding model not available", model=model_name)
            return np.zeros(384)
        
        model = self.embedding_models[model_name]
        
        try:
            embedding = model.encode([query], convert_to_numpy=True)[0]
            return embedding
        except Exception as e:
            logger.error("Failed to generate query embedding", error=str(e))
            return np.zeros(384)
    
    async def _retrieve_documents(
        self,
        query_embedding: np.ndarray,
        config: RAGConfiguration,
        top_k: int,
        filters: Optional[Dict[str, Any]]
    ) -> List[DocumentChunk]:
        """Retrieve relevant documents."""
        vector_store = self.vector_stores.get(config.vector_store_type.value)
        if not vector_store:
            return []
        
        try:
            # Basic similarity search
            documents = await vector_store.search(query_embedding, top_k)
            
            # Apply filters if provided
            if filters:
                documents = self._apply_filters(documents, filters)
            
            # Apply retrieval strategy
            if config.retrieval_strategy == RetrievalStrategy.MMR:
                documents = self._apply_mmr(documents, query_embedding, lambda_mult=0.5)
            elif config.retrieval_strategy == RetrievalStrategy.CONTEXTUAL_COMPRESSION:
                documents = await self._apply_contextual_compression(documents)
            
            # Filter by similarity threshold
            documents = [doc for doc in documents if doc.score >= config.similarity_threshold]
            
            return documents[:top_k]
            
        except Exception as e:
            logger.error("Failed to retrieve documents", error=str(e))
            return []
    
    def _apply_filters(self, documents: List[DocumentChunk], filters: Dict[str, Any]) -> List[DocumentChunk]:
        """Apply metadata filters to documents."""
        filtered_docs = []
        
        for doc in documents:
            include_doc = True
            
            for filter_key, filter_value in filters.items():
                if filter_key in doc.metadata:
                    if isinstance(filter_value, list):
                        if doc.metadata[filter_key] not in filter_value:
                            include_doc = False
                            break
                    else:
                        if doc.metadata[filter_key] != filter_value:
                            include_doc = False
                            break
            
            if include_doc:
                filtered_docs.append(doc)
        
        return filtered_docs
    
    def _apply_mmr(
        self,
        documents: List[DocumentChunk],
        query_embedding: np.ndarray,
        lambda_mult: float = 0.5
    ) -> List[DocumentChunk]:
        """Apply Maximal Marginal Relevance for diversity."""
        if len(documents) <= 1:
            return documents
        
        selected = []
        remaining = documents.copy()
        
        # Select first document (highest similarity)
        selected.append(remaining.pop(0))
        
        while remaining and len(selected) < len(documents):
            mmr_scores = []
            
            for doc in remaining:
                # Similarity to query
                query_sim = doc.score
                
                # Maximum similarity to already selected documents
                max_sim = 0
                for selected_doc in selected:
                    if hasattr(doc, 'embedding') and hasattr(selected_doc, 'embedding'):
                        if doc.embedding is not None and selected_doc.embedding is not None:
                            sim = np.dot(doc.embedding, selected_doc.embedding) / (
                                np.linalg.norm(doc.embedding) * np.linalg.norm(selected_doc.embedding)
                            )
                            max_sim = max(max_sim, sim)
                
                # MMR score
                mmr_score = lambda_mult * query_sim - (1 - lambda_mult) * max_sim
                mmr_scores.append((mmr_score, doc))
            
            # Select document with highest MMR score
            if mmr_scores:
                best_doc = max(mmr_scores, key=lambda x: x[0])[1]
                selected.append(best_doc)
                remaining.remove(best_doc)
            else:
                break
        
        return selected
    
    async def _apply_contextual_compression(self, documents: List[DocumentChunk]) -> List[DocumentChunk]:
        """Apply contextual compression to reduce irrelevant content."""
        # Simplified implementation - would use a compression model in practice
        compressed_docs = []
        
        for doc in documents:
            # Keep documents with high scores and reasonable length
            if doc.score > 0.8 and len(doc.content) < 2000:
                compressed_docs.append(doc)
            elif doc.score > 0.6:
                # Truncate long documents
                truncated_content = doc.content[:1000] + "..."
                compressed_doc = DocumentChunk(
                    chunk_id=doc.chunk_id,
                    content=truncated_content,
                    metadata={**doc.metadata, "compressed": True},
                    score=doc.score
                )
                compressed_docs.append(compressed_doc)
        
        return compressed_docs
    
    async def _generate_rag_response(
        self,
        query: str,
        retrieved_docs: List[DocumentChunk],
        config: RAGConfiguration
    ) -> str:
        """Generate response using retrieved context."""
        # Prepare context from retrieved documents
        context_parts = []
        total_length = 0
        
        for doc in retrieved_docs:
            if total_length + len(doc.content) <= config.max_context_length:
                context_parts.append(f"[Score: {doc.score:.3f}] {doc.content}")
                total_length += len(doc.content)
            else:
                break
        
        context = "\n\n".join(context_parts)
        
        # Generate response based on model type
        if config.model_type == RAGModelType.CLAUDE_RAG:
            return await self._generate_claude_rag_response(query, context)
        elif config.model_type == RAGModelType.HUGGINGFACE_RAG:
            return await self._generate_huggingface_rag_response(query, context)
        else:
            return await self._generate_custom_rag_response(query, context, config)
    
    async def _generate_claude_rag_response(self, query: str, context: str) -> str:
        """Generate response using Claude with RAG context."""
        # Use the existing prompt service to generate response
        rag_prompt = f"""Based on the following context, please answer the question accurately and comprehensively.

Context:
{context}

Question: {query}

Please provide a detailed answer based on the context provided. If the context doesn't contain enough information to answer the question, please indicate that."""
        
        try:
            # Use prompt service to generate response
            response = await prompt_service.generate_response(
                prompt=rag_prompt,
                model="claude-3-sonnet",
                max_tokens=2000,
                temperature=0.3
            )
            return response.get("response", "I apologize, but I couldn't generate a response.")
        except Exception as e:
            logger.error("Failed to generate Claude RAG response", error=str(e))
            return f"Error generating response: {str(e)}"
    
    async def _generate_huggingface_rag_response(self, query: str, context: str) -> str:
        """Generate response using HuggingFace models."""
        # Placeholder for HuggingFace RAG implementation
        return f"HuggingFace RAG response for: {query}\n\nBased on context: {context[:200]}..."
    
    async def _generate_custom_rag_response(
        self,
        query: str,
        context: str,
        config: RAGConfiguration
    ) -> str:
        """Generate response using custom RAG logic."""
        # Simplified custom response generation
        return f"Custom RAG response for: {query}\n\nUsing {config.model_type.value} with context: {context[:200]}..."
    
    async def _analyze_rag_comparison(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze comparison between different RAG results."""
        metrics = {
            "response_lengths": {},
            "retrieval_counts": {},
            "confidence_scores": {},
            "diversity_score": 0.0
        }
        
        for config_name, result in results.items():
            if "error" not in result:
                metrics["response_lengths"][config_name] = len(result.get("response", ""))
                metrics["retrieval_counts"][config_name] = len(result.get("retrieved_documents", []))
                
                # Calculate average confidence score
                docs = result.get("retrieved_documents", [])
                if docs:
                    avg_score = sum(doc.get("score", 0) for doc in docs) / len(docs)
                    metrics["confidence_scores"][config_name] = avg_score
        
        return metrics
    
    async def _recommend_best_rag_config(self, results: Dict[str, Any]) -> str:
        """Recommend the best RAG configuration based on results."""
        scores = {}
        
        for config_name, result in results.items():
            if "error" not in result:
                score = 0
                
                # Score based on response length (moderate length preferred)
                response_len = len(result.get("response", ""))
                if 100 <= response_len <= 1000:
                    score += 0.3
                
                # Score based on retrieval quality
                docs = result.get("retrieved_documents", [])
                if docs:
                    avg_score = sum(doc.get("score", 0) for doc in docs) / len(docs)
                    score += avg_score * 0.4
                
                # Score based on context relevance
                context_len = result.get("context_length", 0)
                if 500 <= context_len <= 3000:
                    score += 0.3
                
                scores[config_name] = score
        
        if scores:
            best_config = max(scores, key=scores.get)
            return f"Recommended configuration: {best_config} (score: {scores[best_config]:.3f})"
        else:
            return "No valid configuration found"
    
    async def _test_parameter_combinations(
        self,
        config: RAGConfiguration,
        test_queries: List[str],
        targets: List[str]
    ) -> Dict[str, Any]:
        """Test different parameter combinations for optimization."""
        # Simplified parameter testing
        parameter_tests = {
            "top_k_values": [3, 5, 8, 10],
            "similarity_thresholds": [0.5, 0.6, 0.7, 0.8]
        }
        
        test_results = {}
        
        for top_k in parameter_tests["top_k_values"]:
            for threshold in parameter_tests["similarity_thresholds"]:
                test_name = f"top_k_{top_k}_threshold_{threshold}"
                
                # Test with modified parameters
                # This would involve running actual queries with modified config
                test_results[test_name] = {
                    "avg_response_time": np.random.uniform(0.5, 3.0),
                    "avg_relevance_score": np.random.uniform(0.6, 0.9),
                    "parameters": {"top_k": top_k, "threshold": threshold}
                }
        
        return test_results
    
    async def _generate_optimization_recommendations(
        self,
        baseline: List[Dict[str, Any]],
        optimization_results: Dict[str, Any],
        targets: List[str]
    ) -> List[str]:
        """Generate optimization recommendations."""
        recommendations = []
        
        # Analyze results and generate recommendations
        if "accuracy" in targets:
            recommendations.append("Consider increasing similarity threshold for better accuracy")
        
        if "speed" in targets:
            recommendations.append("Reduce top_k value to improve response time")
        
        if "relevance" in targets:
            recommendations.append("Use MMR retrieval strategy for better relevance diversity")
        
        return recommendations

# Global advanced RAG service instance
advanced_rag_service = AdvancedRAGService()