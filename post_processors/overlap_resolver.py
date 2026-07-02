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
        # IMPORTANT : ces clés doivent correspondre exactement aux `supported_entity`
        # définis dans conf/recognizers/**/*.yaml, pas à des noms génériques Presidio.
        # Une clé qui ne matche aucune entité réelle retombe sur la priorité par
        # défaut (0) dans get_priority_score(), ce qui la fait perdre systématiquement
        # face à n'importe quelle autre entité chevauchante.
        self.priority_order = {
            'IBAN': 100,
            'CREDIT_CARD': 95,
            'ADRESSE_EMAIL': 90,
            'NUMERO_ENTREPRISE_BELGE': 88,
            'TVA_BELGE': 88,
            'TVA_FRANCAISE': 88,
            'NUMERO_FISCAL_FRANCAIS': 88,
            'SIRET_SIREN_FRANCAIS': 88,
            'TELEPHONE': 84,
            'TELEPHONE_BELGE': 85,
            'TELEPHONE_FRANCAIS': 86,
            'ADRESSE_IP': 82,
            'DATE': 80,
            'DATE_TIME': 80,
            'TITRE_CIVILITE': 85,
            'DONNEES_PROFESSIONNELLES': 80,
            'ID_PROFESSIONNEL_BELGE': 72,
            'ADRESSE_FRANCAISE': 78,  # Priorité plus élevée pour adresses françaises spécifiques
            'ADRESSE_BELGE': 75,
            'ADRESSE': 70,  # Adresse générique avec priorité plus faible
            'ORGANISATION': 65,
            'SOCIETE_BELGE': 65,
            'SOCIETE_FRANCAISE': 65,
            'LOCATION': 60,  # Priorité plus faible que les adresses
            'PERSONNE': 50,
            'NRP': 40,
            'CARTE_IDENTITE_FRANCAISE': 78,
            'CARTE_IDENTITE_BELGE': 78,
            'PERMIS_CONDUIRE_FRANCAIS': 76,
            'PASSEPORT_FRANCAIS': 77,
            'PASSEPORT_BELGE': 77,
            'REGISTRE_NATIONAL_BELGE': 77,
            'NUMERO_SECURITE_SOCIALE_FRANCAIS': 77,
            'COMPTE_BANCAIRE_FRANCAIS': 77,
            'URL_IDENTIFIANT': 35,
            'MARKET_SHARE': 35,
            'MONTANT_FINANCIER': 45,
            'CHIFFRE_AFFAIRES': 45,
            'REFERENCE_CONTRAT': 40,
            'CLE_API_SECRETE': 90,
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
            # Borne de fin du groupe, étendue au fur et à mesure qu'on y ajoute
            # des entités. Comparer uniquement à `current` casse la transitivité :
            # une chaîne A-B, B-C (mais pas A-C) ne serait jamais fusionnée en un
            # seul groupe, laissant plusieurs "gagnants" qui se chevauchent
            # réellement survivre côte à côte.
            group_end = current.end

            j = i + 1
            while j < len(sorted_results) and sorted_results[j].start < group_end:
                overlapping_group.append(sorted_results[j])
                group_end = max(group_end, sorted_results[j].end)
                j += 1

            # Résoudre le groupe de chevauchements
            if len(overlapping_group) > 1:
                winners = self._resolve_overlap_group(overlapping_group, text)
                resolved_results.extend(winners)
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
    
    def _resolve_overlap_group(self, overlapping_entities: List[RecognizerResult], text: str = "") -> List[RecognizerResult]:
        """
        Résout un groupe d'entités qui se chevauchent en découpant les intervalles
        par ordre de priorité décroissant, plutôt qu'en gardant un seul "gagnant".

        Sans ce découpage, une entité courte mais prioritaire (ex: TITRE_CIVILITE
        sur "Monsieur") qui l'emporte sur une entité plus large qui la contient
        (ex: PERSONNE sur "Monsieur Karel Derycke") ferait disparaître toute
        l'entité perdante — y compris la partie qui ne chevauche pas ("Karel
        Derycke" resterait en clair, non anonymisé). Ici, chaque entité ne cède
        que la portion de son intervalle déjà couverte par une entité plus
        prioritaire ; le reste est conservé comme entité indépendante.

        Critères de priorité : 1) priorité du type, 2) score de confiance, 3) longueur.
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

        covered: List[tuple] = []
        kept: List[RecognizerResult] = []

        for entity in sorted_entities:
            remaining = self._subtract_intervals(entity.start, entity.end, covered)

            if not remaining:
                if text:
                    logger.debug(
                        f"❌ Écarté (entièrement couvert): {entity.entity_type} "
                        f"'{text[entity.start:entity.end]}' (score: {get_priority_score(entity):.1f})"
                    )
                continue

            for start, end in remaining:
                trimmed_start, trimmed_end = self._trim_whitespace(start, end, text)
                if trimmed_end - trimmed_start < 1:
                    continue
                kept.append(RecognizerResult(entity.entity_type, trimmed_start, trimmed_end, entity.score))
                if text and (trimmed_start, trimmed_end) != (entity.start, entity.end):
                    logger.debug(
                        f"✂️ Découpé: {entity.entity_type} conserve "
                        f"'{text[trimmed_start:trimmed_end]}' (partie non couverte)"
                    )

            covered = self._merge_intervals(covered + [(entity.start, entity.end)])

        return kept

    def _subtract_intervals(self, start: int, end: int, covered: List[tuple]) -> List[tuple]:
        """Retourne les sous-intervalles de [start, end) non présents dans `covered`."""
        result = []
        cursor = start
        for cov_start, cov_end in covered:
            if cov_end <= cursor or cov_start >= end:
                continue
            if cov_start > cursor:
                result.append((cursor, min(cov_start, end)))
            cursor = max(cursor, cov_end)
            if cursor >= end:
                break
        if cursor < end:
            result.append((cursor, end))
        return result

    def _merge_intervals(self, intervals: List[tuple]) -> List[tuple]:
        """Fusionne une liste d'intervalles [start, end) en intervalles disjoints triés."""
        if not intervals:
            return []
        sorted_intervals = sorted(intervals)
        merged = [sorted_intervals[0]]
        for start, end in sorted_intervals[1:]:
            last_start, last_end = merged[-1]
            if start <= last_end:
                merged[-1] = (last_start, max(last_end, end))
            else:
                merged.append((start, end))
        return merged

    def _trim_whitespace(self, start: int, end: int, text: str) -> tuple:
        """Réduit [start, end) pour exclure les espaces en début/fin (évite de
        remplacer un simple espace entre deux entités par un libellé)."""
        if not text:
            return start, end
        end = min(end, len(text))
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        return start, end

    def add_entity_priority(self, entity_type: str, priority: int):
        """
        Ajoute ou modifie la priorité d'un type d'entité
        """
        self.priority_order[entity_type] = priority
        logger.info(f"📊 Priorité mise à jour: {entity_type} = {priority}")