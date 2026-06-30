from abc import ABC, abstractmethod
from typing import Optional, Tuple
import re
import logging

# Imports des raffineurs modulaires
from refiners.iban_refiner import IBANRefiner
from refiners.ip_refiner import IPAddressRefiner
from refiners.date_refiner import DateRefiner
from refiners.location_address_refiner import LocationAddressRefiner
from refiners.word_boundary_refiner import WordBoundaryRefiner

logger = logging.getLogger(__name__)

class EntityRefiner(ABC):
    """Classe de base pour le recadrage d'entités"""
    
    def __init__(self, entity_type: str):
        self.entity_type = entity_type
    
    @abstractmethod
    def refine(self, text: str, start: int, end: int) -> Optional[Tuple[int, int]]:
        """Recadre une entité détectée"""
        pass
    
    def should_process(self, entity_type: str) -> bool:
        """Vérifie si ce raffineur doit traiter ce type d'entité"""
        return entity_type == self.entity_type

class EntityRefinerManager:
    """Gestionnaire des raffineurs d'entités"""
    
    def __init__(self):
        self.refiners = [
            WordBoundaryRefiner(),  # En premier pour étendre aux mots complets
            IBANRefiner(),
            IPAddressRefiner(),
            DateRefiner(),
            LocationAddressRefiner()
        ]
        logger.info(f"Initialized {len(self.refiners)} entity refiners")
    
    def register_refiner(self, refiner):
        """Enregistre un nouveau raffineur"""
        self.refiners.append(refiner)
    
    def refine_entity(self, text: str, entity_type: str, start: int, end: int) -> Optional[Tuple[int, int]]:
        """Applique tous les raffineurs applicables à une entité"""
        for refiner in self.refiners:
            if refiner.should_process(entity_type):
                result = refiner.refine(text, start, end)
                if result:
                    logger.debug(f"Entity refined by {refiner.__class__.__name__}: {start}-{end} -> {result[0]}-{result[1]}")
                    return result
        
        return (start, end)