# FotoTriage CLI

FotoTriage analiza una ruta de imagenes y asigna un score explicable de 0 a 100. El objetivo es separar fotografias potencialmente importantes de capturas, imagenes defectuosas, duplicados y basura probable sin depender de servicios externos.

## Seguridad por defecto

- No modifica ni elimina originales durante `scan`.
- `export` simula la operacion salvo que se entregue `--apply`.
- La opcion recomendada es `--mode copy`.
- Las decisiones, componentes y motivos quedan registrados en SQLite y JSON.

## Instalacion en Linux

```bash
chmod +x install.sh
./install.sh
source .venv/bin/activate
```

Para agregar deteccion de personas, animales y objetos:

```bash
pip install -e '.[objects]'
```

El primer uso del perfil `balanced` puede descargar el modelo configurado. El modo `fast` no necesita YOLO.

## Uso rapido

```bash
# Analisis liviano, completamente local
fototriage scan ~/Fotos \
  --profile fast \
  --db ./fototriage.sqlite3 \
  --report ./reportes

# Analisis con deteccion de objetos en CPU
fototriage scan ~/Fotos \
  --profile balanced \
  --model yolo11n.pt \
  --db ./fototriage.sqlite3 \
  --report ./reportes

# Controlar la cantidad de hilos de analisis (por defecto usa todos los nucleos)
fototriage scan ~/Fotos --profile fast --db ./fototriage.sqlite3 --workers 4

# Abrir/crear galeria
fototriage gallery --db ./fototriage.sqlite3 --open

# Explicar una imagen
fototriage explain ~/Fotos/IMG_001.jpg --db ./fototriage.sqlite3

# Simular copia de importantes y dudosas
fototriage export \
  --db ./fototriage.sqlite3 \
  --output ./clasificadas \
  --decision important \
  --decision review \
  --mode copy

# Ejecutar la copia una vez revisado el plan
fototriage export \
  --db ./fototriage.sqlite3 \
  --output ./clasificadas \
  --decision important \
  --decision review \
  --mode copy \
  --apply
```

## Perfiles

| Perfil | Analisis tecnico | Duplicados | Objetos YOLO | Semantica/OCR |
|---|---:|---:|---:|---:|
| `fast` | Si | Si | No | No |
| `balanced` | Si | Si | Si, si esta instalado | No |
| `deep` | Si | Si | Si, si esta instalado | Preparado para fase 2 |

Si YOLO no esta instalado, `balanced` continua con el analisis basico y muestra una advertencia.

## Score

El score combina:

- Calidad: nitidez, exposicion y resolucion.
- Metadatos: EXIF, camara, fecha y GPS.
- Contenido: objetos detectados cuando YOLO esta activo.
- Originalidad: penalizacion de duplicados.
- Penalizaciones: captura probable, desenfoque, baja resolucion e imagen casi uniforme.

Todos los pesos estan en `config/scoring.yaml`. Conviene calibrarlos con una muestra de fotos reales antes de usar `trash_candidate` para tomar decisiones.

## Rendimiento

- `scan` analiza las imagenes en paralelo (ajustable con `--workers`) preservando el orden estable de resultados.
- Los re-scans sobre la misma ruta, perfil y configuracion reutilizan el analisis de las imagenes que no cambiaron (comparando mtime y tamano), por lo que solo se reprocesan archivos nuevos o modificados.

## Resultados

`--report` genera:

- `resultados.csv`: revision y filtrado en planilla.
- `resultados.json`: salida completa para integraciones.
- `galeria.html`: galeria offline con filtros.
- `fototriage.sqlite3`: historial de ejecuciones y explicaciones.

## Pruebas

```bash
pip install -e '.[dev]'
pytest -q
```

Tambien se puede ejecutar una prueba end-to-end sin pytest:

```bash
python3 scripts/smoke_test.py
```

## Limites del MVP

- El detector general reconoce clases comunes; no sabe por si solo que una foto es emocionalmente importante.
- La deteccion de capturas es heuristica.
- HEIC necesita `pip install -e '.[heic]'`.
- `deep` reserva la interfaz para CLIP y OCR, que se incorporaran despues de calibrar el MVP.
- Nunca se debe automatizar el borrado definitivo solo con el score inicial.

