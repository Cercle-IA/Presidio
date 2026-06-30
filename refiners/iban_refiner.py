from abc import ABC, abstractmethod
from typing import Optional, Tuple
import re
import logging

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

class IBANRefiner(EntityRefiner):
    """Raffineur pour les IBAN"""
    
    def __init__(self):
        super().__init__("IBAN")
        self.iban_regex = re.compile(r"\b[A-Z]{2}[0-9]{2}\s?(?:[A-Z0-9]{4}\s?){2,7}[A-Z0-9]{1,4}\b", re.IGNORECASE)
    
    def refine(self, text: str, start: int, end: int) -> Optional[Tuple[int, int]]:
        ent_text = text[start:end].strip()
        match = self.iban_regex.search(ent_text)
        
        if not match:
            logger.warning(f"Invalid IBAN detected, skipping: '{ent_text}'")
            return None
            
        true_iban = match.group(0)
        start_offset = ent_text.find(true_iban)
        
        if start_offset == -1:
            logger.warning(f"IBAN regex match but cannot find substring position: '{ent_text}'")
            return None
            
        new_start = start + start_offset
        new_end = new_start + len(true_iban)
        
        logger.debug(f"Adjusted IBAN span: {start}-{end} => {new_start}-{new_end}")
        return (new_start, new_end)