from typing import List
from presidio_analyzer import RecognizerResult
import re

class CleanupProcessor:
    """Post-processor pour nettoyer les résultats d'anonymisation et éviter les chevauchements."""
    
    def __init__(self):
        self.name = "CleanupProcessor"
    
    def process(self, results: List[RecognizerResult]) -> List[RecognizerResult]:
        """Nettoie les résultats pour éviter les chevauchements et les détections incorrectes."""
        if not results:
            return results
        
        # Trier par position de début
        sorted_results = sorted(results, key=lambda x: x.start)
        
        # Supprimer les chevauchements en gardant le score le plus élevé
        cleaned_results = []
        
        for current in sorted_results:
            # Vérifier si ce résultat chevauche avec un résultat déjà accepté
            overlaps = False
            for accepted in cleaned_results:
                if self._overlaps(current, accepted):
                    # Si le score actuel est plus élevé, remplacer
                    if current.score > accepted.score:
                        cleaned_results.remove(accepted)
                        cleaned_results.append(current)
                    overlaps = True
                    break
            
            if not overlaps:
                cleaned_results.append(current)
        
        # Filtrer les résultats trop courts ou suspects
        final_results = []
        for result in cleaned_results:
            if self._is_valid_result(result):
                final_results.append(result)
        
        return final_results
    
    def _overlaps(self, result1: RecognizerResult, result2: RecognizerResult) -> bool:
        """Vérifie si deux résultats se chevauchent."""
        return not (result1.end <= result2.start or result2.end <= result1.start)
    
    def _is_valid_result(self, result: RecognizerResult) -> bool:
        """Vérifie si un résultat est valide (pas trop court, pas suspect)."""
        # Longueur minimale
        if result.end - result.start < 2:
            return False
        
        # Éviter les détections sur des caractères isolés
        if result.entity_type == "PERSON_NAME" and result.end - result.start < 4:
            return False
        
        return True