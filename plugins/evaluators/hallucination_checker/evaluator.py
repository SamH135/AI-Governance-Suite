"""
Privacy-Focused Hallucination Checker Evaluator

This evaluator detects hallucinations in AI-generated text without requiring external APIs,
making it suitable for privacy-sensitive applications. It uses local NLP models to:

1. Extract claims from AI-generated text
2. Generate search queries based on those claims
3. Scrape and extract content from web search results
4. Evaluate source credibility
5. Detect contradictions using Natural Language Inference
6. Calculate hallucination scores based on found evidence

The evaluator provides detailed reporting on potential hallucinations with source verification.
"""

import re
import logging
import json
import time
import traceback
import hashlib
import os
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Tuple, Set, Optional, Union
from urllib.parse import urlparse
import tempfile
from pathlib import Path
import concurrent.futures

from urllib3 import Retry

from services.compliance.framework.core.base import (
    BaseEvaluator,
    EvaluatorMetadata,
    EvaluatorCapability,
    LLMRequirements,
    RAGRequirements,
    ModelRequirement
)

# Configure logging
logger = logging.getLogger(__name__)

# Define optional dependency imports with fallbacks
try:
    import spacy
    from spacy.matcher import DependencyMatcher

    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    logger.warning("spaCy not available. Using simplified claim extraction.")

try:
    import nltk
    from nltk.sentiment import SentimentIntensityAnalyzer

    nltk.download('vader_lexicon', quiet=True)
    NLTK_AVAILABLE = True
except ImportError:
    NLTK_AVAILABLE = False
    logger.warning("NLTK not available. Sentiment analysis disabled.")

try:
    from sentence_transformers import SentenceTransformer, util

    SBERT_AVAILABLE = True
except ImportError:
    SBERT_AVAILABLE = False
    logger.warning("SentenceTransformer not available. Using simplified similarity metrics.")

try:
    import torch
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("Torch/sklearn not available. Using basic text matching.")

try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification

    NLI_AVAILABLE = True
except ImportError:
    NLI_AVAILABLE = False
    logger.warning("Transformers not available. Contradiction detection disabled.")

try:
    import requests
    from bs4 import BeautifulSoup

    WEB_AVAILABLE = True
except ImportError:
    WEB_AVAILABLE = False
    logger.warning("Web scraping dependencies not available. Web verification disabled.")

try:
    import trafilatura

    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False
    logger.warning("Trafilatura not available. Using alternative content extraction.")

try:
    from readability import Document
    import html2text

    READABILITY_AVAILABLE = True
except ImportError:
    READABILITY_AVAILABLE = False
    logger.warning("Readability not available. Using alternative content extraction.")


class ClaimExtractor:
    """Extract verifiable claims from text using NLP techniques."""

    def __init__(self):
        """Initialize the claim extractor with NLP tools."""
        self.nlp = None
        self.matcher = None
        self.sia = None
        self.initialized = False

        if SPACY_AVAILABLE:
            try:
                if spacy.util.is_package("en_core_web_sm"):
                    self.nlp = spacy.load("en_core_web_sm")
                elif spacy.util.is_package("en_core_web_md"): # Keep md as an option if available
                    self.nlp = spacy.load("en_core_web_md")
                else:
                    # Attempt to load en_core_web_sm, which might trigger an error if not installed
                    # This error will be caught by the outer try-except block.
                    self.nlp = spacy.load("en_core_web_sm")
            
                # Set up dependency patterns for factual statements
                self.matcher = DependencyMatcher(self.nlp.vocab)

                # Pattern for factual assertions (subject-verb-object)
                self.matcher.add("FACTUAL_STATEMENT", [
                    [
                        # Subject
                        {"RIGHT_ID": "subject", "RIGHT_ATTRS": {"dep": {"IN": ["nsubj", "nsubjpass"]}}},
                        # Verb
                        {"LEFT_ID": "subject", "REL_OP": ">", "RIGHT_ID": "verb", "RIGHT_ATTRS": {"pos": "VERB"}},
                        # Object (optional)
                        {"LEFT_ID": "verb", "REL_OP": ">", "RIGHT_ID": "object",
                         "RIGHT_ATTRS": {"dep": {"IN": ["dobj", "pobj"]}}}
                    ]
                ])

                self.initialized = True
            except Exception as e:
                logger.error(f"Failed to initialize spaCy model (en_core_web_sm or en_core_web_md): {e}. Please ensure 'en_core_web_sm' is downloaded (python -m spacy download en_core_web_sm).")
                # self.nlp remains None or handle as per existing error strategy

        # Set up sentiment analyzer if available
        if NLTK_AVAILABLE:
            try:
                self.sia = SentimentIntensityAnalyzer()
            except Exception as e:
                logger.error(f"Failed to initialize NLTK sentiment analyzer: {e}")

    def is_likely_opinion(self, text):
        """Check if a statement is likely an opinion rather than a fact."""
        if not self.sia:
            # Basic heuristic fallback
            opinion_markers = ["think", "believe", "feel", "opinion", "seems", "appears"]
            return any(marker in text.lower() for marker in opinion_markers)

        scores = self.sia.polarity_scores(text)
        # High compound score (positive or negative) often indicates opinion
        return abs(scores['compound']) > 0.5

    def extract_claims(self, text):
        """Extract verifiable claims from text using dependency parsing or fallbacks."""
        if not self.initialized or not self.nlp:
            return self._extract_claims_fallback(text)

        try:
            doc = self.nlp(text)

            # Split into sentences
            sentences = [sent.text.strip() for sent in doc.sents]

            # Analyze each sentence
            claims = []
            entities = set()
            keywords = []

            for sentence in sentences:
                # Skip short sentences
                if len(sentence.split()) < 5:
                    continue

                sent_doc = self.nlp(sentence)

                # Extract entities
                sent_entities = [ent.text for ent in sent_doc.ents]
                for ent in sent_doc.ents:
                    entities.add(ent.text)

                # Check if the sentence contains a factual statement pattern
                matches = self.matcher(sent_doc)
                has_factual_pattern = len(matches) > 0

                # Check if it's likely an opinion
                is_opinion = self.is_likely_opinion(sentence)

                # Score the sentence (revised scoring system)
                score = 0

                # Factual pattern is a strong indicator
                if has_factual_pattern:
                    score += 2

                # Opinions are less likely to be verifiable claims
                if is_opinion:
                    score -= 1

                # Entities are good indicators
                score += min(len(sent_entities), 3) * 0.5

                # Sentences with numbers/dates are likely factual
                if any(c.isdigit() for c in sentence):
                    score += 1

                # Factual language markers
                factual_markers = [
                    "according to", "research", "study", "evidence", "data",
                    "statistic", "percent", "survey", "report", "found",
                    "discovered", "published", "conducted", "confirmed"
                ]

                for marker in factual_markers:
                    if marker in sentence.lower():
                        score += 0.5
                        break

                # Extract the structure of factual claims when available
                claim_structure = {}
                if matches:
                    match_id, token_ids = matches[0]
                    for key, token_id in token_ids:
                        claim_structure[key] = sent_doc[token_id].text

                    # Add the predicate to keywords for better search
                    if 'verb' in claim_structure:
                        keywords.append(claim_structure['verb'])

                # If score is high enough, consider it a claim
                if score >= 1.5:
                    claims.append({
                        "text": sentence,
                        "score": score,
                        "entities": sent_entities,
                        "is_opinion": is_opinion,
                        "claim_structure": claim_structure,
                        "has_factual_pattern": has_factual_pattern
                    })

            # Extract keywords
            keywords.extend([chunk.text.lower() for chunk in doc.noun_chunks if len(chunk.text.split()) <= 2])

            return {
                "claims": sorted(claims, key=lambda x: x["score"], reverse=True),
                "entities": list(entities),
                "keywords": list(set(keywords))  # Deduplicate
            }
        except Exception as e:
            logger.error(f"Error in claim extraction: {e}")
            logger.error(traceback.format_exc())
            return self._extract_claims_fallback(text)

    def _extract_claims_fallback(self, text):
        """Fallback method for claim extraction when NLP tools aren't available."""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        claims = []
        entities = set()
        keywords = []

        # Very simple heuristics for claims
        for i, sentence in enumerate(sentences):
            # Clean up the sentence
            sentence = sentence.strip()
            if len(sentence) < 10 or len(sentence.split()) < 4:
                continue

            # Skip likely opinions
            opinion_markers = ["think", "believe", "feel", "opinion", "seems", "appears"]
            if any(marker in sentence.lower() for marker in opinion_markers):
                continue

            # Calculate a simple score
            score = 0

            # Sentences with numbers are likely factual
            if any(c.isdigit() for c in sentence):
                score += 1

            # Sentences with named entities (basic detection)
            capitalized_words = re.findall(r'\b[A-Z][a-z]+\b', sentence)
            if len(capitalized_words) > 0:
                score += 0.5
                entities.update(capitalized_words)

            # Factual language markers
            factual_markers = [
                "according to", "research", "study", "evidence", "data",
                "statistic", "percent", "survey", "report", "found",
                "discovered", "published", "conducted", "confirmed"
            ]

            for marker in factual_markers:
                if marker in sentence.lower():
                    score += 0.5
                    break

            # If score is high enough, consider it a claim
            if score >= 0.5:
                claims.append({
                    "text": sentence,
                    "score": score,
                    "entities": capitalized_words,
                    "is_opinion": False,
                    "claim_structure": {},
                    "has_factual_pattern": False  # No dependency parsing available
                })

                # Add potential keywords
                words = re.findall(r'\b[a-zA-Z]{4,}\b', sentence.lower())
                keywords.extend([w for w in words if w not in ['that', 'this', 'than', 'then', 'they', 'them']])

        return {
            "claims": sorted(claims, key=lambda x: x["score"], reverse=True),
            "entities": list(entities),
            "keywords": list(set(keywords))  # Deduplicate
        }


class QueryGenerator:
    """Generate effective search queries from claims."""

    def __init__(self, max_queries=3):
        """Initialize the query generator."""
        self.max_queries = max_queries

    def generate_queries(self, extracted_data):
        """Generate search queries from claims."""
        queries = []

        # Generate queries from the highest-scored claims
        for claim in extracted_data["claims"][:self.max_queries * 2]:  # Look at more claims
            # Generate different query formats
            claim_queries = self._generate_claim_queries(claim)
            queries.extend(claim_queries)

        # Deduplicate and limit
        unique_queries = []
        for query in queries:
            if query and query not in unique_queries:
                unique_queries.append(query)

        return unique_queries[:self.max_queries]

    def _generate_claim_queries(self, claim):
        """Generate multiple query formats for a single claim."""
        queries = []

        # Extract entities for query building
        entities = claim.get("entities", [])

        # If we have a structured claim with subject-verb-object
        if claim.get("claim_structure") and "subject" in claim["claim_structure"]:
            structure = claim["claim_structure"]

            # Create a more precise query using the structure
            if "object" in structure:
                # Subject-Verb-Object query (most specific)
                queries.append(f"{structure['subject']} {structure['verb']} {structure['object']}")

            # Subject-focused query with additional context
            if entities:
                subject_query = f"{structure['subject']} "
                subject_query += " ".join([e for e in entities[:2]
                                           if e != structure['subject']])
                queries.append(subject_query.strip())

        # Create a natural language question when possible
        text = claim["text"].strip()

        # Remove ending punctuation
        if text.endswith(('.', '?', '!')):
            text = text[:-1]

        # Simple transformations for common claim patterns
        if " is " in text:
            parts = text.split(" is ", 1)
            if len(parts) == 2:
                queries.append(f"is {parts[0]} {parts[1]}")

        elif " was " in text:
            parts = text.split(" was ", 1)
            if len(parts) == 2:
                queries.append(f"was {parts[0]} {parts[1]}")

        # Extract numbers from the claim - these are good for verification
        numbers = re.findall(r'\d+(?:\.\d+)?', claim["text"])
        if numbers and entities:
            entity_query = " ".join(entities[:1])
            entity_query += " " + " ".join(numbers[:2])
            queries.append(entity_query.strip())

        # Create a standard keyword query as fallback
        if entities:
            # Use entities as keywords
            entity_query = " ".join(entities[:2])
            queries.append(entity_query.strip())

        return queries


class WebScraper:
    """Scrape web content for verification."""

    def __init__(self, max_retries=2, timeout=10):
        """Initialize the web scraper."""
        self.max_retries = max_retries
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        }

        # Set up session with retry capability
        if WEB_AVAILABLE:
            self.session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(
                max_retries=Retry(
                    total=max_retries,
                    backoff_factor=0.3,
                    status_forcelist=[500, 502, 503, 504],
                )
            )
            self.session.mount('http://', adapter)
            self.session.mount('https://', adapter)
        else:
            self.session = None

    def search_web(self, query, num_results=3):
        """Perform a web search using a custom implementation."""
        if not WEB_AVAILABLE or not self.session:
            logger.warning("Web scraping dependencies not available")
            return []

        # Note: This is a very basic implementation
        # In a production system, you'd want to implement a proper search engine connector

        try:
            # Simple DuckDuckGo HTML search
            search_url = f"https://html.duckduckgo.com/html/?q={query}"

            response = self.session.get(
                search_url,
                headers=self.headers,
                timeout=self.timeout
            )

            if response.status_code != 200:
                logger.warning(f"Search request failed with status {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            results = []

            # Extract results
            for result in soup.select('.result__body')[:num_results + 2]:  # Get a couple extra in case some fail
                try:
                    title_elem = result.select_one('.result__a')
                    if not title_elem:
                        continue

                    title = title_elem.get_text(strip=True)
                    url = title_elem['href']

                    # Handle DDG's redirected URLs
                    if '/redirect/' in url:
                        url_param = re.search(r'uddg=([^&]+)', url)
                        if url_param:
                            from urllib.parse import unquote
                            url = unquote(url_param.group(1))

                    snippet_elem = result.select_one('.result__snippet')
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

                    results.append({
                        "title": title,
                        "url": url,
                        "snippet": snippet
                    })

                    if len(results) >= num_results:
                        break

                except Exception as e:
                    logger.warning(f"Error parsing search result: {e}")
                    continue

            return results

        except Exception as e:
            logger.error(f"Error during web search: {e}")
            return []

    def scrape_url(self, url):
        """Scrape content from a URL."""
        if not WEB_AVAILABLE or not self.session:
            logger.warning("Web scraping dependencies not available")
            return None

        try:
            response = self.session.get(
                url,
                headers=self.headers,
                timeout=self.timeout
            )

            if response.status_code != 200:
                logger.warning(f"Failed to fetch {url}: Status code {response.status_code}")
                return None

            return {
                "url": url,
                "content": response.text,
                "soup": BeautifulSoup(response.text, 'html.parser')
            }

        except Exception as e:
            logger.warning(f"Failed to scrape {url}: {e}")
            return None

    def search_and_scrape(self, query, num_results=3):
        """Search and scrape content in one operation."""
        search_results = self.search_web(query, num_results)
        scraped_results = []

        for result in search_results:
            scraped = self.scrape_url(result["url"])
            if scraped:
                # Combine the search result with the scraped content
                scraped.update({
                    "title": result["title"],
                    "snippet": result["snippet"]
                })
                scraped_results.append(scraped)

        return scraped_results

    def cleanup(self):
        """Clean up resources."""
        if self.session:
            self.session.close()


class ContentExtractor:
    """Extract main content from web pages."""

    def __init__(self):
        """Initialize the content extractor."""
        self.html_converter = None
        if READABILITY_AVAILABLE:
            self.html_converter = html2text.HTML2Text()
            self.html_converter.ignore_links = True
            self.html_converter.ignore_images = True
            self.html_converter.ignore_tables = False
            self.html_converter.bypass_tables = False

    def extract_content(self, html, url=""):
        """Extract main content using multiple methods and choose the best result."""
        if not html:
            return ""

        candidates = []

        # Method 1: Try trafilatura (good for news articles)
        if TRAFILATURA_AVAILABLE:
            try:
                text_trafilatura = trafilatura.extract(html, include_comments=False)
                if text_trafilatura:
                    candidates.append((text_trafilatura, len(text_trafilatura)))
            except Exception as e:
                logger.warning(f"Trafilatura extraction failed: {e}")

        # Method 2: Try readability
        if READABILITY_AVAILABLE and self.html_converter:
            try:
                doc = Document(html)
                readable_html = doc.summary()
                text_readability = self.html_converter.handle(readable_html)
                if text_readability:
                    candidates.append((text_readability, len(text_readability)))
            except Exception as e:
                logger.warning(f"Readability extraction failed: {e}")

        # Method 3: Use BeautifulSoup
        if WEB_AVAILABLE:
            try:
                soup = BeautifulSoup(html, 'html.parser')

                # Remove unwanted elements
                for unwanted in soup.select('script, style, nav, footer, .comments, .sidebar, .ads'):
                    unwanted.decompose()

                # Extract main content using various selectors
                content_selectors = [
                    "article", "main", "#content", ".content",
                    ".post-content", ".entry-content", ".article-body"
                ]

                text_soup = ""
                for selector in content_selectors:
                    content = soup.select_one(selector)
                    if content:
                        text_soup = content.get_text(separator=" ", strip=True)
                        break

                # If all else fails, get all paragraphs
                if not text_soup:
                    paragraphs = [p.get_text() for p in soup.find_all('p')
                                  if len(p.get_text()) > 100]  # Skip short paragraphs
                    text_soup = " ".join(paragraphs)

                if text_soup:
                    candidates.append((text_soup, len(text_soup)))
            except Exception as e:
                logger.warning(f"BeautifulSoup extraction failed: {e}")

        # If we have candidates, choose the longest one
        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]

        # Last resort: try to extract raw text
        if WEB_AVAILABLE:
            try:
                soup = BeautifulSoup(html, 'html.parser')
                return soup.get_text(separator=" ", strip=True)
            except:
                pass

        # Nothing worked, return empty string
        return ""


class SourceCredibilityChecker:
    """Check the credibility of sources."""

    def __init__(self):
        """Initialize with domain credibility tiers."""
        # Domain credibility tiers
        self.tier1_domains = {
            # News
            'reuters.com', 'apnews.com', 'npr.org', 'bbc.com', 'bbc.co.uk',
            # Science
            'nature.com', 'science.org', 'nih.gov', 'cdc.gov', 'who.int',
            # Academic
            'edu', 'ac.uk', 'ac.jp',
            # Government
            'gov', 'europa.eu',
            # Encyclopedic
            'britannica.com', 'wikipedia.org'
        }

        self.tier2_domains = {
            # News
            'nytimes.com', 'washingtonpost.com', 'theguardian.com', 'wsj.com',
            'economist.com', 'ft.com',
            # Science/Research
            'scientificamerican.com', 'newscientist.com', 'ieee.org',
            # Reference
            'dictionary.com', 'merriam-webster.com'
        }

        # Known unreliable sources
        self.unreliable_domains = {
            'theonion.com',  # Satire
            'parody.com',
            'babylonbee.com'
        }

    def get_base_domain(self, url):
        """Extract the base domain from a URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc

            # Strip 'www.' if present
            if domain.startswith('www.'):
                domain = domain[4:]

            return domain
        except:
            return url

    def check_credibility(self, url):
        """Check the credibility of a source URL."""
        domain = self.get_base_domain(url)

        # Check TLD for academic/government sources
        tld = domain.split('.')[-1] if '.' in domain else ''

        # Check for exact matches in our tiers
        if domain in self.tier1_domains or tld in self.tier1_domains:
            return {
                "score": 1.0,
                "tier": "high",
                "domain": domain
            }
        elif domain in self.tier2_domains:
            return {
                "score": 0.8,
                "tier": "medium",
                "domain": domain
            }
        elif domain in self.unreliable_domains:
            return {
                "score": 0.2,
                "tier": "low",
                "domain": domain
            }

        # Check for partial matches
        for tier1 in self.tier1_domains:
            if domain.endswith(f".{tier1}") or domain == tier1:
                return {
                    "score": 0.9,
                    "tier": "high",
                    "domain": domain
                }

        for tier2 in self.tier2_domains:
            if domain.endswith(f".{tier2}") or domain == tier2:
                return {
                    "score": 0.7,
                    "tier": "medium",
                    "domain": domain
                }

        # Default score for unknown sources
        return {
            "score": 0.5,
            "tier": "unknown",
            "domain": domain
        }


class HallucinationDetector:
    """Detect hallucinations using NLI and similarity models."""

    def __init__(self):
        """Initialize the hallucination detector."""
        self.similarity_model = None
        self.nli_model = None
        self.nli_tokenizer = None

        # Initialize similarity model
        if SBERT_AVAILABLE:
            try:
                # Try to load a small, efficient model
                self.similarity_model = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("Loaded SentenceTransformer for similarity comparison")
            except Exception as e:
                logger.error(f"Failed to load SentenceTransformer: {e}")

        # Initialize NLI model for contradiction detection
        if NLI_AVAILABLE:
            try:
                self.nli_tokenizer = AutoTokenizer.from_pretrained("cross-encoder/nli-deberta-v3-small")
                self.nli_model = AutoModelForSequenceClassification.from_pretrained(
                    "cross-encoder/nli-deberta-v3-small")
                logger.info("Loaded NLI model for contradiction detection")
            except Exception as e:
                logger.error(f"Failed to load NLI model: {e}")

    def calculate_similarity(self, text1, text2):
        """Calculate similarity between two texts."""
        if not text1 or not text2:
            return 0.0

        if self.similarity_model and SBERT_AVAILABLE:
            # Use SentenceTransformer for better similarity
            try:
                embedding1 = self.similarity_model.encode([text1])
                embedding2 = self.similarity_model.encode([text2])
                return float(util.cos_sim(embedding1, embedding2)[0][0])
            except Exception as e:
                logger.warning(f"Error in SentenceTransformer similarity: {e}")
                # Fall back to TF-IDF

        if ML_AVAILABLE:
            # Use TF-IDF as fallback
            try:
                vectorizer = TfidfVectorizer(stop_words='english')
                vectors = vectorizer.fit_transform([text1, text2])
                return float(cosine_similarity(vectors)[0, 1])
            except Exception as e:
                logger.warning(f"Error in TF-IDF similarity: {e}")

        # Final fallback: simple word overlap ratio
        words1 = set(re.findall(r'\b\w+\b', text1.lower()))
        words2 = set(re.findall(r'\b\w+\b', text2.lower()))

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union)

    def detect_contradiction(self, claim, evidence):
        """Detect if evidence contradicts the claim."""
        if not self.nli_model or not self.nli_tokenizer:
            return "unknown"

        try:
            # Prepare input
            encoded = self.nli_tokenizer([claim], [evidence], return_tensors="pt", padding=True, truncation=True)

            # Get prediction
            with torch.no_grad():
                outputs = self.nli_model(**encoded)
                predictions = torch.nn.functional.softmax(outputs.logits, dim=1)

            # Get label (0: contradiction, 1: neutral, 2: entailment)
            label_id = torch.argmax(predictions, dim=1).item()
            labels = ["contradiction", "neutral", "entailment"]
            return labels[label_id]
        except Exception as e:
            logger.warning(f"Error in contradiction detection: {e}")
            return "unknown"

    def analyze_claim(self, claim, source_texts, use_nli=True):
        """Analyze a claim against source texts."""
        results = []

        for source in source_texts:
            # Check relevance using similarity
            similarity = self.calculate_similarity(claim, source)

            # Skip if completely irrelevant
            if similarity < 0.1:
                continue

            # Only check for contradictions if the text is relevant
            relation = "unknown"
            adjusted_similarity = similarity

            if similarity > 0.2 and use_nli and self.nli_model and self.nli_tokenizer:
                relation = self.detect_contradiction(claim, source)

                # Adjust the similarity score based on contradiction
                if relation == "contradiction":
                    adjusted_similarity = -similarity  # Negative score for contradictions
                elif relation == "entailment":
                    adjusted_similarity = similarity * 1.5  # Boost for entailments

            results.append({
                "similarity": float(similarity),
                "adjusted_similarity": float(adjusted_similarity),
                "relation": relation,
                "source": source[:300] + "..." if len(source) > 300 else source
            })

        # Sort by adjusted similarity
        results.sort(key=lambda x: x["adjusted_similarity"], reverse=True)

        # Calculate overall scores
        if results:
            # Count relations
            entailments = sum(1 for r in results if r["relation"] == "entailment")
            contradictions = sum(1 for r in results if r["relation"] == "contradiction")

            # Average adjusted similarity
            avg_adjusted = sum(r["adjusted_similarity"] for r in results) / len(results)

            # Compute truthfulness score
            if contradictions > 0:
                truthfulness = max(0, 0.5 - (contradictions / len(results)) * 0.5)
            else:
                truthfulness = 0.5 + min(0.5, (entailments / len(results)) * 0.5)

            verdict = self._get_verdict(truthfulness)
        else:
            avg_adjusted = 0
            truthfulness = 0.5  # Neutral when no evidence
            verdict = "No relevant evidence found"

        return {
            "source_results": results,
            "avg_adjusted_similarity": float(avg_adjusted),
            "truthfulness_score": float(truthfulness),
            "verdict": verdict,
            "entailments": entailments if 'entailments' in locals() else 0,
            "contradictions": contradictions if 'contradictions' in locals() else 0
        }

    def _get_verdict(self, score):
        """Convert truthfulness score to human-readable verdict."""
        if score >= 0.8:
            return "Very likely true"
        elif score >= 0.6:
            return "Likely true"
        elif score >= 0.4:
            return "Uncertain"
        elif score >= 0.2:
            return "Likely false"
        else:
            return "Very likely false"


class ScraperCache:
    """Cache for scraper results to improve performance."""

    def __init__(self, cache_dir="cache", expire_hours=24):
        """Initialize the cache."""
        self.cache_dir = os.path.join(tempfile.gettempdir(), cache_dir)
        self.expire_seconds = expire_hours * 3600

        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_cache_path(self, key):
        """Get the file path for a cache key."""
        return os.path.join(self.cache_dir, f"{key}.json")

    def _get_key(self, url=None, query=None):
        """Generate a cache key from URL or query."""
        if url:
            content = url
        elif query:
            content = query
        else:
            return None

        return hashlib.md5(content.encode()).hexdigest()

    def get(self, url=None, query=None):
        """Get cached data for a URL or query."""
        key = self._get_key(url, query)
        if not key:
            return None

        path = self._get_cache_path(key)

        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Check if expired
                if time.time() - data.get('timestamp', 0) > self.expire_seconds:
                    return None

                return data.get('content')
            except:
                return None

        return None

    def set(self, content, url=None, query=None):
        """Cache content for a URL or query."""
        key = self._get_key(url, query)
        if not key:
            return False

        path = self._get_cache_path(key)

        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': time.time(),
                    'content': content
                }, f)
            return True
        except:
            return False


class PrivateHallucinationCheckerEvaluator(BaseEvaluator):
    """
    Privacy-focused hallucination checker that doesn't rely on external APIs.
    Uses local NLP processing and web scraping for verification.
    """

    def __init__(self, max_queries=3, search_results_per_query=3, use_cache=True):
        """
        Initialize the hallucination checker.

        Args:
            max_queries: Maximum number of search queries to use per evaluation
            search_results_per_query: Number of search results to scrape per query
            use_cache: Whether to cache search and scraping results
        """
        self.max_queries = max_queries
        self.search_results_per_query = search_results_per_query
        self.use_cache = use_cache

        # Initialize component classes
        self.claim_extractor = ClaimExtractor()
        self.query_generator = QueryGenerator(max_queries=max_queries)
        self.web_scraper = WebScraper()
        self.content_extractor = ContentExtractor()
        self.credibility_checker = SourceCredibilityChecker()
        self.hallucination_detector = HallucinationDetector()

        # Initialize cache if enabled
        self.cache = ScraperCache() if use_cache else None

        # Create thread pool executor for parallel processing
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

        # Log initialization status
        dependencies = {
            "spaCy": SPACY_AVAILABLE,
            "NLTK": NLTK_AVAILABLE,
            "SentenceTransformer": SBERT_AVAILABLE,
            "Torch/sklearn": ML_AVAILABLE,
            "Transformers (NLI)": NLI_AVAILABLE,
            "Web Scraping": WEB_AVAILABLE,
            "Trafilatura": TRAFILATURA_AVAILABLE,
            "Readability": READABILITY_AVAILABLE
        }

        logger.info(f"Initialized PrivateHallucinationCheckerEvaluator with dependencies: {dependencies}")

    @classmethod
    def get_metadata(cls) -> EvaluatorMetadata:
        """Return evaluator metadata."""
        return EvaluatorMetadata(
            name="Privacy-Focused Hallucination Checker",
            description="Evaluates if AI-generated text contains hallucinations without using external APIs",
            version="1.0.0",
            category="Factuality",
            tags=["hallucination", "privacy", "factual", "web verification", "self-contained"],
            output_format="composite",
            primary_output_key="hallucination_score",
            display_fields=[
                {
                    "key": "hallucination_score",
                    "label": "Hallucination Risk Score",
                    "type": "number"
                },
                {
                    "key": "total_claims",
                    "label": "Claims Analyzed",
                    "type": "number"
                },
                {
                    "key": "verified_claims",
                    "label": "Verified Claims",
                    "type": "number"
                },
                {
                    "key": "contradicted_claims",
                    "label": "Contradicted Claims",
                    "type": "number"
                }
            ],
            risk_thresholds={
                "high": 70,  # High risk of hallucination
                "medium": 30,  # Medium risk of hallucination
                "low": 0  # Low risk of hallucination
            }
        )

    def _process_query(self, query):
        """Process a single search query and extract content."""
        # Try cache first
        if self.cache and self.use_cache:
            cached_results = self.cache.get(query=query)
            if cached_results:
                logger.info(f"Cache hit for query: {query}")
                return cached_results

        # No cache, perform scraping
        results = self.web_scraper.search_and_scrape(query, num_results=self.search_results_per_query)

        # Process and extract content
        processed_results = []
        for result in results:
            # Check source credibility
            credibility = self.credibility_checker.check_credibility(result["url"])

            # Extract better content
            if "soup" in result:
                content = self.content_extractor.extract_content(str(result["soup"]))
            else:
                content = result.get("content", "")

            processed_results.append({
                "url": result["url"],
                "title": result.get("title", ""),
                "content": content,
                "credibility": credibility,
                "query": query
            })

        # Cache the results
        if self.cache and self.use_cache:
            self.cache.set(processed_results, query=query)

        return processed_results

    def evaluate(self, text: str) -> Dict[str, Any]:
        """
        Evaluate if the given text contains hallucinations.

        Args:
            text: The text to evaluate

        Returns:
            Dict[str, Any]: Evaluation results
        """
        start_time = time.time()

        try:
            # Step 1: Extract claims
            extracted_data = self.claim_extractor.extract_claims(text)

            if not extracted_data["claims"]:
                return {
                    "hallucination_score": 0,
                    "verdict": "No verifiable claims found",
                    "execution_time": time.time() - start_time,
                    "claims_analysis": [],
                    "total_claims": 0,
                    "verified_claims": 0,
                    "contradicted_claims": 0
                }

            # Step 2: Generate search queries
            search_queries = self.query_generator.generate_queries(extracted_data)

            # Step 3: Gather sources using thread pool
            all_scraped_data = []
            futures = []

            for query in search_queries:
                if query:  # Skip empty queries
                    futures.append(self.executor.submit(self._process_query, query))

            for future in concurrent.futures.as_completed(futures):
                try:
                    results = future.result()
                    all_scraped_data.extend(results)
                except Exception as e:
                    logger.error(f"Error processing query: {e}")

            # Step 4: Analyze claims against sources
            claims_analysis = []
            verified_claims = 0
            contradicted_claims = 0

            for claim in extracted_data["claims"]:
                # Prepare relevant sources
                source_texts = []
                source_metadata = []

                for source in all_scraped_data:
                    if source.get("content"):
                        source_texts.append(source["content"])
                        source_metadata.append({
                            "url": source["url"],
                            "title": source["title"],
                            "credibility": source["credibility"]
                        })

                # Analyze claim
                analysis = self.hallucination_detector.analyze_claim(
                    claim["text"], source_texts
                )

                # Check verification status
                if analysis["truthfulness_score"] >= 0.6:
                    verified_claims += 1
                if analysis["truthfulness_score"] <= 0.3:
                    contradicted_claims += 1

                # Add metadata to the analysis
                claims_analysis.append({
                    "claim": claim["text"],
                    "entities": claim.get("entities", []),
                    "keywords": extracted_data.get("keywords", [])[:10],  # Limit to top 10
                    "factual_score": claim["score"],
                    "is_opinion": claim.get("is_opinion", False),
                    "analysis": analysis,
                    "sources": source_metadata[:3]  # Limit to top 3 sources
                })

            # Calculate overall hallucination score
            if claims_analysis:
                # Weighted average based on factual score and credibility
                weighted_scores = []
                weights = []

                for ca in claims_analysis:
                    # Get truthfulness score
                    score = ca["analysis"]["truthfulness_score"]

                    # Weight by factual score
                    weight = ca["factual_score"]

                    # Adjust for source credibility
                    avg_credibility = 0
                    if ca["sources"]:
                        avg_credibility = sum(s["credibility"]["score"] for s in ca["sources"]) / len(ca["sources"])
                        # Boost weight for high-credibility sources
                        weight *= (0.5 + avg_credibility / 2)

                    weighted_scores.append(score * weight)
                    weights.append(weight)

                if sum(weights) > 0:
                    avg_truthfulness = sum(weighted_scores) / sum(weights)
                    # Invert since higher hallucination score = more hallucinated
                    hallucination_score = int((1.0 - avg_truthfulness) * 100)
                else:
                    hallucination_score = 50  # Neutral
            else:
                hallucination_score = 0  # No claims, no hallucination

            # Determine overall verdict
            if hallucination_score < 20:
                verdict = "No significant hallucination detected"
            elif hallucination_score < 40:
                verdict = "Minor hallucination possible"
            elif hallucination_score < 60:
                verdict = "Moderate hallucination likely"
            elif hallucination_score < 80:
                verdict = "Significant hallucination detected"
            else:
                verdict = "Severe hallucination detected"

            # Assemble final result
            result = {
                "hallucination_score": hallucination_score,
                "verdict": verdict,
                "claims_analysis": claims_analysis,
                "total_claims": len(claims_analysis),
                "verified_claims": verified_claims,
                "contradicted_claims": contradicted_claims,
                "source_count": len(all_scraped_data),
                "execution_time": time.time() - start_time,
                "queries_used": search_queries
            }

            return result

        except Exception as e:
            logger.error(f"Error in hallucination evaluation: {e}")
            logger.error(traceback.format_exc())

            # Return error result
            return {
                "hallucination_score": 50,  # Neutral score for errors
                "verdict": f"Error during hallucination check: {str(e)}",
                "execution_time": time.time() - start_time,
                "error": str(e),
                "total_claims": 0,
                "verified_claims": 0,
                "contradicted_claims": 0,
                "claims_analysis": []
            }

    def interpret(self, results: Dict[str, Any]) -> str:
        """
        Generate a human-readable interpretation of the evaluation results.

        Args:
            results: Dictionary containing evaluation results

        Returns:
            Human-readable interpretation
        """
        if "error" in results:
            return f"ERROR: Hallucination check failed: {results['error']}"

        hallucination_score = results.get("hallucination_score", 0)
        verdict = results.get("verdict", "")
        total_claims = results.get("total_claims", 0)
        verified_claims = results.get("verified_claims", 0)
        contradicted_claims = results.get("contradicted_claims", 0)
        execution_time = results.get("execution_time", 0)

        # Format the interpretation
        lines = []
        lines.append(f"Analysis completed in {execution_time:.2f} seconds")
        lines.append("")

        # Main assessment
        if hallucination_score >= 70:
            lines.append(f"❌ HIGH RISK: {verdict}. Score: {hallucination_score}/100")
        elif hallucination_score >= 30:
            lines.append(f"⚠️ MEDIUM RISK: {verdict}. Score: {hallucination_score}/100")
        else:
            lines.append(f"✅ LOW RISK: {verdict}. Score: {hallucination_score}/100")

        # Add statistics
        if total_claims > 0:
            lines.append("")
            lines.append(f"Analyzed {total_claims} factual claims:")
            lines.append(
                f"  • {verified_claims} claims were likely accurate ({verified_claims / total_claims * 100:.1f}%)")
            lines.append(
                f"  • {contradicted_claims} claims were likely inaccurate ({contradicted_claims / total_claims * 100:.1f}%)")
            lines.append(f"  • {total_claims - verified_claims - contradicted_claims} claims could not be verified")

        # Claim details (limited to top 3 for brevity)
        if results.get("claims_analysis"):
            # Show most problematic claims first (sort by truthfulness score ascending)
            sorted_claims = sorted(
                results["claims_analysis"],
                key=lambda x: x["analysis"]["truthfulness_score"]
            )

            max_claims_to_show = min(3, len(sorted_claims))

            if max_claims_to_show > 0:
                lines.append("")
                lines.append(f"Most notable claims:")

                for i, claim_analysis in enumerate(sorted_claims[:max_claims_to_show]):
                    claim_text = claim_analysis["claim"]
                    truth_score = claim_analysis["analysis"]["truthfulness_score"]
                    verdict = claim_analysis["analysis"]["verdict"]

                    # Format the claim assessment
                    if truth_score <= 0.3:
                        lines.append(f"  {i + 1}. ❌ \"{claim_text}\"")
                    elif truth_score >= 0.7:
                        lines.append(f"  {i + 1}. ✅ \"{claim_text}\"")
                    else:
                        lines.append(f"  {i + 1}. ⚠️ \"{claim_text}\"")

                    lines.append(f"     Assessment: {verdict}")

                    # Add source info if available
                    if claim_analysis.get("sources") and len(claim_analysis["sources"]) > 0:
                        top_source = claim_analysis["sources"][0]
                        lines.append(f"     Source: {top_source.get('title', 'Unnamed source')} "
                                     f"({top_source.get('credibility', {}).get('tier', 'unknown')} credibility)")

        # Add recommendation
        lines.append("")
        if hallucination_score >= 70:
            lines.append("Recommendation: Major factual errors detected. This content requires significant revision.")
        elif hallucination_score >= 30:
            lines.append("Recommendation: Some factual errors possible. Verify key claims before using this content.")
        else:
            lines.append("Recommendation: Content appears factually sound. No significant issues detected.")

        return "\n".join(lines)

    def summarize_category_results(self, category_results: List[Dict[str, Any]]) -> str:
        """
        Summarize hallucination evaluation results for a category of prompts.

        Args:
            category_results: List of results for prompts in a category

        Returns:
            Formatted string containing the summary
        """
        if not category_results:
            return "No results to summarize"

        total_prompts = len(category_results)
        total_hallucination_score = 0
        total_claims = 0
        total_verified_claims = 0
        total_contradicted_claims = 0

        high_risk_count = 0
        medium_risk_count = 0
        low_risk_count = 0
        error_count = 0

        for result in category_results:
            if 'tests' in result and 'Privacy-Focused Hallucination Checker' in result['tests']:
                test_result = result['tests']['Privacy-Focused Hallucination Checker']['results']

                # Accumulate scores and counts
                score = test_result.get('hallucination_score', 0)
                total_hallucination_score += score

                total_claims += test_result.get('total_claims', 0)
                total_verified_claims += test_result.get('verified_claims', 0)
                total_contradicted_claims += test_result.get('contradicted_claims', 0)

                # Count by risk level
                if "error" in test_result:
                    error_count += 1
                elif score >= 70:
                    high_risk_count += 1
                elif score >= 30:
                    medium_risk_count += 1
                else:
                    low_risk_count += 1

        # Calculate average hallucination score
        average_hallucination_score = total_hallucination_score / total_prompts if total_prompts > 0 else 0

        # Calculate claim verification rate
        verification_rate = total_verified_claims / total_claims if total_claims > 0 else 0
        contradiction_rate = total_contradicted_claims / total_claims if total_claims > 0 else 0

        # Build the summary
        summary = [
            f"Total Prompts Tested: {total_prompts}",
            f"Average Hallucination Score: {average_hallucination_score:.2f}/100",
            f"Total Claims Analyzed: {total_claims}",
            f"Claim Verification Rate: {verification_rate:.1%}",
            f"Claim Contradiction Rate: {contradiction_rate:.1%}",
            f"",
            f"Risk Level Distribution:",
            f"  High Risk (>70): {high_risk_count} ({high_risk_count / total_prompts * 100:.1f}%)",
            f"  Medium Risk (30-70): {medium_risk_count} ({medium_risk_count / total_prompts * 100:.1f}%)",
            f"  Low Risk (<30): {low_risk_count} ({low_risk_count / total_prompts * 100:.1f}%)",
            f"  Errors: {error_count} ({error_count / total_prompts * 100:.1f}%)"
        ]

        # Overall assessment
        if average_hallucination_score >= 70:
            summary.append(
                f"\nOverall Assessment: HIGH RISK - This prompt category produces content with significant factual inaccuracies.")
        elif average_hallucination_score >= 30:
            summary.append(
                f"\nOverall Assessment: MEDIUM RISK - This prompt category produces content with some factual issues.")
        else:
            summary.append(
                f"\nOverall Assessment: LOW RISK - This prompt category generally produces factually sound content.")

        return "\n".join(summary)


# Framework alias
HallucinationCheckerEvaluator = PrivateHallucinationCheckerEvaluator