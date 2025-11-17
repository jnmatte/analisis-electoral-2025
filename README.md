# Análisis electoral 2025

Este repositorio contiene los insumos oficiales de la elección senatorial 2025 y un pequeño
script en Python para simular escenarios alternativos con el método proporcional d'Hondt.

## Requisitos

1. Python 3.11 o superior.
2. Dependencias listadas en `pyproject.toml`. Para instalarlas se puede usar `pip`:

```bash
pip install -e .
```

## Uso

El comando expone un CLI llamado `simular-pactos` que lee todos los archivos Excel ubicados en
`Inputs/Senadores` y permite unir dos pactos/listas dentro de cada circunscripción para medir
el impacto sobre la asignación de escaños.

```bash
python -m analisis_electoral.simulation --pact-a C --pact-b J --circ 1
```

Parámetros importantes:

- `--inputs`: carpeta donde están los archivos Excel (por defecto `Inputs/Senadores`).
- `--circ`: IDs de circunscripción a revisar (si no se especifica se utilizan todas).
- `--pact-a` y `--pact-b`: códigos de los pactos a unir (por ejemplo `C`, `J`, etc.).

La salida incluye:

1. El listado de pactos encontrados en la circunscripción y su votación.
2. La asignación de escaños calculada con los pactos originales.
3. El escenario alternativo con ambos pactos unidos.
4. El detalle de candidaturas electas en cada caso, ordenadas por votos.

Esto permite evaluar rápidamente si la alianza habría aumentado (o reducido) el número total de
escaños y qué candidaturas se habrían beneficiado.
