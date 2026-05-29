# Microsoft Rewards Autoclicker

Automatización para dos flujos separados:

- Búsquedas web en Windows con Microsoft Edge.
- Lectura de noticias en Android real por USB usando ADB.

## Qué hace

Este proyecto:

- escribe búsquedas de forma natural en desktop,
- mantiene pausas cortas entre bloques en Windows,
- lee noticias en Android por USB,
- filtra anuncios, tarjetas de video y banners de cookies en móvil,
- guarda trazabilidad por cuenta en CSV dentro de `logs/`.

## Requisitos

- Python 3.11 o superior.
- Windows con Microsoft Edge instalado.
- Conexión a Internet para el flujo desktop.
- Android platform-tools instalado si vas a usar el modo USB.
- Teléfono Android real con USB debugging habilitado.
- App Microsoft Bing instalada en el teléfono para el modo Android.

## Instalación

### 1. Abrir la carpeta del proyecto

```powershell
cd c:\Users\LAAO\Projects\autoclicker
```

### 2. Crear el entorno virtual

```powershell
python -m venv .venv
```

### 3. Activar el entorno virtual

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. Instalar dependencias

```powershell
pip install -r requirements.txt
```

## Verificación rápida

### Python

```powershell
python --version
```

### ADB

```powershell
adb version
adb devices
```

Si el teléfono aparece como `unauthorized`:

1. Desconecta el USB.
2. Vuelve a conectarlo.
3. Acepta la huella RSA en el teléfono.
4. Ejecuta `adb devices` otra vez.

## Uso desktop

### Ejecución normal

```powershell
python autoclicker.py
```

### Cuenta personalizada

```powershell
python autoclicker.py --account usuario@ejemplo.com
```

### Modo seguro sin red

```powershell
python autoclicker.py --simulate
```

Este modo solo genera búsquedas y las registra en CSV. No abre navegador ni accede a la web.

### Comportamiento del escritorio

- El script usa Microsoft Edge.
- No abre enlaces de resultados.
- Entre bloques hace pausas cortas de minutos, no de horas.
- Entre búsquedas hace una pausa breve aleatoria.

## Uso Android por USB

### Comando

```powershell
python autoclicker.py --android-adb --adb-serial <serial> --android-cycles 10
```

Si solo hay un dispositivo conectado, puedes omitir `--adb-serial`.

### Pasos recomendados

1. Abre Bing en el teléfono y déjalo actualizado.
2. Mantén la pantalla desbloqueada durante la ejecución.
3. Conecta el teléfono por USB.
4. Ejecuta `adb devices` y confirma que el serial aparece como `device`.
5. Lanza el comando anterior.
6. El script hará scroll inicial, buscará tarjetas válidas, rechazará cookies si aparece el botón y volverá al feed al terminar cada ciclo.

## Argumentos disponibles

| Argumento | Descripción | Valor por defecto |
|---|---|---|
| `--account` | Identificador de cuenta para logs | `default` |
| `--headless` | Ejecuta el navegador sin UI visible en desktop | No |
| `--android-adb` | Activa el flujo móvil por USB | No |
| `--adb-serial` | Serial ADB del dispositivo Android | Vacío |
| `--android-cycles` | Cantidad de ciclos de lectura móvil | `10` |
| `--simulate` | Genera y registra búsquedas sin acceder a la web | No |

## Configuración

Edita `config.py` si quieres ajustar tiempos, bloques o filtros.

Parámetros útiles:

- `DAILY_SEARCHES_MIN` / `DAILY_SEARCHES_MAX`
- `BETWEEN_SEARCHES_MIN` / `BETWEEN_SEARCHES_MAX`
- `BLOCK_GAP_MIN` / `BLOCK_GAP_MAX`
- `ANDROID_NEWS_CYCLES`
- `ANDROID_NEWS_MIN_TOP_PX`
- `ANDROID_NEWS_SCROLL_STEPS_MIN` / `ANDROID_NEWS_SCROLL_STEPS_MAX`
- `ANDROID_NEWS_RETURN_WAIT_MIN` / `ANDROID_NEWS_RETURN_WAIT_MAX`

## Filtros Android

El selector móvil intenta evitar:

- anuncios,
- tarjetas de video,
- elementos superiores del encabezado,
- banners de cookies cuando detecta un botón de rechazo.

## Logs

Cada cuenta genera un CSV en `logs/`.

Ejemplo:

```csv
date,account,keyword,url,dwell_seconds
2025-06-01 08:15:32,usuario@ejemplo.com,titular visible,adb://device,10.0
```

## Pruebas

```powershell
python -m pytest tests/ -v
```

## Estructura

```text
autoclicker/
├── autoclicker.py
├── android_helpers.py
├── config.py
├── logger.py
├── searches.py
├── typer.py
├── requirements.txt
├── tests/
└── logs/
```

## Solución de problemas

### El script tarda demasiado entre bloques

- Revisa `DAILY_BLOCKS` en `config.py`.
- El modo desktop usa pausas cortas de minutos entre bloques.

### El script toca un elemento demasiado alto en Android

- Sube `ANDROID_NEWS_MIN_TOP_PX` en `config.py`.

### No aparece el teléfono en `adb devices`

- Revisa el cable USB.
- Verifica que USB debugging esté activado.
- Instala o repara los drivers USB/OEM si hace falta.

### El flujo Android no detecta noticias válidas

- Haz un scroll manual en Bing para refrescar las cards.
- Verifica que estés en el feed correcto.

### El banner de cookies cambia de texto

- El script intenta rechazarlo automáticamente.
- Si cambió el texto del botón, habrá que ampliar el matcher.

## Nota

Usa este proyecto respetando los términos y políticas de la plataforma objetivo.