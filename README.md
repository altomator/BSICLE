# BSICLE

## Corpus de test

> Script : summarize_csv.py

Manuscrits numérisés de Gallica :
- date de publication : 5e-15e siècles (inclus)
- 3 630 documents
- Langue (Top 5) : 'lat': 1,575, 'fre': 630, 'chi': 333, 'grc': 328, 'ara': 234
- Siècles :
• 5 : 5 (0.1%)
• 6 : 25 (0.7%)
• 7 : 37 (1.0%)
• 8 : 190 (5.2%)
• 9 : 259 (7.1%)
• 10 : 206 (5.7%)
• 11 : 173 (4.8%)
• 12 : 316 (8.7%)
• 13 : 487 (13.4%)
• 14 : 842 (23.2%)
• 15 : 1,091 (30.0%)

## Extraction du sous-corpus

> Script : download_gallica_images.py

- 194 documents parmi les 3630, 42 481 images
- filtrage des manuscrits chinois
- images IIIF downloadés à 256 pixels de largeur

## Traitement

> Script : infer.py

- inférence avec le modèle `mobilenetv3_large`
- seuil à 0.75
- images copiées dans 2 dossiers après inférence `illustrations/non_illustrations`

## Analyse

