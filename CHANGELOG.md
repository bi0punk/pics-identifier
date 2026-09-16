# Changelog

Todas las mejoras notables de FotoTriage se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es/1.0.0/) y el versionado es semantico ([SemVer](https://semver.org/lang/es/)).

## [No publicado]

### Añadido

- `.gitignore` para entornos virtuales, artefactos de Python, bases y reportes generados.
- `.editorconfig` para consistencia de estilo entre editores.
- Identidad de commits en GitHub como `bi0punk`.
- Pipeline CI en GitHub Actions (`pytest`, `ruff` y smoke test) para Python 3.10-3.12.
- Ruff como linter/format checker incluido en las dependencias de desarrollo.
- Cobertura de pruebas ampliada a 22 casos: base de datos, exportador, reportes, scanner y CLI end-to-end.
- El progreso de `scan` ahora se escribe en stderr, dejando stdout limpio para JSON.
- Analisis paralelo por defecto en `scan` (nuevo flag `--workers`), preservando el orden estable de resultados.
- Procesamiento incremental: las imagenes sin cambios (mismo mtime y tamano) se reutilizan de la ultima corrida compatible, evitando recalcular hashes.
- `export` ahora resuelve colisiones de nombres dentro del mismo plan (no solo contra archivos existentes).