"""Advanced embedding management system using sentence-transformers with FAISS caching and advanced similarity operations."""

import logging
import os
import pickle
import time
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
from pathlib import Path
import numpy as np
import pandas as pd
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json

# Core embedding libraries
from sentence_transformers import SentenceTransformer, util
import faiss
from sklearn.cluster import DBSCAN, KMeans
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.manifold import TSNE
import umap

# Visualization
import matplotlib.pyplot as plt
import seaborn as sns

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingConfig:
    """Configuration for embedding models and operations."""
    model_name: str = "all-MiniLM-L6-v2"
    cache_dir: str = "./embedding_cache"
    faiss_index_type: str = "IVFFlat"  # "Flat", "IVFFlat", "HNSW"
    similarity_threshold: float = 0.7
    clustering_eps: float = 0.3
    clustering_min_samples: int = 2
    max_cache_size_mb: int = 1000
    enable_quantization: bool = True
    use_gpu: bool = False


@dataclass
class SimilarityResult:
    """Result of similarity search operation."""
    query_id: str
    matches: List[Dict[str, Any]]
    query_embedding: np.ndarray
    search_time: float
    total_matches: int


@dataclass
class ClusteringResult:
    """Result of entity clustering operation."""
    cluster_id: int
    entities: List[Dict[str, Any]]
    centroid: np.ndarray
    cluster_size: int
    confidence: float
    representative_entity: Optional[Dict[str, Any]] = None


@dataclass
class QualityMetrics:
    """Embedding quality evaluation metrics."""
    model_name: str
    coherence_score: float
    diversity_score: float
    stability_score: float
    evaluation_time: float
    sample_size: int
    metrics: Dict[str, float]


class EmbeddingManager:
    """Advanced embedding management with FAISS caching, similarity search, and clustering."""
    
    def __init__(self, config: Optional[EmbeddingConfig] = None):
        """Initialize the embedding manager.
        
        Args:
            config: Configuration for embedding operations
        """
        self.config = config or EmbeddingConfig()
        self.models: Dict[str, SentenceTransformer] = {}
        self.faiss_indexes: Dict[str, Any] = {}
        self.embedding_cache: Dict[str, np.ndarray] = {}
        self.metadata_cache: Dict[str, Dict[str, Any]] = {}
        
        # Performance tracking
        self.operation_metrics: Dict[str, List[float]] = {}
        self.cache_hits = 0
        self.cache_misses = 0
        
        # Initialize cache directory
        os.makedirs(self.config.cache_dir, exist_ok=True)
        
        # Load or initialize FAISS index
        self._initialize_faiss_index()
        
        # Load default model
        self._load_model(self.config.model_name)
        
        logger.info(f"EmbeddingManager initialized with model: {self.config.model_name}")
    
    def _initialize_faiss_index(self):
        """Initialize FAISS index for vector similarity search."""
        try:
            index_path = os.path.join(self.config.cache_dir, "faiss_index.bin")
            
            if os.path.exists(index_path):
                # Load existing index
                self.faiss_indexes["main"] = faiss.read_index(index_path)
                logger.info("Loaded existing FAISS index")
            else:
                # Create new index
                dimension = self._get_model_dimension(self.config.model_name)
                
                if self.config.faiss_index_type == "Flat":
                    index = faiss.IndexFlatIP(dimension)  # Inner product for cosine similarity
                elif self.config.faiss_index_type == "IVFFlat":
                    nlist = min(100, max(1, dimension // 10))  # Number of clusters
                    quantizer = faiss.IndexFlatIP(dimension)
                    index = faiss.IndexIVFFlat(quantizer, dimension, nlist, faiss.METRIC_INNER_PRODUCT)
                elif self.config.faiss_index_type == "HNSW":
                    index = faiss.IndexHNSWFlat(dimension, 32)  # 32 neighbors
                    index.hnsw.efConstruction = 200
                    index.hnsw.efSearch = 100
                else:
                    index = faiss.IndexFlatIP(dimension)
                
                # Enable quantization if requested
                if self.config.enable_quantization:
                    index = faiss.IndexIDMap2(index)
                
                self.faiss_indexes["main"] = index
                logger.info(f"Created new FAISS index: {self.config.faiss_index_type}")
                
        except Exception as e:
            logger.error(f"Failed to initialize FAISS index: {e}")
            # Fallback to simple numpy-based similarity
            self.faiss_indexes["main"] = None
    
    def _get_model_dimension(self, model_name: str) -> int:
        """Get the embedding dimension for a model."""
        try:
            # Try to get dimension from model info
            model = SentenceTransformer(model_name)
            test_embedding = model.encode(["test"], convert_to_tensor=False)
            return test_embedding.shape[1]
        except Exception:
            # Default dimensions for common models
            default_dimensions = {
                "all-MiniLM-L6-v2": 384,
                "all-mpnet-base-v2": 768,
                "all-MiniLM-L12-v2": 384,
                "paraphrase-multilingual-MiniLM-L12-v2": 384
            }
            return default_dimensions.get(model_name, 384)
    
    def _load_model(self, model_name: str) -> bool:
        """Load an embedding model."""
        try:
            if model_name not in self.models:
                logger.info(f"Loading embedding model: {model_name}")
                model = SentenceTransformer(model_name, cache_folder=self.config.cache_dir)
                self.models[model_name] = model
                
                # Warm up the model
                _ = model.encode(["warmup"], convert_to_tensor=False)
                
                logger.info(f"Successfully loaded model: {model_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {e}")
            return False
    
    def generate_embeddings(self, texts: List[str], model_name: Optional[str] = None,
                           cache_key: Optional[str] = None, batch_size: int = 32) -> np.ndarray:
        """Generate embeddings for a list of texts with caching.
        
        Args:
            texts: List of text strings to embed
            model_name: Name of the model to use
            cache_key: Optional cache key for the texts
            batch_size: Batch size for processing
            
        Returns:
            Array of embeddings
        """
        model_name = model_name or self.config.model_name
        
        if not self._load_model(model_name):
            raise RuntimeError(f"Failed to load model: {model_name}")
        
        # Check cache first
        if cache_key and cache_key in self.embedding_cache:
            self.cache_hits += 1
            logger.debug(f"Cache hit for key: {cache_key}")
            return self.embedding_cache[cache_key]
        
        self.cache_misses += 1
        start_time = time.time()
        
        try:
            model = self.models[model_name]
            
            # Process in batches for memory efficiency
            all_embeddings = []
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                batch_embeddings = model.encode(batch, convert_to_tensor=False, show_progress_bar=False)
                all_embeddings.append(batch_embeddings)
            
            embeddings = np.vstack(all_embeddings)
            
            # Cache the results
            if cache_key:
                self.embedding_cache[cache_key] = embeddings
                self._save_cache_metadata(cache_key, {
                    'model_name': model_name,
                    'text_count': len(texts),
                    'dimension': embeddings.shape[1],
                    'created_at': datetime.now().isoformat()
                })
            
            processing_time = time.time() - start_time
            self._track_metric('embedding_generation', processing_time)
            
            logger.debug(f"Generated embeddings for {len(texts)} texts in {processing_time:.3f}s")
            return embeddings
            
        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise
    
    def _save_cache_metadata(self, cache_key: str, metadata: Dict[str, Any]):
        """Save metadata for cached embeddings."""
        try:
            metadata_path = os.path.join(self.config.cache_dir, f"{cache_key}_metadata.json")
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save cache metadata: {e}")
    
    def similarity_search(self, query_text: str, candidate_texts: List[str],
                        candidate_ids: Optional[List[str]] = None,
                        threshold: Optional[float] = None,
                        top_k: int = 10,
                        model_name: Optional[str] = None) -> SimilarityResult:
        """Perform similarity search with configurable threshold.
        
        Args:
            query_text: Query text to search for
            candidate_texts: List of candidate texts
            candidate_ids: Optional IDs for candidates
            threshold: Similarity threshold (uses config default if None)
            top_k: Maximum number of results
            model_name: Model to use for embeddings
            
        Returns:
            SimilarityResult with matches and metadata
        """
        start_time = time.time()
        threshold = threshold or self.config.similarity_threshold
        
        try:
            # Generate embeddings
            query_embedding = self.generate_embeddings([query_text], model_name)[0]
            candidate_embeddings = self.generate_embeddings(candidate_texts, model_name)
            
            # Calculate similarities
            similarities = util.pytorch_cos_sim(query_embedding, candidate_embeddings)[0].cpu().numpy()
            
            # Find matches above threshold
            matches = []
            for i, similarity in enumerate(similarities):
                if similarity >= threshold:
                    match = {
                        'id': candidate_ids[i] if candidate_ids else str(i),
                        'text': candidate_texts[i],
                        'similarity': float(similarity),
                        'rank': len(matches) + 1
                    }
                    matches.append(match)
            
            # Sort by similarity and limit results
            matches.sort(key=lambda x: x['similarity'], reverse=True)
            matches = matches[:top_k]
            
            search_time = time.time() - start_time
            self._track_metric('similarity_search', search_time)
            
            result = SimilarityResult(
                query_id=hashlib.md5(query_text.encode()).hexdigest()[:8],
                matches=matches,
                query_embedding=query_embedding,
                search_time=search_time,
                total_matches=len(matches)
            )
            
            logger.info(f"Similarity search completed: {len(matches)} matches above threshold {threshold}")
            return result
            
        except Exception as e:
            logger.error(f"Similarity search failed: {e}")
            raise
    
    def find_duplicate_entities(self, entities: List[Dict[str, Any]],
                              threshold: float = 0.85,
                              model_name: Optional[str] = None) -> List[List[Dict[str, Any]]]:
        """Find duplicate entities across files using embedding similarity.
        
        Args:
            entities: List of entity dictionaries
            threshold: Similarity threshold for duplicates
            model_name: Model to use for embeddings
            
        Returns:
            List of duplicate groups
        """
        try:
            if len(entities) < 2:
                return []
            
            # Extract entity texts for embedding
            entity_texts = []
            for entity in entities:
                # Create comprehensive text representation
                text_parts = [
                    entity.get('name', ''),
                    entity.get('entity_type', ''),
                    entity.get('source_column', ''),
                    str(entity.get('attributes', {}))
                ]
                entity_text = ' | '.join(filter(None, text_parts))
                entity_texts.append(entity_text)
            
            # Generate embeddings
            embeddings = self.generate_embeddings(entity_texts, model_name)
            
            # Find duplicates using clustering
            duplicate_groups = self._cluster_similar_entities(embeddings, entities, threshold)
            
            # Filter out single-entity clusters
            duplicate_groups = [group for group in duplicate_groups if len(group) > 1]
            
            logger.info(f"Found {len(duplicate_groups)} duplicate groups with {sum(len(g) for g in duplicate_groups)} total entities")
            return duplicate_groups
            
        except Exception as e:
            logger.error(f"Duplicate detection failed: {e}")
            return []
    
    def _cluster_similar_entities(self, embeddings: np.ndarray, entities: List[Dict[str, Any]],
                                threshold: float) -> List[List[Dict[str, Any]]]:
        """Cluster entities based on embedding similarity."""
        try:
            # Convert threshold to clustering parameters
            eps = 1.0 - threshold  # DBSCAN eps parameter
            
            # Perform clustering
            clustering = DBSCAN(eps=eps, min_samples=2, metric='cosine')
            cluster_labels = clustering.fit_predict(embeddings)
            
            # Group entities by cluster
            clusters = {}
            for i, label in enumerate(cluster_labels):
                if label not in clusters:
                    clusters[label] = []
                clusters[label].append(entities[i])
            
            # Convert to list format
            cluster_groups = list(clusters.values())
            
            return cluster_groups
            
        except Exception as e:
            logger.error(f"Entity clustering failed: {e}")
            return []
    
    def cluster_similar_entities(self, entities: List[Dict[str, Any]],
                               n_clusters: Optional[int] = None,
                               model_name: Optional[str] = None) -> List[ClusteringResult]:
        """Cluster entities into semantic groups.
        
        Args:
            entities: List of entity dictionaries
            n_clusters: Number of clusters (auto-determined if None)
            model_name: Model to use for embeddings
            
        Returns:
            List of ClusteringResult objects
        """
        try:
            if len(entities) < 2:
                return []
            
            # Generate embeddings
            entity_texts = [entity.get('name', '') for entity in entities]
            embeddings = self.generate_embeddings(entity_texts, model_name)
            
            # Determine number of clusters
            if n_clusters is None:
                n_clusters = min(10, max(2, len(entities) // 5))
            
            # Perform clustering
            clustering = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            cluster_labels = clustering.fit_predict(embeddings)
            
            # Create cluster results
            clusters = {}
            for i, label in enumerate(cluster_labels):
                if label not in clusters:
                    clusters[label] = []
                clusters[label].append(entities[i])
            
            # Convert to ClusteringResult format
            cluster_results = []
            for cluster_id, cluster_entities in clusters.items():
                # Calculate centroid
                cluster_embeddings = embeddings[cluster_labels == cluster_id]
                centroid = np.mean(cluster_embeddings, axis=0)
                
                # Find representative entity (closest to centroid)
                distances = np.linalg.norm(cluster_embeddings - centroid, axis=1)
                representative_idx = np.argmin(distances)
                representative_entity = cluster_entities[representative_idx]
                
                # Calculate cluster confidence
                avg_distance = np.mean(distances)
                confidence = max(0, 1 - avg_distance / np.linalg.norm(centroid))
                
                cluster_result = ClusteringResult(
                    cluster_id=cluster_id,
                    entities=cluster_entities,
                    centroid=centroid,
                    cluster_size=len(cluster_entities),
                    confidence=confidence,
                    representative_entity=representative_entity
                )
                cluster_results.append(cluster_result)
            
            logger.info(f"Clustered {len(entities)} entities into {len(cluster_results)} groups")
            return cluster_results
            
        except Exception as e:
            logger.error(f"Entity clustering failed: {e}")
            return []
    
    def semantic_search_in_graph(self, query_text: str, graph_entities: List[Dict[str, Any]],
                                threshold: float = 0.6,
                                top_k: int = 20,
                                model_name: Optional[str] = None) -> SimilarityResult:
        """Perform semantic search within graph entities.
        
        Args:
            query_text: Query text
            graph_entities: List of entities from the graph
            threshold: Similarity threshold
            top_k: Maximum number of results
            model_name: Model to use for embeddings
            
        Returns:
            SimilarityResult with graph entity matches
        """
        try:
            # Extract entity information for search
            entity_texts = []
            entity_ids = []
            
            for entity in graph_entities:
                # Create rich text representation
                text_parts = [
                    entity.get('name', ''),
                    entity.get('entity_type', ''),
                    entity.get('source_column', ''),
                    str(entity.get('attributes', {}))
                ]
                entity_text = ' | '.join(filter(None, text_parts))
                entity_texts.append(entity_text)
                entity_ids.append(entity.get('id', str(len(entity_ids))))
            
            # Perform similarity search
            result = self.similarity_search(
                query_text=query_text,
                candidate_texts=entity_texts,
                candidate_ids=entity_ids,
                threshold=threshold,
                top_k=top_k,
                model_name=model_name
            )
            
            logger.info(f"Semantic graph search completed: {result.total_matches} matches")
            return result
            
        except Exception as e:
            logger.error(f"Semantic graph search failed: {e}")
            raise
    
    def update_faiss_index(self, new_embeddings: np.ndarray, new_ids: List[str],
                          model_name: Optional[str] = None):
        """Update FAISS index with new embeddings incrementally.
        
        Args:
            new_embeddings: New embeddings to add
            new_ids: IDs for the new embeddings
            model_name: Model used for embeddings
        """
        try:
            if self.faiss_indexes["main"] is None:
                logger.warning("FAISS index not available, skipping update")
                return
            
            # Add new embeddings to index
            if hasattr(self.faiss_indexes["main"], 'add_with_ids'):
                self.faiss_indexes["main"].add_with_ids(new_embeddings, np.array(new_ids))
            else:
                self.faiss_indexes["main"].add(new_embeddings)
            
            # Save updated index
            index_path = os.path.join(self.config.cache_dir, "faiss_index.bin")
            faiss.write_index(self.faiss_indexes["main"], index_path)
            
            logger.info(f"Updated FAISS index with {len(new_embeddings)} new embeddings")
            
        except Exception as e:
            logger.error(f"Failed to update FAISS index: {e}")
    
    def reduce_dimensions_umap(self, embeddings: np.ndarray, n_components: int = 2,
                              n_neighbors: int = 15, min_dist: float = 0.1,
                              random_state: int = 42) -> np.ndarray:
        """Reduce embedding dimensions using UMAP for visualization.
        
        Args:
            embeddings: Input embeddings
            n_components: Target dimensions
            n_neighbors: Number of neighbors for UMAP
            min_dist: Minimum distance between points
            random_state: Random seed
            
        Returns:
            Reduced dimension embeddings
        """
        try:
            start_time = time.time()
            
            # Apply UMAP
            reducer = umap.UMAP(
                n_components=n_components,
                n_neighbors=n_neighbors,
                min_dist=min_dist,
                random_state=random_state,
                metric='cosine'
            )
            
            reduced_embeddings = reducer.fit_transform(embeddings)
            
            processing_time = time.time() - start_time
            self._track_metric('umap_reduction', processing_time)
            
            logger.info(f"UMAP reduction completed: {embeddings.shape[1]} -> {n_components} dimensions")
            return reduced_embeddings
            
        except Exception as e:
            logger.error(f"UMAP dimension reduction failed: {e}")
            raise
    
    def visualize_embeddings(self, embeddings: np.ndarray, labels: Optional[List[str]] = None,
                            title: str = "Embedding Visualization",
                            save_path: Optional[str] = None,
                            use_umap: bool = True):
        """Visualize embeddings using UMAP or t-SNE.
        
        Args:
            embeddings: Embeddings to visualize
            labels: Optional labels for points
            title: Plot title
            save_path: Optional path to save the plot
            use_umap: Whether to use UMAP (True) or t-SNE (False)
        """
        try:
            # Reduce dimensions for visualization
            if use_umap:
                reduced_embeddings = self.reduce_dimensions_umap(embeddings, n_components=2)
            else:
                # Use t-SNE as alternative
                tsne = TSNE(n_components=2, random_state=42, perplexity=min(30, len(embeddings) - 1))
                reduced_embeddings = tsne.fit_transform(embeddings)
            
            # Create visualization
            plt.figure(figsize=(12, 8))
            
            if labels:
                # Color by labels
                unique_labels = list(set(labels))
                colors = plt.cm.Set3(np.linspace(0, 1, len(unique_labels)))
                
                for i, label in enumerate(unique_labels):
                    mask = [l == label for l in labels]
                    plt.scatter(reduced_embeddings[mask, 0], reduced_embeddings[mask, 1],
                               c=[colors[i]], label=label, alpha=0.7)
                
                plt.legend()
            else:
                plt.scatter(reduced_embeddings[:, 0], reduced_embeddings[:, 1], alpha=0.7)
            
            plt.title(title)
            plt.xlabel("Component 1")
            plt.ylabel("Component 2")
            plt.grid(True, alpha=0.3)
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                logger.info(f"Visualization saved to {save_path}")
            
            plt.show()
            
        except Exception as e:
            logger.error(f"Embedding visualization failed: {e}")
    
    def evaluate_embedding_quality(self, embeddings: np.ndarray, texts: List[str],
                                 model_name: str) -> QualityMetrics:
        """Evaluate the quality of embeddings.
        
        Args:
            embeddings: Embeddings to evaluate
            texts: Original texts
            model_name: Name of the model used
            
        Returns:
            QualityMetrics object with evaluation results
        """
        try:
            start_time = time.time()
            
            # Calculate coherence (average similarity within clusters)
            coherence_score = self._calculate_coherence_score(embeddings)
            
            # Calculate diversity (spread of embeddings)
            diversity_score = self._calculate_diversity_score(embeddings)
            
            # Calculate stability (consistency across similar texts)
            stability_score = self._calculate_stability_score(embeddings, texts)
            
            evaluation_time = time.time() - start_time
            
            metrics = QualityMetrics(
                model_name=model_name,
                coherence_score=coherence_score,
                diversity_score=diversity_score,
                stability_score=stability_score,
                evaluation_time=evaluation_time,
                sample_size=len(embeddings),
                metrics={
                    'coherence': coherence_score,
                    'diversity': diversity_score,
                    'stability': stability_score,
                    'avg_similarity': float(np.mean(cosine_similarity(embeddings)))
                }
            )
            
            logger.info(f"Embedding quality evaluation completed for {model_name}")
            return metrics
            
        except Exception as e:
            logger.error(f"Embedding quality evaluation failed: {e}")
            raise
    
    def _calculate_coherence_score(self, embeddings: np.ndarray) -> float:
        """Calculate coherence score (average similarity within clusters)."""
        try:
            # Use simple clustering to find groups
            n_clusters = min(5, max(2, len(embeddings) // 10))
            clustering = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            cluster_labels = clustering.fit_predict(embeddings)
            
            # Calculate average similarity within clusters
            intra_cluster_similarities = []
            for cluster_id in range(n_clusters):
                cluster_mask = cluster_labels == cluster_id
                if np.sum(cluster_mask) > 1:
                    cluster_embeddings = embeddings[cluster_mask]
                    similarities = cosine_similarity(cluster_embeddings)
                    # Get upper triangle (excluding diagonal)
                    upper_tri = similarities[np.triu_indices_from(similarities, k=1)]
                    if len(upper_tri) > 0:
                        intra_cluster_similarities.extend(upper_tri)
            
            return float(np.mean(intra_cluster_similarities)) if intra_cluster_similarities else 0.0
            
        except Exception:
            return 0.0
    
    def _calculate_diversity_score(self, embeddings: np.ndarray) -> float:
        """Calculate diversity score (spread of embeddings)."""
        try:
            # Calculate pairwise distances
            distances = []
            for i in range(len(embeddings)):
                for j in range(i + 1, len(embeddings)):
                    dist = np.linalg.norm(embeddings[i] - embeddings[j])
                    distances.append(dist)
            
            # Diversity is the average distance
            return float(np.mean(distances)) if distances else 0.0
            
        except Exception:
            return 0.0
    
    def _calculate_stability_score(self, embeddings: np.ndarray, texts: List[str]) -> float:
        """Calculate stability score (consistency across similar texts)."""
        try:
            # Simple approach: check if very similar texts have similar embeddings
            stability_scores = []
            
            for i in range(len(texts)):
                for j in range(i + 1, len(texts)):
                    # Simple text similarity (word overlap)
                    words_i = set(texts[i].lower().split())
                    words_j = set(texts[j].lower().split())
                    
                    if len(words_i) > 0 and len(words_j) > 0:
                        text_similarity = len(words_i.intersection(words_j)) / len(words_i.union(words_j))
                        
                        if text_similarity > 0.8:  # High text similarity
                            embedding_similarity = cosine_similarity([embeddings[i]], [embeddings[j]])[0][0]
                            # Stability: embedding similarity should be high for similar texts
                            stability = min(1.0, embedding_similarity / text_similarity)
                            stability_scores.append(stability)
            
            return float(np.mean(stability_scores)) if stability_scores else 0.0
            
        except Exception:
            return 0.0
    
    def compare_models(self, texts: List[str], model_names: List[str]) -> Dict[str, QualityMetrics]:
        """Compare multiple embedding models on the same texts.
        
        Args:
            texts: Texts to evaluate
            model_names: List of model names to compare
            
        Returns:
            Dictionary mapping model names to QualityMetrics
        """
        try:
            results = {}
            
            for model_name in model_names:
                logger.info(f"Evaluating model: {model_name}")
                
                # Load model if not already loaded
                if not self._load_model(model_name):
                    logger.warning(f"Skipping model {model_name} due to loading failure")
                    continue
                
                # Generate embeddings
                embeddings = self.generate_embeddings(texts, model_name)
                
                # Evaluate quality
                quality_metrics = self.evaluate_embedding_quality(embeddings, texts, model_name)
                results[model_name] = quality_metrics
            
            # Log comparison summary
            if results:
                logger.info("Model comparison completed:")
                for model_name, metrics in results.items():
                    logger.info(f"  {model_name}: Coherence={metrics.coherence_score:.3f}, "
                              f"Diversity={metrics.diversity_score:.3f}, "
                              f"Stability={metrics.stability_score:.3f}")
            
            return results
            
        except Exception as e:
            logger.error(f"Model comparison failed: {e}")
            return {}
    
    def ensemble_similarity_search(self, query_text: str, candidate_texts: List[str],
                                 model_names: List[str],
                                 weights: Optional[List[float]] = None,
                                 threshold: float = 0.7,
                                 top_k: int = 10) -> SimilarityResult:
        """Perform ensemble similarity search using multiple models.
        
        Args:
            query_text: Query text
            candidate_texts: Candidate texts
            model_names: List of models to use
            weights: Optional weights for each model (equal if None)
            threshold: Similarity threshold
            top_k: Maximum number of results
            
        Returns:
            SimilarityResult with ensemble scoring
        """
        try:
            if not model_names:
                raise ValueError("At least one model must be specified")
            
            # Set equal weights if not provided
            if weights is None:
                weights = [1.0 / len(model_names)] * len(model_names)
            
            if len(weights) != len(model_names):
                raise ValueError("Number of weights must match number of models")
            
            # Get embeddings from each model
            all_embeddings = {}
            for model_name in model_names:
                if self._load_model(model_name):
                    embeddings = self.generate_embeddings(candidate_texts, model_name)
                    all_embeddings[model_name] = embeddings
            
            if not all_embeddings:
                raise RuntimeError("No models could be loaded")
            
            # Calculate ensemble similarities
            query_embeddings = {}
            ensemble_similarities = np.zeros(len(candidate_texts))
            
            for i, model_name in enumerate(model_names):
                if model_name in all_embeddings:
                    # Get query embedding for this model
                    query_embedding = self.generate_embeddings([query_text], model_name)[0]
                    query_embeddings[model_name] = query_embedding
                    
                    # Calculate similarities for this model
                    similarities = util.pytorch_cos_sim(query_embedding, all_embeddings[model_name])[0].cpu().numpy()
                    
                    # Weight and accumulate
                    ensemble_similarities += weights[i] * similarities
            
            # Find matches above threshold
            matches = []
            for i, similarity in enumerate(ensemble_similarities):
                if similarity >= threshold:
                    match = {
                        'id': str(i),
                        'text': candidate_texts[i],
                        'similarity': float(similarity),
                        'rank': len(matches) + 1
                    }
                    matches.append(match)
            
            # Sort by similarity and limit results
            matches.sort(key=lambda x: x['similarity'], reverse=True)
            matches = matches[:top_k]
            
            # Use first model's query embedding for result
            first_model = list(query_embeddings.keys())[0]
            query_embedding = query_embeddings[first_model]
            
            result = SimilarityResult(
                query_id=hashlib.md5(query_text.encode()).hexdigest()[:8],
                matches=matches,
                query_embedding=query_embedding,
                search_time=0.0,  # Not tracking time for ensemble
                total_matches=len(matches)
            )
            
            logger.info(f"Ensemble similarity search completed: {len(matches)} matches using {len(model_names)} models")
            return result
            
        except Exception as e:
            logger.error(f"Ensemble similarity search failed: {e}")
            raise
    
    def _track_metric(self, operation: str, time_taken: float):
        """Track performance metrics for operations."""
        if operation not in self.operation_metrics:
            self.operation_metrics[operation] = []
        self.operation_metrics[operation].append(time_taken)
        
        # Keep only last 100 measurements
        if len(self.operation_metrics[operation]) > 100:
            self.operation_metrics[operation] = self.operation_metrics[operation][-100:]
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for the embedding manager."""
        metrics = {
            'cache_stats': {
                'hits': self.cache_hits,
                'misses': self.cache_misses,
                'hit_rate': self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0.0
            },
            'operation_metrics': {},
            'loaded_models': list(self.models.keys()),
            'faiss_index_type': self.config.faiss_index_type
        }
        
        # Calculate operation statistics
        for operation, times in self.operation_metrics.items():
            if times:
                metrics['operation_metrics'][operation] = {
                    'count': len(times),
                    'avg_time': np.mean(times),
                    'min_time': np.min(times),
                    'max_time': np.max(times),
                    'std_time': np.std(times)
                }
        
        return metrics
    
    def clear_cache(self):
        """Clear the embedding cache."""
        self.embedding_cache.clear()
        self.metadata_cache.clear()
        self.cache_hits = 0
        self.cache_misses = 0
        logger.info("Embedding cache cleared")
    
    def close(self):
        """Clean up resources."""
        try:
            # Save FAISS index
            if self.faiss_indexes.get("main") is not None:
                index_path = os.path.join(self.config.cache_dir, "faiss_index.bin")
                faiss.write_index(self.faiss_indexes["main"], index_path)
                logger.info("FAISS index saved")
            
            # Clear caches
            self.clear_cache()
            
            logger.info("EmbeddingManager closed successfully")
            
        except Exception as e:
            logger.error(f"Error during EmbeddingManager cleanup: {e}")
