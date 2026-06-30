from typing import List
from presidio_analyzer import RecognizerResult
import logging
import re

logger = logging.getLogger(__name__)

class OverlapResolver:
    """
    Résout les chevauchements entre entités de différents types
    Priorités: IBAN > EMAIL > PHONE > IP_ADDRESS > ADDRESS > LOCATION > ORGANIZATION > PERSON
    """
    
    def __init__(self):
        # Ordre de priorité (plus haut = plus prioritaire)
        self.priority_order = {
            'IBAN': 100,
            'CREDIT_CARD': 95,
            'EMAIL_ADDRESS': 90,
            'BE_ENTERPRISE_NUMBER': 88,  
            'PHONE_NUMBER': 85,
            'BE_PHONE_NUMBER': 85,
            'TELEPHONE': 84,
            'TELEPHONE_FRANCAIS': 86,
            'IP_ADDRESS': 82,
            'ADRESSE_FRANCAISE': 78,  # Priorité plus élevée pour adresses françaises spécifiques
            'BE_ADDRESS': 75,
            'FR_ADDRESS': 75,
            'ADRESSE': 70,  # Adresse générique avec priorité plus faible
            'ORGANISATION': 65,
            'LOCATION': 60,  # Priorité plus faible que les adresses
            'PERSON': 50,
            'PERSON_NAME': 45,
            'NRP': 40,
            'BE_PROFESSIONAL_ID': 40,
            'FR_CIVILITY_TITLE': 85,
            'FR_REGULATED_PROFESSION': 80,
            'CARTE_IDENTITE_FRANCAISE': 78,
            'PERMIS_CONDUIRE_FRANCAIS': 76,
            'PASSEPORT_FRANCAIS': 77,
            'URL': 35,
            'MARKET_SHARE': 35
        }
        
        # Patterns pour identifier les organisations
        self.organization_patterns = [
            r'\\b\\w+Consult\\b',
            r'\\bSPRL\\s+\\w+\\b',  # Pattern pour SPRL + nom
            r'\\bSRL\\s+\\w+\\b',   # Pattern pour SRL + nom
            r'\\bSA\\s+\\w+\\b',    # Pattern pour SA + nom
            r'\\bASBL\\s+\\w+\\b',  # Pattern pour ASBL + nom
            r'\\bSCS\\s+\\w+\\b',   # Pattern pour SCS + nom
            r'\\bSNC\\s+\\w+\\b',   # Pattern pour SNC + nom
            r'\\bSPRL\\b',
            r'\\bSRL\\b',
            r'\\bSA\\b',
            r'\\bASBL\\b',
            r'\\bSCS\\b',
            r'\\bSNC\\b',
            r'\\bLtd\\b',
            r'\\bInc\\b',
            r'\\bCorp\\b',
            r'\\bGmbH\\b'
        ]
        
        logger.info(f"✅ OverlapResolver initialisé avec {len(self.priority_order)} types d'entités")
    
    def process(self, results: List[RecognizerResult], text: str = "") -> List[RecognizerResult]:
        """
        Résout les chevauchements en gardant l'entité la plus prioritaire
        """
        if not results:
            return results
        
        original_count = len(results)
        
        # Appliquer les corrections spécifiques avant résolution des chevauchements
        corrected_results = self._apply_specific_corrections(results, text)
        
        # Trier par position pour traitement séquentiel
        sorted_results = sorted(corrected_results, key=lambda x: (x.start, x.end))
        
        resolved_results = []
        i = 0
        
        while i < len(sorted_results):
            current = sorted_results[i]
            overlapping_group = [current]
            
            # Trouver tous les chevauchements avec l'entité courante
            j = i + 1
            while j < len(sorted_results):
                if self._is_overlapping(current, sorted_results[j]):
                    overlapping_group.append(sorted_results[j])
                    j += 1
                elif sorted_results[j].start >= current.end:
                    # Plus de chevauchement possible
                    break
                else:
                    j += 1
            
            # Résoudre le groupe de chevauchements
            if len(overlapping_group) > 1:
                winner = self._resolve_overlap_group(overlapping_group, text)
                resolved_results.append(winner)
                # Avancer l'index pour éviter de retraiter les entités du groupe
                i = j
            else:
                resolved_results.append(current)
                i += 1
        
        logger.info(f"🔧 OverlapResolver: {original_count} -> {len(resolved_results)} entités")
        return resolved_results
    
    def _apply_specific_corrections(self, results: List[RecognizerResult], text: str) -> List[RecognizerResult]:
        """
        Applique des corrections spécifiques avant la résolution des chevauchements
        """
        corrected_results = []
        
        for result in results:
            entity_text = text[result.start:result.end] if text else ""
            
            # Correction 1: PERSON -> ORGANIZATION pour les noms d'entreprise
            if result.entity_type == 'PERSON' and self._is_organization_name(entity_text):
                corrected_result = RecognizerResult(
                    entity_type='ORGANISATION',
                    start=result.start,
                    end=result.end,
                    score=result.score + 0.1  # Bonus de confiance
                )
                logger.debug(f"🔄 Correction PERSON -> ORGANISATION: '{entity_text}'")
                corrected_results.append(corrected_result)
            
            # Correction 2: Séparer IP des adresses physiques
            elif result.entity_type in ['BE_ADDRESS', 'FR_ADDRESS'] and self._contains_ip_address(entity_text):
                # Extraire l'IP et créer une entité séparée
                ip_matches = list(re.finditer(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', entity_text))
                if ip_matches:
                    for ip_match in ip_matches:
                        ip_start = result.start + ip_match.start()
                        ip_end = result.start + ip_match.end()
                        
                        # Créer l'entité IP
                        ip_result = RecognizerResult(
                            entity_type='IP_ADDRESS',
                            start=ip_start,
                            end=ip_end,
                            score=0.95
                        )
                        corrected_results.append(ip_result)
                        logger.debug(f"🔄 IP extraite de l'adresse: '{ip_match.group()}'")
                    
                    # Créer une nouvelle entité adresse SANS la partie IP
                    # Chercher la partie adresse physique (après l'IP)
                    address_pattern = r'\b(?:Avenue|Rue|Boulevard|Chaussée|Place|Quai|Impasse|Drève|Clos|Allée)\b.*?\b[1-9]\d{3}\s+[A-Za-zà-ÿ\'-]+'
                    address_match = re.search(address_pattern, entity_text, re.IGNORECASE)
                    
                    if address_match:
                        address_start = result.start + address_match.start()
                        address_end = result.start + address_match.end()
                        
                        # Vérifier qu'il n'y a pas de chevauchement avec l'IP
                        ip_overlaps = any(not (address_end <= ip_start or address_start >= ip_end) 
                                        for ip_match in ip_matches 
                                        for ip_start, ip_end in [(result.start + ip_match.start(), result.start + ip_match.end())])
                        
                        if not ip_overlaps:
                            address_result = RecognizerResult(
                                entity_type=result.entity_type,
                                start=address_start,
                                end=address_end,
                                score=result.score
                            )
                            corrected_results.append(address_result)
                            logger.debug(f"🔄 Adresse physique séparée: '{address_match.group()}'")
                else:
                    corrected_results.append(result)
            else:
                corrected_results.append(result)
        
        return corrected_results
    
    def _is_organization_name(self, text: str) -> bool:
        """
        Détermine si un texte ressemble à un nom d'organisation
        """
        for pattern in self.organization_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def _contains_ip_address(self, text: str) -> bool:
        """
        Vérifie si le texte contient une adresse IP
        """
        ip_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
        return bool(re.search(ip_pattern, text))
    
    def _is_overlapping(self, entity1: RecognizerResult, entity2: RecognizerResult) -> bool:
        """
        Vérifie si deux entités se chevauchent
        """
        return not (entity1.end <= entity2.start or entity1.start >= entity2.end)
    
    def _resolve_overlap_group(self, overlapping_entities: List[RecognizerResult], text: str = "") -> RecognizerResult:
        """
        Résout un groupe d'entités qui se chevauchent
        Critères: 1) Priorité du type, 2) Score de confiance, 3) Longueur
        """
        def get_priority_score(entity):
            base_priority = self.priority_order.get(entity.entity_type, 0)
            confidence_bonus = entity.score * 10  # Score 0.9 = +9 points
            
            # Calculer la longueur depuis les positions
            entity_length = entity.end - entity.start
            length_bonus = entity_length * 0.1  # Bonus longueur
            
            # Bonus spécial pour IBAN vs FR_DRIVER_LICENSE
            if entity.entity_type == 'IBAN':
                # Vérifier si c'est un vrai IBAN (commence par code pays)
                if text:
                    entity_text = text[entity.start:entity.end].replace(' ', '')
                    if re.match(r'^[A-Z]{2}[0-9]{2}', entity_text):
                        base_priority += 20  # Bonus pour vrai IBAN
            
            return base_priority + confidence_bonus + length_bonus
        
        # Trier par score de priorité décroissant
        sorted_entities = sorted(overlapping_entities, 
                               key=get_priority_score, 
                               reverse=True)
        
        winner = sorted_entities[0]
        
        # Log des entités écartées (si texte disponible)
        if text:
            for loser in sorted_entities[1:]:
                loser_text = text[loser.start:loser.end]
                logger.debug(f"❌ Écarté: {loser.entity_type} '{loser_text}' (score: {get_priority_score(loser):.1f})")
            
            winner_text = text[winner.start:winner.end]
            logger.debug(f"✅ Gagnant: {winner.entity_type} '{winner_text}' (score: {get_priority_score(winner):.1f})")
        
        return winner
    
    def add_entity_priority(self, entity_type: str, priority: int):
        """
        Ajoute ou modifie la priorité d'un type d'entité
        """
        self.priority_order[entity_type] = priority
        logger.info(f"📊 Priorité mise à jour: {entity_type} = {priority}")