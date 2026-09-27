# BSICLE

## Corpus de test

> Script : summarize_csv.py

Manuscrits numérisés de Gallica :
- date de publication : 5e-15e siècles (inclus)
- [3 630 documents](data/dataset_century_5_15.csv)
- Langue (Top 5) :
  
| Langue | Documents | 
|:--------: |--------:|
| lat | 1575|
| fr | 630 |
| chi | 333 |
| grc | 328 |
| ara | 234 |

- Siècles :

| Siècle | Documents | % |
|:--------: |--------:| --------:|
|   5   |  5  |  0.1   |
|    6  |   25 | 0.7    |
|     7 |  37  |   1.0  |
|    8  |  190  |   5.2  |
|    9  |   259 |    7.1 |
|    10  |   206 |   5.7  |
|    11  |  173  |   4.8  |
|    12  |   316 |   8.7  |
|    13  |  487  |   13.4  |
|    14  |  842  |   23.2  |
|    15  |  1091  |    30.0 |


## Extraction du sous-corpus

> Script : download_gallica_images.py

- [194 documents](data/dataset_194.txt) parmi les 3630, 42 481 images
- filtrage des manuscrits chinois
- images IIIF downloadés à 256 pixels de largeur

## Traitement

> Script : infer.py

- inférence avec le modèle `mobilenetv3_large`
- seuil à 0.75
- images copiées dans 2 dossiers après inférence : `illustrations/non_illustrations`
  
| Images | illustrations | non_illustrations | ratio ill. % |
|:--------: |:--------:| :--------:| :--------:|
| 42 112     | 1037   | 41075    | 2,5%

## Analyse

Analyse visuelle des images et détection des faux positifs et faux négatifs.

### Illustrations

Les faux positifs (228, 18%) appartiennent principalement aux catégories suivantes :

| Type | Nombre |
|:-------- |--------:| 
|éléments de reliure|	38|
|mire	|10|
|transparence	|24|
|scan	|14|
|dégradation|	44|
|recueils|	47|
|divers |	51|


- Reliure : couverture, tranche, contre-plats, papier orné...

- Mire : mire, microfilm, contrôle couleurs...

- Transparence : les zones illustrées du verso sont visibles sur l'image

- Scan : une partie du scan couvre une zone illustrée sur la page précédente ou suivante

- Dégradation : tâches, perte de matériaux
  
- Recueil : éléments de manuscrits recomposés en recueil relié 

- Divers : page blanche, page de texte, lettrine non ornée, double page avec mise en page atypique...

Dans les faux positifs, on peut noter une présence massive de documents numérisés en niveaux de gris et/ou sur double page.
La double-page n'est plus lisible en largeur 256 pixels.

