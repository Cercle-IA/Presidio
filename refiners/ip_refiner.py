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

class IPAddressRefiner(EntityRefiner):
    """Raffineur pour les adresses IP"""
    
    def __init__(self):
        super().__init__("IP_ADDRESS")
        self.ipv4_regex = re.compile(
            r"\b(?:(?:25[0-5]|2[0-4][0-9]|1\d{2}|[1-9]?\d)\.){3}"
            r"(?:25[0-5]|2[0-4][0-9]|1\d{2}|[1-9]?\d)\b"
        )
    
    def refine(self, text: str, start: int, end: int) -> Optional[Tuple[int, int]]:
        ent_text = text[start:end].strip()
        match = self.ipv4_regex.search(ent_text)
        
        if not match:
            logger.warning(f"Invalid IP detected, skipping: '{ent_text}'")
            return None
            
        true_ip = match.group(0)
        start_offset = ent_text.find(true_ip)
        
        if start_offset == -1:
            logger.warning(f"IP regex match but cannot find substring position: '{ent_text}'")
            return None
            
        new_start = start + start_offset
        new_end = new_start + len(true_ip)
        
        logger.debug(f"Adjusted IP span: {start}-{end} => {new_start}-{new_end}")
        return (new_start, new_end)