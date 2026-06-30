Fichiers de test pour les recognizers CHIFFRE_AFFAIRES et MARKET_SHARE
=======================================================================

01_chiffre_affaires_basique.txt
  Cas d'usage courants en langage naturel.
  Tous les montants doivent être détectés et anonymisés en plage [min - max] EUR.

02_chiffre_affaires_formats.txt
  Variété de formats : entiers avec séparateurs, K/M/Md, décimaux, multi-devises, petits montants.
  Vérifie que le parser _parse_amount gère tous les formats correctement.

03_parts_de_marche_basique.txt
  Cas d'usage courants pour les pourcentages de part de marché.
  Tous les % doivent être anonymisés en plage [min-max]%.

04_parts_de_marche_patterns.txt
  Couvre chaque pattern du recognizer :
  - Score 0.95 : % + lookahead "de part de marché"
  - Score 0.85 : % + CA sectoriel / positions textuelles
  - Score 0.80 : parts relatives textuelles
  - Score 0.30 + boost contextuel : % simples avec mots-clés proches

05_texte_mixte_complet.txt
  Document réaliste mélangeant CHIFFRE_AFFAIRES et MARKET_SHARE.
  Bon test de coexistence des deux entités dans un même texte.

06_faux_positifs_a_ignorer.txt
  ATTENTION : ces éléments NE doivent PAS être détectés.
  Permet de valider que les recognizers ne sur-détectent pas.
  - Pourcentages sans contexte marché (TVA, satisfaction...)
  - Montants sans contexte CA (factures, salaires...)

07_cas_limites_edge_cases.txt
  Cas aux bornes et comportements spéciaux :
  - Vérification des arrondis de l'opérateur turnover_range
  - Clamping [0,100] de l'opérateur market_share_range
  - Décimales, formatage européen, séquences multiples
