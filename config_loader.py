import os
import yaml
import glob
import re
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class ConfigLoader:
    def __init__(self, config_dir: str = "conf"):
        self.config_dir = config_dir
        self.config = {}

    def load_config(self, main_config_file: str = "main.yaml") -> Dict[str, Any]:
        main_config_path = os.path.join(self.config_dir, main_config_file)

        if not os.path.exists(main_config_path):
            logger.warning(f"Fichier de configuration principal non trouvé: {main_config_path}")
            return self._load_legacy_config()

        with open(main_config_path, 'r', encoding='utf-8') as f:
            main_config = yaml.safe_load(f)

        if 'includes' in main_config:
            for include_pattern in main_config['includes']:
                self._load_includes(include_pattern)

        # Préprocesser les patterns du fichier principal aussi
        self._preprocess_regex_patterns(main_config)
        self._merge_config(main_config)

        logger.info(f"Configuration chargée avec {len(self.config.get('recognizer_registry', {}).get('recognizers', []))} recognizers")
        return self.config

    def _load_includes(self, pattern: str):
        pattern = os.path.expandvars(pattern)
        full_pattern = os.path.join(self.config_dir, pattern)
        matching_files = glob.glob(full_pattern, recursive=True)

        for file_path in sorted(matching_files):
            if os.path.isfile(file_path) and file_path.endswith('.yaml'):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        module_config = yaml.safe_load(f)
                        if module_config:
                            # Préprocesser les patterns regex pour gérer la ponctuation
                            self._preprocess_regex_patterns(module_config)
                            self._merge_config(module_config)
                            logger.debug(f"Module chargé: {file_path}")
                except Exception as e:
                    logger.error(f"Erreur lors du chargement de {file_path}: {e}")

    def _preprocess_regex_patterns(self, config: Dict[str, Any]):
        """Préprocesse les patterns regex pour gérer automatiquement la ponctuation"""
        if 'recognizer_registry' in config and 'recognizers' in config['recognizer_registry']:
            for recognizer in config['recognizer_registry']['recognizers']:
                if 'patterns' in recognizer:
                    for pattern in recognizer['patterns']:
                        if 'regex' in pattern:
                            original_regex = pattern['regex']
                            # Remplacer \b en fin de regex par un lookahead pour la ponctuation
                            # Seulement si le pattern se termine par \b
                            if original_regex.endswith('\\b'):
                                # Enlever le \b final et ajouter le lookahead
                                new_regex = original_regex[:-2] + '(?=\\s|[,.;:!?()]|$)'
                                pattern['regex'] = new_regex
                                logger.debug(f"Pattern modifié: {original_regex} -> {new_regex}")

    def _merge_config(self, new_config: Dict[str, Any]):
        for key, value in new_config.items():
            if key == 'recognizer_registry':
                if 'recognizer_registry' not in self.config:
                    self.config['recognizer_registry'] = {'recognizers': []}

                if 'recognizers' in value:
                    self.config['recognizer_registry']['recognizers'].extend(value['recognizers'])

                for reg_key, reg_value in value.items():
                    if reg_key != 'recognizers':
                        self.config['recognizer_registry'][reg_key] = reg_value

            elif key == 'allow_list':
                if 'allow_list' not in self.config:
                    self.config['allow_list'] = []
                if isinstance(value, list):
                    self.config['allow_list'].extend(value)

            elif key == 'nlp_configuration':
                logger.info(f"🔧 Fusion de nlp_configuration: {value}")
                if 'nlp_configuration' not in self.config:
                    self.config['nlp_configuration'] = {}
                self._merge_dict(self.config['nlp_configuration'], value)

            elif isinstance(value, dict) and key in self.config and isinstance(self.config[key], dict):
                self._merge_dict(self.config[key], value)
            else:
                self.config[key] = value

    def _merge_dict(self, target: Dict[str, Any], source: Dict[str, Any]):
        for key, value in source.items():
            if isinstance(value, dict) and key in target and isinstance(target[key], dict):
                self._merge_dict(target[key], value)
            else:
                target[key] = value

    def _load_legacy_config(self) -> Dict[str, Any]:
        legacy_path = os.path.join(self.config_dir, "default.yaml")
        if os.path.exists(legacy_path):
            logger.info("Utilisation de la configuration legacy: default.yaml")
            with open(legacy_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        else:
            raise FileNotFoundError(f"Aucun fichier de configuration trouvé dans {self.config_dir}")

    def get_recognizers(self) -> List[Dict[str, Any]]:
        return self.config.get('recognizer_registry', {}).get('recognizers', [])

    def get_supported_languages(self) -> List[str]:
        return self.config.get('supported_languages', ['fr'])

    def load_single_file(self, file_path: str) -> Dict[str, Any]:
        full_path = os.path.join(self.config_dir, file_path) if not os.path.isabs(file_path) else file_path
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Fichier de configuration non trouvé: {full_path}")

        with open(full_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
