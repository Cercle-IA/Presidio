from typing import List
from presidio_analyzer import RecognizerResult
import logging

logger = logging.getLogger(__name__)

class DeduplicationProcessor:
    def __init__(self):
        self.rules = [
            LocationAddressRule()
        ]
        logger.info("🔧 DeduplicationProcessor initialisé avec les règles de déduplication")
    
    def process(self, results: List[RecognizerResult], text: str) -> List[RecognizerResult]:
        """Applique les règles de déduplication aux résultats"""
        processed_results = results.copy()
        
        for rule in self.rules:
            processed_results = rule.apply(processed_results, text)
            
        logger.info(f"🔧 DeduplicationProcessor: {len(results)} -> {len(processed_results)} entités")
        return processed_results

class LocationAddressRule:
    """Règle pour éviter les doublons entre LOCATION et ADDRESS"""
    
    def __init__(self):
        self.insignificant_terms = {'le', 'la', 'les', 'de', 'du', 'des', 'à', 'au', 'aux'}
    
    ADDRESS_TYPES = {'ADRESSE', 'ADRESSE_BELGE', 'ADRESSE_FRANCAISE'}

    def apply(self, results: List[RecognizerResult], text: str) -> List[RecognizerResult]:
        """Supprime les LOCATION qui sont des doublons d'une adresse"""
        locations = [r for r in results if r.entity_type == 'LOCATION']
        addresses = [r for r in results if r.entity_type in self.ADDRESS_TYPES]
        others = [r for r in results if r.entity_type != 'LOCATION' and r.entity_type not in self.ADDRESS_TYPES]
        
        filtered_locations = []
        for location in locations:
            if self._should_keep_location(location, addresses, text):
                filtered_locations.append(location)
            else:
                location_text = text[location.start:location.end]
                logger.debug(f"🗑️ Suppression LOCATION dupliquée: '{location_text}'")
        
        return addresses + filtered_locations + others
    
    def _should_keep_location(self, location: RecognizerResult, addresses: List[RecognizerResult], text: str) -> bool:
        location_text = text[location.start:location.end].strip().lower()
        
        # Ignorer termes non significatifs
        if (len(location_text) <= 3 or 
            location_text in self.insignificant_terms):
            return False
        
        # Vérifier chevauchement avec adresses
        for address in addresses:
            if self._is_overlapping_or_contained(location, address, text):
                return False
        
        return True
    
    def _is_overlapping_or_contained(self, loc: RecognizerResult, addr: RecognizerResult, text: str) -> bool:
        """Vérifie si une location est contenue dans une address"""
        loc_text = text[loc.start:loc.end].strip().lower()
        addr_text = text[addr.start:addr.end].strip().lower()
        
        return loc_text in addr_text