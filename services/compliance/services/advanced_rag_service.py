"""Advanced RAG service with multiple models and enhanced retrieval."""

import os
import asyncio
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import structlog
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

from ...shared.exceptions import ExternalServiceError
from ...shared.local_models import local_model_manager
from .milvus_service import milvus_service
from .rag_service import RAGService

logger = structlog.get_logger()

class AdvancedRAGService:
    """Advanced RAG service with multiple retrieval strategies and model support."""
    
    def __init__(self):
        self.embedding_models = {}
        self.reranking_models = {}
        self.tfidf_vectorizer = None
        self.retrieval_strategies = {}
        self.initialized = False
        
    async def initialize(self):
        """Initialize the advanced RAG service."""
        
        if self.initialized:
            return
            
        try:
            logger.info("Initializing Advanced RAG service")
            
            # Initialize local model manager
            if not local_model_manager.initialized:
                await local_model_manager.initialize()
            
            # Set up retrieval strategies
            self.retrieval_strategies = {
                "semantic": self._semantic_retrieval,
                "hybrid": self._hybrid_retrieval,
                "contextual": self._contextual_retrieval,
                "multi_query": self._multi_query_retrieval,
                "hierarchical": self._hierarchical_retrieval
            }
            
            # Initialize TF-IDF vectorizer for hybrid search
            self.tfidf_vectorizer = TfidfVectorizer(
                max_features=10000,
                stop_words='english',
                ngram_range=(1, 2)
            )
            
            self.initialized = True
            logger.info("Advanced RAG service initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize Advanced RAG service", error=str(e))
            raise ExternalServiceError("AdvancedRAG", f"Initialization failed: {str(e)}")
    
    async def setup_embedding_model(
        self, 
        model_name: str, 
        model_key: Optional[str] = None
    ) -> str:
        """Set up an embedding model for RAG."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            # Load embedding model
            model_key = model_key or f"{model_name}_embedding"
            
            if model_key not in self.embedding_models:
                loaded_key = await local_model_manager.load_model(
                    model_name=model_name,
                    model_type="embedding"
                )
                self.embedding_models[model_key] = loaded_key
                
                logger.info("Embedding model loaded for RAG", 
                           model_name=model_name, model_key=model_key)
            
            return model_key
            
        except Exception as e:
            logger.error("Failed to setup embedding model", 
                        model_name=model_name, error=str(e))
            raise ExternalServiceError("AdvancedRAG", f"Model setup failed: {str(e)}")
    
    async def enhanced_query(
        self,
        query: str,
        strategy: str = "hybrid",
        framework: str = "GDPR",
        top_k: int = 10,
        rerank: bool = True,
        context_window: int = 3,
        **kwargs
    ) -> Dict[str, Any]:
        """Enhanced query with multiple retrieval strategies."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            logger.debug("Processing enhanced RAG query", 
                        query=query[:100], strategy=strategy, framework=framework)
            
            # Select retrieval strategy
            if strategy not in self.retrieval_strategies:
                strategy = "hybrid"
                
            retrieval_func = self.retrieval_strategies[strategy]
            
            # Execute retrieval
            retrieval_results = await retrieval_func(
                query=query,
                framework=framework,
                top_k=top_k,
                context_window=context_window,
                **kwargs
            )
            
            # Apply reranking if requested
            if rerank and len(retrieval_results) > 1:
                retrieval_results = await self._rerank_results(
                    query, retrieval_results, top_k
                )
            
            # Generate enhanced insights
            insights = await self._generate_enhanced_insights(
                query, retrieval_results, framework
            )
            
            # Calculate confidence and quality scores
            confidence_score = self._calculate_confidence_score(retrieval_results)
            quality_score = self._calculate_quality_score(retrieval_results, query)
            
            result = {
                "query": query,
                "strategy": strategy,
                "framework": framework,
                "documents": retrieval_results,
                "insights": insights,
                "confidence_score": confidence_score,
                "quality_score": quality_score,
                "metadata": {
                    "retrieval_time": datetime.utcnow().isoformat(),
                    "documents_found": len(retrieval_results),
                    "reranked": rerank,
                    "context_window": context_window
                }
            }
            
            logger.debug("Enhanced RAG query completed", 
                        strategy=strategy, 
                        documents_found=len(retrieval_results),
                        confidence=confidence_score)
            
            return result
            
        except Exception as e:
            logger.error("Enhanced RAG query failed", 
                        query=query[:100], strategy=strategy, error=str(e))
            raise ExternalServiceError("AdvancedRAG", f"Query failed: {str(e)}")
    
    async def _semantic_retrieval(
        self,
        query: str,
        framework: str,
        top_k: int,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Pure semantic retrieval using vector similarity."""
        
        try:
            # Use default embedding model if available
            if self.embedding_models:
                model_key = list(self.embedding_models.values())[0]
                
                # Generate query embedding
                embedding_result = await local_model_manager.generate_embeddings(
                    model_key=model_key,
                    texts=[query]
                )
                
                query_embedding = embedding_result["embeddings"][0]
                
                # Search in vector database
                results = await milvus_service.search_similar_documents(
                    query_embedding=query_embedding,
                    framework=framework,
                    top_k=top_k
                )
                
                return results
            else:
                # Fallback to basic RAG service
                basic_rag = RAGService()
                await basic_rag.initialize()
                basic_result = await basic_rag.query_compliance_docs(
                    query, framework, top_k
                )
                return basic_result.get("relevant_documents", [])
                
        except Exception as e:
            logger.error("Semantic retrieval failed", error=str(e))
            return []
    
    async def _hybrid_retrieval(
        self,
        query: str,
        framework: str,
        top_k: int,
        alpha: float = 0.7,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Hybrid retrieval combining semantic and keyword search."""
        
        try:
            # Get semantic results
            semantic_results = await self._semantic_retrieval(
                query, framework, top_k * 2
            )
            
            # Get keyword-based results using TF-IDF
            keyword_results = await self._keyword_retrieval(
                query, framework, top_k * 2
            )
            
            # Combine and rerank results
            combined_results = self._combine_retrieval_results(
                semantic_results, keyword_results, alpha
            )
            
            return combined_results[:top_k]
            
        except Exception as e:
            logger.error("Hybrid retrieval failed", error=str(e))
            return await self._semantic_retrieval(query, framework, top_k)
    
    async def _contextual_retrieval(
        self,
        query: str,
        framework: str,
        top_k: int,
        context_window: int = 3,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Contextual retrieval with expanded context windows."""
        
        try:
            # Get initial results
            initial_results = await self._semantic_retrieval(
                query, framework, top_k
            )
            
            # Expand context for each result
            expanded_results = []
            for result in initial_results:
                expanded_result = await self._expand_document_context(
                    result, context_window
                )
                expanded_results.append(expanded_result)
            
            return expanded_results
            
        except Exception as e:
            logger.error("Contextual retrieval failed", error=str(e))
            return await self._semantic_retrieval(query, framework, top_k)
    
    async def _multi_query_retrieval(
        self,
        query: str,
        framework: str,
        top_k: int,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Multi-query retrieval with query expansion."""
        
        try:
            # Generate query variations
            query_variations = await self._generate_query_variations(query)
            
            # Retrieve for each query variation
            all_results = []
            for variation in query_variations:
                results = await self._semantic_retrieval(
                    variation, framework, top_k // len(query_variations) + 1
                )
                all_results.extend(results)
            
            # Deduplicate and rank
            unique_results = self._deduplicate_results(all_results)
            
            return unique_results[:top_k]
            
        except Exception as e:
            logger.error("Multi-query retrieval failed", error=str(e))
            return await self._semantic_retrieval(query, framework, top_k)
    
    async def _hierarchical_retrieval(
        self,
        query: str,
        framework: str,
        top_k: int,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Hierarchical retrieval with document structure awareness."""
        
        try:
            # First pass: retrieve document sections
            section_results = await self._semantic_retrieval(
                query, framework, top_k * 3
            )
            
            # Second pass: retrieve related subsections
            hierarchical_results = []
            for result in section_results:
                # Get parent and child sections
                related_sections = await self._get_related_sections(result)
                hierarchical_results.extend(related_sections)
            
            # Deduplicate and rank by relevance
            unique_results = self._deduplicate_results(hierarchical_results)
            
            return unique_results[:top_k]
            
        except Exception as e:
            logger.error("Hierarchical retrieval failed", error=str(e))
            return await self._semantic_retrieval(query, framework, top_k)
    
    async def _keyword_retrieval(
        self,
        query: str,
        framework: str,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Keyword-based retrieval using TF-IDF."""
        
        try:
            # This would integrate with a full-text search engine
            # For now, return empty list as fallback
            return []
            
        except Exception as e:
            logger.error("Keyword retrieval failed", error=str(e))
            return []
    
    def _combine_retrieval_results(
        self,
        semantic_results: List[Dict[str, Any]],
        keyword_results: List[Dict[str, Any]],
        alpha: float
    ) -> List[Dict[str, Any]]:
        """Combine semantic and keyword retrieval results."""
        
        # Create combined scoring
        combined_results = {}
        
        # Add semantic results with alpha weighting
        for i, result in enumerate(semantic_results):
            doc_id = result.get("id", str(i))
            semantic_score = result.get("score", 0.0)
            combined_results[doc_id] = {
                **result,
                "combined_score": alpha * semantic_score,
                "semantic_score": semantic_score,
                "keyword_score": 0.0
            }
        
        # Add keyword results with (1-alpha) weighting
        for i, result in enumerate(keyword_results):
            doc_id = result.get("id", str(i))
            keyword_score = result.get("score", 0.0)
            
            if doc_id in combined_results:
                combined_results[doc_id]["combined_score"] += (1 - alpha) * keyword_score
                combined_results[doc_id]["keyword_score"] = keyword_score
            else:
                combined_results[doc_id] = {
                    **result,
                    "combined_score": (1 - alpha) * keyword_score,
                    "semantic_score": 0.0,
                    "keyword_score": keyword_score
                }
        
        # Sort by combined score
        sorted_results = sorted(
            combined_results.values(),
            key=lambda x: x["combined_score"],
            reverse=True
        )
        
        return sorted_results
    
    async def _rerank_results(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Rerank results using cross-encoder model."""
        
        try:
            # If we have a reranking model, use it
            if self.reranking_models:
                # Use first available reranking model
                model_key = list(self.reranking_models.values())[0]
                
                # Prepare query-document pairs
                pairs = []
                for result in results:
                    content = result.get("content", "")
                    pairs.append((query, content))
                
                # Get reranking scores
                rerank_result = await local_model_manager.rerank_documents(
                    model_key=model_key,
                    query_doc_pairs=pairs
                )
                
                # Update scores and sort
                for i, result in enumerate(results):
                    if i < len(rerank_result["scores"]):
                        result["rerank_score"] = rerank_result["scores"][i]
                        result["score"] = rerank_result["scores"][i]
                
                results.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)
            
            return results[:top_k]
            
        except Exception as e:
            logger.error("Reranking failed", error=str(e))
            return results[:top_k]
    
    async def _generate_enhanced_insights(
        self,
        query: str,
        results: List[Dict[str, Any]],
        framework: str
    ) -> Dict[str, Any]:
        """Generate enhanced insights from retrieval results."""
        
        try:
            insights = {
                "summary": "",
                "key_points": [],
                "compliance_implications": [],
                "recommendations": [],
                "confidence_level": "medium"
            }
            
            if not results:
                insights["summary"] = "No relevant documents found for the query."
                insights["confidence_level"] = "low"
                return insights
            
            # Extract key information from top results
            top_results = results[:5]
            
            # Generate summary
            contents = [r.get("content", "") for r in top_results]
            insights["summary"] = self._generate_summary(contents, query)
            
            # Extract key points
            insights["key_points"] = self._extract_key_points(top_results)
            
            # Generate compliance implications
            insights["compliance_implications"] = self._generate_compliance_implications(
                top_results, framework
            )
            
            # Generate recommendations
            insights["recommendations"] = self._generate_recommendations(
                top_results, query, framework
            )
            
            # Calculate confidence level
            avg_score = np.mean([r.get("score", 0) for r in top_results])
            if avg_score > 0.8:
                insights["confidence_level"] = "high"
            elif avg_score > 0.6:
                insights["confidence_level"] = "medium"
            else:
                insights["confidence_level"] = "low"
            
            return insights
            
        except Exception as e:
            logger.error("Enhanced insights generation failed", error=str(e))
            return {
                "summary": "Unable to generate insights due to processing error.",
                "key_points": [],
                "compliance_implications": [],
                "recommendations": [],
                "confidence_level": "low"
            }
    
    def _generate_summary(self, contents: List[str], query: str) -> str:
        """Generate a summary from document contents."""
        
        if not contents:
            return "No content available for summary."
        
        # Simple extractive summarization
        combined_content = " ".join(contents)
        sentences = combined_content.split(". ")
        
        # Score sentences by query relevance
        query_words = set(query.lower().split())
        scored_sentences = []
        
        for sentence in sentences[:20]:  # Limit to first 20 sentences
            sentence_words = set(sentence.lower().split())
            relevance_score = len(query_words.intersection(sentence_words))
            if relevance_score > 0:
                scored_sentences.append((sentence, relevance_score))
        
        # Select top sentences
        scored_sentences.sort(key=lambda x: x[1], reverse=True)
        top_sentences = [s[0] for s in scored_sentences[:3]]
        
        return ". ".join(top_sentences) + "." if top_sentences else "No relevant summary available."
    
    def _extract_key_points(self, results: List[Dict[str, Any]]) -> List[str]:
        """Extract key points from results."""
        
        key_points = []
        
        for result in results[:3]:
            content = result.get("content", "")
            title = result.get("title", "")
            
            # Extract sentences that seem like key points
            sentences = content.split(". ")
            for sentence in sentences:
                if any(keyword in sentence.lower() for keyword in 
                      ["must", "shall", "required", "mandatory", "prohibited", "ensure"]):
                    key_points.append(sentence.strip())
                    if len(key_points) >= 5:
                        break
            
            if len(key_points) >= 5:
                break
        
        return key_points[:5]
    
    def _generate_compliance_implications(
        self, 
        results: List[Dict[str, Any]], 
        framework: str
    ) -> List[str]:
        """Generate compliance implications."""
        
        implications = []
        
        framework_keywords = {
            "GDPR": ["data protection", "consent", "privacy", "personal data"],
            "HIPAA": ["health information", "medical records", "patient privacy"],
            "EU_AI_ACT": ["AI system", "risk assessment", "transparency", "human oversight"]
        }
        
        keywords = framework_keywords.get(framework, [])
        
        for result in results[:3]:
            content = result.get("content", "").lower()
            
            for keyword in keywords:
                if keyword in content:
                    implications.append(
                        f"Consider {keyword} requirements under {framework}"
                    )
                    break
        
        if not implications:
            implications.append(f"Review {framework} compliance requirements")
        
        return implications[:3]
    
    def _generate_recommendations(
        self, 
        results: List[Dict[str, Any]], 
        query: str, 
        framework: str
    ) -> List[str]:
        """Generate actionable recommendations."""
        
        recommendations = [
            f"Review the retrieved documents for {framework} compliance",
            "Consult with legal experts for specific implementation guidance",
            "Document compliance measures and maintain audit trails"
        ]
        
        # Add query-specific recommendations
        if "data" in query.lower():
            recommendations.append("Implement data protection measures")
        
        if "consent" in query.lower():
            recommendations.append("Establish clear consent mechanisms")
        
        if "risk" in query.lower():
            recommendations.append("Conduct thorough risk assessments")
        
        return recommendations[:5]
    
    def _calculate_confidence_score(self, results: List[Dict[str, Any]]) -> float:
        """Calculate confidence score for retrieval results."""
        
        if not results:
            return 0.0
        
        scores = [r.get("score", 0) for r in results]
        avg_score = np.mean(scores)
        score_variance = np.var(scores)
        
        # High confidence if high average score and low variance
        confidence = avg_score * (1 - min(score_variance, 0.5))
        
        return min(1.0, max(0.0, confidence))
    
    def _calculate_quality_score(
        self, 
        results: List[Dict[str, Any]], 
        query: str
    ) -> float:
        """Calculate quality score for retrieval results."""
        
        if not results:
            return 0.0
        
        quality_factors = []
        
        # Factor 1: Average relevance score
        avg_relevance = np.mean([r.get("score", 0) for r in results])
        quality_factors.append(avg_relevance)
        
        # Factor 2: Content length (longer content often more informative)
        avg_length = np.mean([len(r.get("content", "")) for r in results])
        length_score = min(1.0, avg_length / 1000)  # Normalize to 1000 chars
        quality_factors.append(length_score)
        
        # Factor 3: Query coverage (how well results cover query terms)
        query_words = set(query.lower().split())
        coverage_scores = []
        
        for result in results:
            content_words = set(result.get("content", "").lower().split())
            coverage = len(query_words.intersection(content_words)) / len(query_words)
            coverage_scores.append(coverage)
        
        avg_coverage = np.mean(coverage_scores) if coverage_scores else 0
        quality_factors.append(avg_coverage)
        
        return np.mean(quality_factors)
    
    async def _generate_query_variations(self, query: str) -> List[str]:
        """Generate query variations for multi-query retrieval."""
        
        variations = [query]
        
        # Simple query expansion techniques
        words = query.split()
        
        # Add synonyms and related terms
        synonyms = {
            "data": ["information", "records"],
            "privacy": ["confidentiality", "protection"],
            "consent": ["permission", "authorization"],
            "compliance": ["adherence", "conformity"]
        }
        
        for word in words:
            if word.lower() in synonyms:
                for synonym in synonyms[word.lower()]:
                    new_query = query.replace(word, synonym)
                    variations.append(new_query)
        
        # Add question variations
        if not query.endswith("?"):
            variations.append(f"What is {query}?")
            variations.append(f"How to {query}?")
        
        return variations[:5]  # Limit to 5 variations
    
    def _deduplicate_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate results based on content similarity."""
        
        if not results:
            return results
        
        unique_results = []
        seen_contents = set()
        
        for result in results:
            content = result.get("content", "")
            content_hash = hash(content[:200])  # Use first 200 chars for deduplication
            
            if content_hash not in seen_contents:
                seen_contents.add(content_hash)
                unique_results.append(result)
        
        return unique_results
    
    async def _expand_document_context(
        self, 
        result: Dict[str, Any], 
        context_window: int
    ) -> Dict[str, Any]:
        """Expand document context by including surrounding sections."""
        
        # This would integrate with document structure information
        # For now, return the result as-is
        expanded_result = result.copy()
        expanded_result["context_expanded"] = True
        expanded_result["context_window"] = context_window
        
        return expanded_result
    
    async def _get_related_sections(
        self, 
        result: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get related sections for hierarchical retrieval."""
        
        # This would use document structure information
        # For now, return the original result
        return [result]
    
    async def close(self):
        """Close the advanced RAG service."""
        
        try:
            # Clean up resources
            self.embedding_models.clear()
            self.reranking_models.clear()
            
            logger.info("Advanced RAG service closed")
            
        except Exception as e:
            logger.error("Advanced RAG service close failed", error=str(e))

# Global instance
advanced_rag_service = AdvancedRAGService()
            
            return unique_results[:top_k]
            
        except Exception as e:
            logger.error("Multi-query retrieval failed", error=str(e))
            return await self._semantic_retrieval(query, framework, top_k)
    
    async def _hierarchical_retrieval(
        self,
        query: str,
        framework: str,
        top_k: int,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Hierarchical retrieval with multiple levels of granularity."""
        
        try:
            # Level 1: Broad category search
            broad_results = await self._semantic_retrieval(
                query, framework, top_k * 3
            )
            
            # Level 2: Specific section search within broad results
            refined_results = []
            for result in broad_results[:top_k * 2]:
                if self._is_relevant_to_query(result, query):
                    refined_results.append(result)
            
            # Level 3: Fine-grained relevance scoring
            scored_results = await self._score_relevance(query, refined_results)
            
            return scored_results[:top_k]
            
        except Exception as e:
            logger.error("Hierarchical retrieval failed", error=str(e))
            return await self._semantic_retrieval(query, framework, top_k)
    
    async def _keyword_retrieval(
        self,
        query: str,
        framework: str,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Keyword-based retrieval using TF-IDF."""
        
        try:
            # This is a simplified implementation
            # In practice, you'd have a pre-built TF-IDF index
            
            # Get all documents for the framework
            all_docs = await milvus_service.search_similar_documents(
                query_embedding=[0.0] * 768,  # Dummy embedding
                framework=framework,
                top_k=1000,
                similarity_threshold=0.0
            )
            
            if not all_docs:
                return []
            
            # Extract text content
            doc_texts = [doc.get("content", "") for doc in all_docs]
            
            # Fit TF-IDF if not already fitted
            if not hasattr(self.tfidf_vectorizer, 'vocabulary_'):
                self.tfidf_vectorizer.fit(doc_texts)
            
            # Transform query and documents
            query_tfidf = self.tfidf_vectorizer.transform([query])
            doc_tfidf = self.tfidf_vectorizer.transform(doc_texts)
            
            # Calculate similarities
            similarities = cosine_similarity(query_tfidf, doc_tfidf).flatten()
            
            # Get top results
            top_indices = np.argsort(similarities)[::-1][:top_k]
            
            keyword_results = []
            for idx in top_indices:
                if similarities[idx] > 0:
                    result = all_docs[idx].copy()
                    result["keyword_score"] = float(similarities[idx])
                    keyword_results.append(result)
            
            return keyword_results
            
        except Exception as e:
            logger.error("Keyword retrieval failed", error=str(e))
            return []
    
    def _combine_retrieval_results(
        self,
        semantic_results: List[Dict[str, Any]],
        keyword_results: List[Dict[str, Any]],
        alpha: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Combine semantic and keyword retrieval results."""
        
        # Create a mapping of document IDs to results
        combined_scores = {}
        
        # Add semantic results
        for i, result in enumerate(semantic_results):
            doc_id = result.get("id", f"semantic_{i}")
            semantic_score = result.get("similarity_score", 0.0)
            combined_scores[doc_id] = {
                "result": result,
                "semantic_score": semantic_score,
                "keyword_score": 0.0,
                "combined_score": alpha * semantic_score
            }
        
        # Add keyword results
        for i, result in enumerate(keyword_results):
            doc_id = result.get("id", f"keyword_{i}")
            keyword_score = result.get("keyword_score", 0.0)
            
            if doc_id in combined_scores:
                # Update existing result
                combined_scores[doc_id]["keyword_score"] = keyword_score
                combined_scores[doc_id]["combined_score"] = (
                    alpha * combined_scores[doc_id]["semantic_score"] +
                    (1 - alpha) * keyword_score
                )
            else:
                # Add new result
                combined_scores[doc_id] = {
                    "result": result,
                    "semantic_score": 0.0,
                    "keyword_score": keyword_score,
                    "combined_score": (1 - alpha) * keyword_score
                }
        
        # Sort by combined score
        sorted_results = sorted(
            combined_scores.values(),
            key=lambda x: x["combined_score"],
            reverse=True
        )
        
        # Return results with combined scores
        final_results = []
        for item in sorted_results:
            result = item["result"].copy()
            result["combined_score"] = item["combined_score"]
            result["semantic_score"] = item["semantic_score"]
            result["keyword_score"] = item["keyword_score"]
            final_results.append(result)
        
        return final_results
    
    async def _rerank_results(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Rerank results using a more sophisticated scoring method."""
        
        try:
            # Simple reranking based on content relevance
            reranked_results = []
            
            for result in results:
                content = result.get("content", "")
                title = result.get("title", "")
                
                # Calculate relevance score
                relevance_score = self._calculate_relevance_score(
                    query, content, title
                )
                
                result_copy = result.copy()
                result_copy["relevance_score"] = relevance_score
                reranked_results.append(result_copy)
            
            # Sort by relevance score
            reranked_results.sort(
                key=lambda x: x.get("relevance_score", 0),
                reverse=True
            )
            
            return reranked_results[:top_k]
            
        except Exception as e:
            logger.error("Result reranking failed", error=str(e))
            return results[:top_k]
    
    def _calculate_relevance_score(
        self,
        query: str,
        content: str,
        title: str
    ) -> float:
        """Calculate relevance score for reranking."""
        
        query_terms = set(query.lower().split())
        content_terms = set(content.lower().split())
        title_terms = set(title.lower().split())
        
        # Term overlap scores
        content_overlap = len(query_terms.intersection(content_terms)) / len(query_terms)
        title_overlap = len(query_terms.intersection(title_terms)) / len(query_terms)
        
        # Weighted relevance score
        relevance_score = 0.3 * title_overlap + 0.7 * content_overlap
        
        return relevance_score
    
    async def _generate_query_variations(self, query: str) -> List[str]:
        """Generate query variations for multi-query retrieval."""
        
        variations = [query]  # Include original query
        
        # Simple query expansion techniques
        # In practice, you might use a language model for this
        
        # Add synonyms and related terms
        expansion_terms = {
            "compliance": ["regulatory", "legal", "requirements"],
            "data": ["information", "records", "details"],
            "privacy": ["confidentiality", "protection", "security"],
            "rights": ["permissions", "entitlements", "privileges"]
        }
        
        query_lower = query.lower()
        for term, synonyms in expansion_terms.items():
            if term in query_lower:
                for synonym in synonyms:
                    expanded_query = query_lower.replace(term, synonym)
                    variations.append(expanded_query)
        
        return variations[:5]  # Limit to 5 variations
    
    def _deduplicate_results(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Remove duplicate results based on content similarity."""
        
        unique_results = []
        seen_ids = set()
        
        for result in results:
            result_id = result.get("id", result.get("document_id", ""))
            
            if result_id and result_id not in seen_ids:
                seen_ids.add(result_id)
                unique_results.append(result)
            elif not result_id:
                # For results without IDs, check content similarity
                is_duplicate = False
                content = result.get("content", "")
                
                for existing in unique_results:
                    existing_content = existing.get("content", "")
                    if self._calculate_content_similarity(content, existing_content) > 0.8:
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    unique_results.append(result)
        
        return unique_results
    
    def _calculate_content_similarity(self, content1: str, content2: str) -> float:
        """Calculate similarity between two content strings."""
        
        if not content1 or not content2:
            return 0.0
        
        # Simple Jaccard similarity
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    async def _expand_document_context(
        self,
        document: Dict[str, Any],
        context_window: int
    ) -> Dict[str, Any]:
        """Expand document context with surrounding content."""
        
        # This is a simplified implementation
        # In practice, you'd retrieve related document sections
        
        expanded_doc = document.copy()
        expanded_doc["context_expanded"] = True
        expanded_doc["context_window"] = context_window
        
        return expanded_doc
    
    def _is_relevant_to_query(self, result: Dict[str, Any], query: str) -> bool:
        """Check if a result is relevant to the query."""
        
        content = result.get("content", "").lower()
        title = result.get("title", "").lower()
        query_lower = query.lower()
        
        # Simple relevance check
        query_terms = query_lower.split()
        
        relevance_count = 0
        for term in query_terms:
            if term in content or term in title:
                relevance_count += 1
        
        # Consider relevant if at least 50% of query terms are found
        return relevance_count >= len(query_terms) * 0.5
    
    async def _score_relevance(
        self,
        query: str,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Score results for relevance."""
        
        scored_results = []
        
        for result in results:
            relevance_score = self._calculate_relevance_score(
                query,
                result.get("content", ""),
                result.get("title", "")
            )
            
            result_copy = result.copy()
            result_copy["hierarchical_score"] = relevance_score
            scored_results.append(result_copy)
        
        # Sort by hierarchical score
        scored_results.sort(
            key=lambda x: x.get("hierarchical_score", 0),
            reverse=True
        )
        
        return scored_results
    
    async def _generate_enhanced_insights(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        framework: str
    ) -> List[str]:
        """Generate enhanced insights from retrieved documents."""
        
        if not documents:
            return ["No relevant documents found for the query."]
        
        insights = []
        
        # Analyze document categories
        categories = {}
        for doc in documents:
            category = doc.get("category", "general")
            categories[category] = categories.get(category, 0) + 1
        
        if categories:
            top_category = max(categories, key=categories.get)
            insights.append(f"Most relevant category: {top_category} ({categories[top_category]} documents)")
        
        # Analyze framework coverage
        framework_docs = [doc for doc in documents if doc.get("framework") == framework]
        if framework_docs:
            insights.append(f"Found {len(framework_docs)} documents specific to {framework}")
        
        # Quality assessment
        high_quality_docs = [doc for doc in documents if doc.get("similarity_score", 0) > 0.8]
        if high_quality_docs:
            insights.append(f"{len(high_quality_docs)} high-quality matches found")
        
        return insights
    
    def _calculate_confidence_score(self, results: List[Dict[str, Any]]) -> float:
        """Calculate confidence score based on retrieval results."""
        
        if not results:
            return 0.0
        
        # Average similarity score
        similarity_scores = [
            result.get("similarity_score", 0.0) for result in results
        ]
        
        avg_similarity = sum(similarity_scores) / len(similarity_scores)
        
        # Adjust based on number of results
        result_count_factor = min(len(results) / 10, 1.0)
        
        confidence = avg_similarity * result_count_factor
        
        return round(confidence, 3)
    
    def _calculate_quality_score(
        self,
        results: List[Dict[str, Any]],
        query: str
    ) -> float:
        """Calculate quality score based on result relevance."""
        
        if not results:
            return 0.0
        
        # Calculate average relevance
        relevance_scores = []
        for result in results:
            relevance = self._calculate_relevance_score(
                query,
                result.get("content", ""),
                result.get("title", "")
            )
            relevance_scores.append(relevance)
        
        avg_relevance = sum(relevance_scores) / len(relevance_scores)
        
        return round(avg_relevance, 3)

# Global advanced RAG service instance
advanced_rag_service = AdvancedRAGService()