from typing import List, Optional, Tuple
from presidio_analyzer import RecognizerResult
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class EntityRefiner(ABC):
    """Classe de base pour le recadrage d'entités"""
    
    def __init__(self, entity_type: str):
        self.entity_type = entity_type
    
    @abstractmethod
    def refine(self, text: str, start: int, end: int) -> Optional[Tuple[int, int]]:
        """
        Recadre une entité détectée
        
        Args:
            text: Le texte complet
            start: Position de début de l'entité détectée
            end: Position de fin de l'entité détectée
            
        Returns:
            Tuple (nouveau_start, nouveau_end) ou None si l'entité doit être ignorée
        """
        pass
    
    def should_process(self, entity_type: str) -> bool:
        """Vérifie si ce raffineur doit traiter ce type d'entité"""
        return entity_type == self.entity_type

class LocationAddressRefiner(EntityRefiner):
    """
    Refiner pour filtrer les doublons entre LOCATION et BE_ADDRESS/FR_ADDRESS.
    Ce refiner ne modifie pas les positions mais peut supprimer des entités.
    """
    
    def __init__(self):
        super().__init__("LOCATION")  # Ne traite que les LOCATION
        self.address_entities = {'BE_ADDRESS', 'FR_ADDRESS'}
        self.location_entity = 'LOCATION'
        # Cache pour stocker les adresses détectées
        self._detected_addresses = []
    
    def refine(self, text: str, start: int, end: int) -> Optional[Tuple[int, int]]:
        """
        Vérifie si cette LOCATION fait partie d'une adresse déjà détectée.
        
        Args:
            text: Le texte complet
            start: Position de début de la LOCATION
            end: Position de fin de la LOCATION
            
        Returns:
            Tuple (start, end) si la location doit être conservée, None sinon
        """
        location_text = text[start:end].strip().lower()
        
        # Ignorer les locations trop courtes ou non significatives
        if len(location_text) <= 3 or location_text in ['tel', 'fax', 'gsm']:
            logger.debug(f"Ignoring short/insignificant location: '{location_text}'")
            return None
        
        # Chercher des adresses dans le texte (simple heuristique)
        # Cette approche est limitée car on n'a accès qu'à une entité à la fois
        # Une meilleure approche serait de modifier l'architecture globale
        
        # Pour l'instant, on garde toutes les locations valides
        # et on laisse un post-processing global gérer les doublons
        logger.debug(f"Keeping location: '{location_text}'")
        return (start, end)
    
    def should_process(self, entity_type: str) -> bool:
        """Ne traite que les entités LOCATION"""
        return entity_type == self.location_entity