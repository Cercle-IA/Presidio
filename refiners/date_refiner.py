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

class DateRefiner(EntityRefiner):
    """Raffineur pour les dates - élimine les faux positifs"""
    
    def __init__(self):
        super().__init__("DATE")
        # Patterns pour valider les vraies dates
        self.valid_date_patterns = [
            # Format DD/MM/YYYY
            re.compile(r"\b(?:0[1-9]|[12][0-9]|3[01])/(?:0[1-9]|1[0-2])/(?:19|20)\d{2}\b"),
            # Format DD-MM-YYYY
            re.compile(r"\b(?:0[1-9]|[12][0-9]|3[01])-(?:0[1-9]|1[0-2])-(?:19|20)\d{2}\b"),
            # Format ISO YYYY-MM-DD
            re.compile(r"\b(?:19|20)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])\b"),
            # Dates avec mois en lettres
            re.compile(r"\b(?:0?[1-9]|[12][0-9]|3[01])\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+(?:19|20)\d{2}\b", re.IGNORECASE),
            # Heures
            re.compile(r"\b(?:[01][0-9]|2[0-3]):[0-5][0-9](?::[0-5][0-9])?\b")
        ]
        
        # Patterns à rejeter (faux positifs courants)
        self.reject_patterns = [
            # Codes IBAN belges (BE + chiffres)
            re.compile(r"\bBE\d{2,}\b", re.IGNORECASE),
            # Numéros d'entreprise belges
            re.compile(r"\bBE\d{3}\.\d{3}\.\d{3}\b"),
            # Mots comme HTVA, TVA, etc.
            re.compile(r"\b(?:HTVA|TVA|BCE|ONSS|SIREN|SIRET)\b", re.IGNORECASE),
            # Données sensibles (texte)
            re.compile(r"\b(?:données?\s+sensibles?)\b", re.IGNORECASE),
            # Codes postaux isolés
            re.compile(r"^\d{4}$"),
            # Codes courts (2-4 caractères alphanumériques)
            re.compile(r"^[A-Z]{2}\d{1,2}$")
        ]
    
    def refine(self, text: str, start: int, end: int) -> Optional[Tuple[int, int]]:
        """Valide si l'entité détectée est vraiment une date"""
        ent_text = text[start:end].strip()
        
        # Vérifier si c'est un pattern à rejeter
        for reject_pattern in self.reject_patterns:
            if reject_pattern.search(ent_text):
                logger.info(f"Date rejetée (faux positif): '{ent_text}'")
                return None
        
        # Vérifier si c'est un pattern de date valide
        for valid_pattern in self.valid_date_patterns:
            if valid_pattern.search(ent_text):
                logger.info(f"Date validée: '{ent_text}'")
                return (start, end)
        
        # Si aucun pattern valide trouvé, rejeter
        logger.info(f"Date rejetée (format invalide): '{ent_text}'")
        return None
    
    def validate_date_logic(self, day: int, month: int, year: int) -> bool:
        """Valide la logique de la date (jours/mois corrects)"""
        if month < 1 or month > 12:
            return False
        
        days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        
        # Année bissextile
        if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
            days_in_month[1] = 29
        
        return 1 <= day <= days_in_month[month - 1]