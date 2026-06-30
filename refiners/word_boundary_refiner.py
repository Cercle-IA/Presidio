import re
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class WordBoundaryRefiner:
    """Refiner pour étendre les entités aux limites de mots complets"""
    
    def __init__(self):
        self.entity_type = "ALL"  # S'applique à tous les types d'entités
    
    def should_process(self, entity_type: str) -> bool:
        """Ce refiner s'applique à tous les types d'entités"""
        return True
    
    def refine(self, text: str, start: int, end: int) -> Optional[Tuple[int, int]]:
        """Étend l'entité pour inclure le mot complet"""
        try:
            # Trouver le début du mot
            new_start = start
            while new_start > 0 and text[new_start - 1].isalnum():
                new_start -= 1
            
            # Trouver la fin du mot
            new_end = end
            while new_end < len(text) and text[new_end].isalnum():
                new_end += 1
            
            # Retourner les nouvelles positions si elles ont changé
            if new_start != start or new_end != end:
                logger.debug(f"Extended entity boundaries from [{start}:{end}] to [{new_start}:{new_end}]")
                return (new_start, new_end)
            
            return None
            
        except Exception as e:
            logger.error(f"Error in WordBoundaryRefiner: {e}")
            return None