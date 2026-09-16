# Especificacion funcional — FotoTriage 0.1.0

## Objetivo

Clasificar colecciones locales de imagenes mediante reglas explicables y modelos opcionales, priorizando recall de fotografias importantes y cero eliminaciones automaticas.

## Requisitos funcionales

1. Recorrer directorios de forma recursiva.
2. Validar archivos y registrar corrupcion sin detener la corrida.
3. Extraer resolucion, formato, EXIF, brillo, nitidez y entropia.
4. Calcular SHA-256 y hash perceptual.
5. Identificar duplicados exactos y similares.
6. Detectar objetos con un backend opcional.
7. Calcular un score reproducible y explicable.
8. Persistir ejecuciones en SQLite.
9. Exportar CSV, JSON y galeria HTML offline.
10. Copiar o mover archivos solo bajo una accion explicita.

## Requisitos no funcionales

- Linux como plataforma principal.
- Procesamiento CPU por defecto.
- Sin llamadas a servicios remotos.
- Ejecuciones auditables.
- Configuracion externa mediante YAML.
- Fallo aislado por imagen.
- Rutas absolutas en la base y relativas en exportaciones.

## Criterio de aceptacion del MVP

- Procesa JPG, PNG y WEBP recursivamente.
- Una imagen corrupta no interrumpe la corrida.
- Un duplicado exacto es identificado.
- Una imagen negra recibe penalizacion fuerte.
- La presencia detectada de una persona incrementa el score.
- Se generan los tres reportes.
- `export` no escribe sin `--apply`.

## Proxima fase

- CLIP/ONNX para similitud semantica.
- OCR selectivo para memes, documentos y capturas.
- Etiquetas del usuario y calibracion supervisada.
- Procesamiento incremental reutilizando resultados por hash.
- Panel web Flask para revisar lotes.

