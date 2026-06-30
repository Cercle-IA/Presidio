from typing import List
from presidio_analyzer import RecognizerResult
from entity_refiners import EntityRefinerManager
from post_processors import DeduplicationProcessor, OverlapResolver
from post_processors.cleanup_processor import CleanupProcessor
import logging

logger = logging.getLogger(__name__)

class AnalysisPipeline:
    def __init__(self):
        self.refiner_manager = EntityRefinerManager()
        self.cleanup_processor = CleanupProcessor()
        self.overlap_resolver = OverlapResolver()
        self.deduplicator = DeduplicationProcessor()
        logger.info("🚀 Pipeline d'analyse initialisé avec nettoyage avancé")
    
    def process(self, text: str, results: List[RecognizerResult], allow_list_terms: List[str]) -> List[RecognizerResult]:
        """Traite les résultats à travers le pipeline complet"""
        # 1. Filtrage allow-list
        filtered_results = self._filter_allow_list(results, allow_list_terms, text)
        
        # 2. Raffinement individuel des entités
        refined_results = []
        for result in filtered_results:
            refined_coords = self.refiner_manager.refine_entity(
                text, 
                result.entity_type, 
                result.start, 
                result.end
            )
            
            if refined_coords is not None:
                # Créer un nouveau RecognizerResult avec les coordonnées raffinées
                refined_result = RecognizerResult(
                    entity_type=result.entity_type,
                    start=refined_coords[0],
                    end=refined_coords[1],
                    score=result.score
                )
                refined_results.append(refined_result)
        
        # 3. Nettoyage avancé des résultats
        cleaned_results = self.cleanup_processor.process(refined_results)
        
        # 4. Résolution des chevauchements
        resolved_results = self.overlap_resolver.process(cleaned_results, text)
        
        # 5. Déduplication
        final_results = self.deduplicator.process(resolved_results, text)
        
        logger.info(f"🎯 Pipeline complet: {len(results)} -> {len(final_results)} entités")
        return final_results
    
    def _filter_allow_list(self, results: List[RecognizerResult], allow_list_terms: List[str], text: str) -> List[RecognizerResult]:
        """Filtre les résultats en supprimant les termes de la allow-list"""
        if not allow_list_terms:
            return results
        
        filtered_results = []
        allow_list_lower = [term.lower().strip() for term in allow_list_terms]
        
        for result in results:
            entity_text = text[result.start:result.end].lower().strip()
            
            # Garder l'entité si elle n'est pas dans la allow-list
            if entity_text not in allow_list_lower:
                filtered_results.append(result)
            else:
                logger.debug(f"🚫 Entité filtrée (allow-list): '{entity_text}'")
        
        logger.info(f"🔍 Filtrage allow-list: {len(results)} -> {len(filtered_results)} entités")
        return filtered_results