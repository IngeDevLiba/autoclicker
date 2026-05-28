# Microsoft Rewards Autoclicker

Simula búsquedas en Microsoft Rewards de forma natural, distribuyéndolas a lo largo del día en bloques (mañana, tarde y noche) con velocidad de escritura variable, errores tipográficos ocasionales y tiempos de espera aleatorios.

## Características

| Característica | Detalle |
|---|---|
| Búsquedas diarias | 30–40 por cuenta |
| Temas | Noticias, deportes, tecnología, cultura, ciencia, salud, economía |
| Velocidad de escritura | 80–120 ms por tecla (variable) |
| Errores tipográficos | ~4 % de probabilidad, con autocorrección |
| Pausa entre búsquedas | 10–30 segundos (aleatoria) |
| Lectura de artículos | 20–40 segundos con scroll simulado |
| Bloques horarios | Mañana (08–11), Tarde (14–17), Noche (20–23) |
| Registro | CSV por cuenta en la carpeta `logs/` |

## Requisitos

- Python 3.11 o superior
- Google Chrome o Microsoft Edge instalado
- Conexión a Internet

## Instalación

```bash
pip install -r requirements.txt
```

## Uso

```bash
# Cuenta por defecto (log guardado en logs/default.csv)
python autoclicker.py

# Especificar cuenta y modo headless (sin ventana)
python autoclicker.py --account usuario@ejemplo.com --headless
```

### Argumentos

| Argumento | Descripción | Valor por defecto |
|---|---|---|
| `--account` | Identificador de cuenta (etiqueta para el log) | `default` |
| `--headless` | Ejecutar el navegador sin ventana visible | No |
| `--android-adb` | Usar ADB para leer noticias en Android sin Appium | No |
| `--adb-serial` | Serial ADB del dispositivo Android | Vacío |
| `--android-cycles` | Número de ciclos de lectura de noticias en Android | `10` |

## Nota sobre noticias

La automatización de noticias de Microsoft Rewards no se acredita en Windows PC con este flujo. El script la omite en escritorio para evitar un comportamiento que Microsoft no contabiliza y que además entra en conflicto con sus políticas.

## Android real

La alternativa recomendada es usar un teléfono Android real conectado por USB y automatizarlo con `adb`. Este modo no usa Appium y es más corto de poner en marcha.

```bash
python autoclicker.py --android-adb --adb-serial <serial> --android-cycles 10
```

Guía rápida:

1. Instala Android platform-tools y verifica que `adb` responde en la terminal con `adb version`.
2. En tu teléfono, activa Opciones de desarrollador y luego USB debugging.
3. Conecta el teléfono por USB y acepta la huella RSA cuando aparezca.
4. Ejecuta `adb devices` y copia el serial que aparezca como `device`.
5. Lanza el script con `python autoclicker.py --android-adb --adb-serial <serial> --android-cycles 10`.
6. El script abrirá Bing en el teléfono, hará un desplazamiento gradual por la sección de noticias, intentará abrir la primera noticia visible con varios puntos de toque y, si hace falta, usará Enter como respaldo.
7. Después esperará la carga, permanecerá un tiempo aleatorio dentro del artículo y volverá atrás.
8. Repetirá ese ciclo el número de veces indicado con `--android-cycles`.

Si tienes un solo dispositivo conectado, puedes omitir `--adb-serial`.

En este modo, el script usa el paquete `com.microsoft.bing` y `uiautomator dump` para localizar titulares visibles, pero ya no depende de Appium ni de automatización de búsqueda en Android.

## Consejos

- Mantén la pantalla desbloqueada mientras corre el script.
- Si `adb devices` muestra `unauthorized`, desconecta y vuelve a conectar el USB para aceptar la autorización.
- Si Bing no abre en el teléfono, confirma que la app está instalada y actualizada.
- Si no detecta noticias visibles, desplázate una vez manualmente dentro de Bing para cargar más contenido y vuelve a ejecutar.

## Configuración

Edita `config.py` para ajustar los parámetros de tiempo, número de búsquedas y bloques horarios.

```python
# Ejemplo: cambiar el rango de búsquedas diarias
DAILY_SEARCHES_MIN = 30
DAILY_SEARCHES_MAX = 40

# Ejemplo: ajustar la velocidad de escritura (ms)
TYPING_SPEED_MIN_MS = 80
TYPING_SPEED_MAX_MS = 120
```

## Estructura del proyecto

```
autoclicker/
├── autoclicker.py   # Orquestador principal
├── config.py        # Parámetros configurables
├── searches.py      # Banco de búsquedas por categoría
├── typer.py         # Simulación de escritura natural
├── logger.py        # Registro CSV por cuenta
├── requirements.txt # Dependencias Python
├── tests/           # Pruebas unitarias
│   ├── test_searches.py
│   ├── test_typer.py
│   └── test_logger.py
└── logs/            # Generado automáticamente (gitignored)
```

## Formato del log

Cada cuenta genera un archivo CSV en `logs/`:

```
date,account,keyword,url,dwell_seconds
2025-06-01 08:15:32,usuario@ejemplo.com,últimas noticias de fútbol,https://www.bing.com/search?q=...,0.0
2025-06-01 08:15:32,usuario@ejemplo.com,últimas noticias de fútbol,https://www.marca.com/...,27.4
```

## Ejemplo de salida en consola

```
[08:14:55] Sesión iniciada para la cuenta 'usuario@ejemplo.com'. Total de búsquedas planificadas hoy: 35.
[08:15:01] Bloque 1 (08:00–11:00): 12 búsquedas.
[08:15:01] Escribiendo búsqueda: últimas noticias de fútbol…
[08:15:09] Resultados cargados: https://www.bing.com/search?q=...
[08:15:09] Leyendo artículo: Resultados de la jornada – Marca…
[08:15:12] Desplazando página 420px…
[08:15:15] Desplazando página 310px…
[08:15:38] Artículo leído durante 29 segundos.
[08:15:38] Esperando 18 segundos antes de la siguiente búsqueda…
```

## Ejecutar pruebas

```bash
python -m pytest tests/ -v
```