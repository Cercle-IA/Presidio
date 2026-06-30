import os
import logging
import re
import tempfile
import yaml
from flask import Flask, request, jsonify, make_response
from presidio_analyzer import AnalyzerEngineProvider
from config_loader import ConfigLoader
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from entity_refiners import EntityRefinerManager
from pipeline_manager import AnalysisPipeline
from operators.market_share_operator import MarketShareRangeOperator
from operators.turnover_operator import TurnoverRangeOperator

# Initialisation logger
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

refiner_manager = EntityRefinerManager()
analyzer = None
allow_list_terms = set()

try:
    logger.info("--- Presidio Analyzer Service Starting (Architecture Modulaire) ---")
    config_loader = ConfigLoader()
    config = config_loader.load_config("main.yaml")
    logger.info("✅ Configuration modulaire chargée avec succès")

    allow_list_terms = set(term.lower().strip() for term in config.get('allow_list', []))
    logger.info(f"✅ Allow list chargée avec {len(allow_list_terms)} termes")

    recognizers_count = len(config.get('recognizer_registry', {}).get('recognizers', []))
    logger.info(f"📊 Nombre de recognizers chargés: {recognizers_count}")

    presidio_config = config_loader.get_presidio_config()
    if 'nlp_configuration' not in presidio_config:
        logger.warning("❌ nlp_configuration MANQUANTE dans la config Presidio")

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as tmp_file:
        yaml.dump(presidio_config, tmp_file, default_flow_style=False, allow_unicode=True)
        temp_config_path = tmp_file.name

    provider = AnalyzerEngineProvider(analyzer_engine_conf_file=temp_config_path)
    analyzer = provider.create_engine()
    os.unlink(temp_config_path)

    logger.info(f"Analyzer ready. Languages: {analyzer.supported_languages}")

except Exception as e:
    logger.exception("Error during AnalyzerEngine initialization.")
    analyzer = None


def normalize_label(text: str) -> str:
    # Règles générales de normalisation pour gérer tous les cas
    text = text.strip().lower()
    
    # 1. Supprimer parenthèses et leur contenu
    text = re.sub(r'\([^)]*\)', '', text)
    
    # 2. Supprimer virgules et points suivis d'un espace
    text = re.sub(r'[,.] ', ' ', text)
    
    # 3. Supprimer points collés (ex: "Dr.Marie" -> "Dr Marie")
    text = re.sub(r'\.(\w)', r' \1', text)
    
    # 4. Supprimer tirets collés aux espaces SEULEMENT (garder les tirets dans les mots composés)
    text = re.sub(r'- ', ' ', text)  # "expert- comptable" -> "expert comptable"
    text = re.sub(r' -', ' ', text)  # "expert -comptable" -> "expert comptable"
    
    # 5. Supprimer deux-points et ce qui suit (ex: "n° IEC: 567890" -> "n° IEC")
    text = re.sub(r':.*$', '', text)
    
    # 6. Normaliser les espaces multiples
    text = re.sub(r'\s+', ' ', text)
    
    # 7. Normalisation finale : garder lettres, chiffres, espaces ET tirets pour mots composés
    cleaned = re.sub(r'[^\w\s-]', '', text)
    
    # 8. Nettoyer les espaces en début/fin
    return cleaned.strip()


def filter_by_category(results, mode):
    """Filtre les résultats selon la catégorie sélectionnée"""
    if mode == "pii_business":
        return results  # Tout
    
    # Définir les entités PII (Données personnelles)
    pii_entities = {
        # Données personnelles de base
        'PERSONNE', 'PERSON', 'DATE', 'DATE_TIME',
        'EMAIL_ADDRESS', 'ADRESSE_EMAIL', 'PHONE_NUMBER', 'TELEPHONE',
        'CREDIT_CARD', 'IBAN', 'ADRESSE_IP',
        
        # Adresses personnelles
        'ADRESSE', 'ADRESSE_FRANCAISE', 'ADRESSE_BELGE', 'LOCATION',
        
        # Téléphones personnels
        'TELEPHONE_FRANCAIS', 'TELEPHONE_BELGE',
        
        # Documents d'identité personnels
        'NUMERO_SECURITE_SOCIALE_FRANCAIS', 'REGISTRE_NATIONAL_BELGE',
        'CARTE_IDENTITE_FRANCAISE', 'CARTE_IDENTITE_BELGE',
        'PASSEPORT_FRANCAIS', 'PASSEPORT_BELGE',
        'PERMIS_CONDUIRE_FRANCAIS',
        
        # Données financières personnelles
        'COMPTE_BANCAIRE_FRANCAIS',
        
        # Données sensibles RGPD
        'HEALTH_DATA', 'DONNEES_SANTE',
        'SEXUAL_ORIENTATION', 'ORIENTATION_SEXUELLE',
        'POLITICAL_OPINIONS', 'OPINIONS_POLITIQUES',
        'BIOMETRIC_DATA', 'DONNEES_BIOMETRIQUES',
        'RGPD_FINANCIAL_DATA', 'DONNEES_FINANCIERES_RGPD',
        
        # Identifiants personnels
        'IDENTIFIANT_PERSONNEL'
    }
    
    # Définir les entités Business (Données d'entreprise)
    business_entities = {
        # Organisations et sociétés
        'ORGANISATION', 'ORGANIZATION',
        'SOCIETE_FRANCAISE', 'SOCIETE_BELGE',
        
        # Identifiants fiscaux et d'entreprise
        'TVA_FRANCAISE', 'TVA_BELGE',
        'NUMERO_FISCAL_FRANCAIS', 'SIRET_SIREN_FRANCAIS',
        'NUMERO_ENTREPRISE_BELGE',
        
        # Identifiants professionnels
        'ID_PROFESSIONNEL_BELGE',
        
        # Données commerciales
        'MARKET_SHARE', 'SECRET_COMMERCIAL',
        'REFERENCE_CONTRAT', 'MONTANT_FINANCIER',
        'CHIFFRE_AFFAIRES',
        
        # Données techniques d'entreprise
        'CLE_API_SECRETE'
    }
    
    # Définir les entités mixtes (PII + Business)
    mixed_entities = {
        # Données pouvant être personnelles ou professionnelles
        'TITRE_CIVILITE', 'DONNEES_PROFESSIONNELLES',
        'LOCALISATION_GPS', 'URL_IDENTIFIANT'
    }
    
    if mode == "pii":
        # Inclure PII + mixtes
        allowed_entities = pii_entities | mixed_entities
        return [r for r in results if r.entity_type in allowed_entities]
    
    elif mode == "business":
        # Inclure Business + mixtes
        allowed_entities = business_entities | mixed_entities
        return [r for r in results if r.entity_type in allowed_entities]
    
    # Par défaut, retourner tous les résultats
    return results


# Remplacer ligne 18
pipeline = AnalysisPipeline()

# Modifier la fonction analyze_text (lignes 73-105)
@app.route("/analyze", methods=["POST"])
def analyze_text():
    if not analyzer:
        return jsonify({"error": "Analyzer engine is not available. Check startup logs."}), 500

    try:
        data = request.get_json(force=True)
        text_to_analyze = data.get("text", "")
        language = data.get("language", "fr")
        mode = data.get("mode", "pii_business")  # Nouveau paramètre

        if not text_to_analyze:
            return jsonify({"error": "text field is missing or empty"}), 400

        # Analyse brute
        raw_results = analyzer.analyze(text=text_to_analyze, language=language)
        
        # Filtrer selon la catégorie
        filtered_results = filter_by_category(raw_results, mode)
        
        # Pipeline modulaire complet
        final_results = pipeline.process(text_to_analyze, filtered_results, allow_list_terms)
        
        response_data = [res.to_dict() for res in final_results]
        return make_response(jsonify(response_data), 200)

    except Exception as e:
        logger.exception("Error processing analysis")
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health_check():
    if analyzer:
        return jsonify({
            "status": "healthy",
            "languages": analyzer.supported_languages,
            "version": "2.0.0"
        }), 200
    else:
        return jsonify({"status": "unhealthy", "error": "Analyzer not initialized"}), 503


def load_replacements():
    """Charge les configurations d'anonymisation depuis YAML"""
    try:
        config_path = "conf/anonymization/replacements.yaml"
        if not os.path.exists(config_path):
            logger.warning(f"❌ Fichier de configuration non trouvé: {config_path}")
            return {}

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not config:
            logger.warning("❌ Fichier de configuration vide")
            return {}

        anonymizer_config = config.get("anonymizer_config", {})
        replacements = anonymizer_config.get("replacements", {})

        if not replacements:
            logger.warning("❌ Aucun remplacement trouvé dans la configuration")
            return {}

        operators = {}
        for entity_type, replacement_value in replacements.items():
            try:
                operators[entity_type] = OperatorConfig("replace", {"new_value": replacement_value})
            except Exception as e:
                logger.error(f"❌ Erreur lors création opérateur {entity_type}: {e}")
                continue

        logger.info(f"✅ Loaded {len(operators)} replacement operators from config")
        return operators

    except Exception as e:
        logger.error(f"❌ Failed to load replacements config: {e}")
        return {}


# Initialisation anonymizer et opérateurs
try:
    anonymizer = AnonymizerEngine()
    anonymizer.add_anonymizer(MarketShareRangeOperator)
    anonymizer.add_anonymizer(TurnoverRangeOperator)
    logger.info("✅ Anonymizer engine initialized successfully")
    replacement_operators = load_replacements()
    replacement_operators["MARKET_SHARE"] = OperatorConfig("market_share_range", {})
    replacement_operators["CHIFFRE_AFFAIRES"] = OperatorConfig("turnover_range", {})
    if replacement_operators:
        logger.info(f"✅ Loaded {len(replacement_operators)} custom replacement operators")
    else:
        logger.warning("⚠️ Aucun opérateur remplacement chargé, fallback par défaut")
        replacement_operators = {}

except Exception as e:
    logger.error(f"❌ Anonymizer initialization failed: {e}")
    anonymizer = None
    replacement_operators = {}


@app.route("/anonymize", methods=["POST"])
def anonymize_text():
    logger.error("🚨 ENDPOINT /anonymize APPELÉ")

    global anonymizer, replacement_operators

    if anonymizer is None:
        return jsonify({"error": "Anonymizer not initialized"}), 500

    if not replacement_operators:
        logger.warning("⚠️ replacement_operators non défini, rechargement...")
        replacement_operators = load_replacements()

    logger.info(f"🔍 Opérateurs disponibles: {list(replacement_operators.keys())}")

    try:
        data = request.get_json(force=True)
        text_to_anonymize = data.get("text", "")
        language = data.get("language", "fr")
        mode = data.get("mode", "pii")

        if not text_to_anonymize:
            return jsonify({"error": "No text provided"}), 400

        logger.info(f"🔍 Texte à anonymiser: '{text_to_anonymize}'")

        entities_to_detect = get_entities_by_mode(mode) if 'get_entities_by_mode' in globals() else None

        analyzer_results = analyzer.analyze(
            text=text_to_anonymize,
            language=language,
            entities=entities_to_detect
        )

        logger.info(f"🔍 Entités détectées: {[(r.entity_type, text_to_anonymize[r.start:r.end], r.score) for r in analyzer_results]}")

        filtered_results = []
        for res in analyzer_results:
            ent_text = text_to_anonymize[res.start:res.end].strip()
            ent_text_norm = normalize_label(ent_text)

            logger.info(f"🔍 Traitement entité: {res.entity_type} = '{ent_text}' (score: {res.score})")
            logger.info(f"🔍 Allow list terms: {allow_list_terms}")

            # Normalisation douce du texte de l'entité (cohérente avec l'allow_list)
            ent_text_normalized = ent_text.lower().strip()
            logger.info(f"🔍 Texte normalisé: '{ent_text_normalized}'")
            
            # Vérifier si l'entité est dans l'allow-list (correspondance exacte)
            is_allowed = ent_text_normalized in allow_list_terms
            
            if is_allowed:
                logger.info(f"✅ Entité '{ent_text}' ignorée (dans allow list)")
                continue

            refined_positions = refiner_manager.refine_entity(text_to_anonymize, res.entity_type, res.start, res.end)
            if refined_positions is None:
                logger.info(f"❌ Entité {res.entity_type} supprimée par le refiner")
                continue

            res.start, res.end = refined_positions
            filtered_results.append(res)
            logger.info(f"✅ Entité {res.entity_type} conservée après refinement")

        logger.info(f"🔍 Entités finales pour anonymisation: {[(r.entity_type, text_to_anonymize[r.start:r.end]) for r in filtered_results]}")

        operators_to_use = replacement_operators if replacement_operators else {}
        logger.info(f"🔍 Opérateurs utilisés: {list(operators_to_use.keys())}")

        anonymized_result = anonymizer.anonymize(
            text=text_to_anonymize,
            analyzer_results=filtered_results,
            operators=operators_to_use
        )

        logger.info(f"🔍 Résultat anonymisation: '{anonymized_result.text}'")

        replacement_map = {}
        for item in anonymized_result.items:
            original_text = text_to_anonymize[item.start:item.end]
            replacement_map[original_text] = item.text

        logger.info(f"🔍 Replacement map: {replacement_map}")

        return jsonify({
            "original_text": text_to_anonymize,
            "anonymized_text": anonymized_result.text,
            "entities_found": [
                {
                    "entity_type": result.entity_type,
                    "start": result.start,
                    "end": result.end,
                    "score": result.score
                } for result in filtered_results
            ],
            "replacement_map": replacement_map,
            "mode": mode
        })

    except Exception as e:
        logger.error(f"Error during anonymization: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
