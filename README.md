# Microsoft Rewards Autoclicker

> 🟢 Automatización de flujo de búsquedas y lectura móvil con enfoque ADB para Android real por USB.

## ✨ ¿Qué hace este proyecto?

Este script automatiza comportamientos tipo usuario para Microsoft Rewards:

- 🧠 Simula búsquedas con escritura natural (desktop).
- 📱 Lee noticias en Android real por USB usando ADB.
- 🧭 Filtra contenido no deseado en móvil:
	- ignora anuncios,
	- ignora tarjetas de video,
	- rechaza banners de cookies cuando aparecen.
- 📝 Guarda trazabilidad en CSV por cuenta en la carpeta logs.

## 🎬 Flujo visual del modo Android

Inicio → Scroll inicial largo → Detectar noticia válida → Tap centrado
→ Rechazar cookies (si aparece) → Scroll dentro del artículo
→ Espera de lectura → Volver atrás → Scroll de salida → Siguiente ciclo

## ✅ Requisitos

### Requisitos generales

- Python 3.11 o superior.
- Windows con conexión a Internet.
- Dependencias del proyecto instaladas.

### Requisitos desktop

- Google Chrome o Microsoft Edge instalado.

### Requisitos Android USB (modo recomendado para noticias)

- Android platform-tools instalado (adb disponible).
- Teléfono Android real (USB).
- App Microsoft Bing instalada en el teléfono.
- USB debugging habilitado en Opciones de desarrollador.

## 🚀 Instalación paso a paso

### 1) Clonar o abrir proyecto

Ubícate en la carpeta del proyecto:

```bash
cd c:\Users\LAAO\Projects\autoclicker
```

### 2) Crear y activar entorno virtual (recomendado)

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3) Instalar dependencias

```bash
pip install -r requirements.txt
```

## 🧪 Verificación rápida del entorno

### Verificar Python

```bash
python --version
```

### Verificar ADB

```bash
adb version
adb devices
```

Si el teléfono aparece como unauthorized:

1. Desconecta USB.
2. Conecta de nuevo.
3. Acepta la huella RSA en el teléfono.
4. Ejecuta adb devices otra vez.

## 🖥️ Ejecución desktop (búsquedas)

### Cuenta por defecto

```bash
python autoclicker.py
```

### Cuenta personalizada + headless

```bash
python autoclicker.py --account usuario@ejemplo.com --headless
```

> ℹ️ Nota: la lectura de noticias en desktop no se usa para acreditación de Rewards con este flujo.

## 📱 Ejecución Android USB (ADB)

### Comando recomendado

```bash
python autoclicker.py --android-adb --adb-serial <serial> --android-cycles 10
```

Si tienes un solo dispositivo conectado, puedes omitir adb-serial.

### Pasos detallados en el teléfono

1. Abre Bing y déjalo instalado/actualizado.
2. Mantén pantalla desbloqueada durante la ejecución.
3. Conecta por USB y verifica serial con adb devices.
4. Ejecuta el comando anterior.
5. El script:
	 - hará scroll inicial,
	 - elegirá noticias válidas,
	 - evitará anuncios y videos,
	 - rechazará cookies cuando detecte botón de rechazo,
	 - hará scroll dentro del artículo,
	 - volverá al feed y repetirá.

## ⚙️ Argumentos disponibles

| Argumento | Descripción | Valor por defecto |
|---|---|---|
| --account | Identificador de cuenta (etiqueta para logs) | default |
| --headless | Ejecuta navegador sin UI visible (desktop) | No |
| --android-adb | Activa flujo móvil ADB por USB | No |
| --adb-serial | Serial ADB del dispositivo Android | Vacío |
| --android-cycles | Cantidad de ciclos de lectura móvil | 10 |

## 🧩 Configuración avanzada

Edita config.py para afinar comportamiento.

Parámetros útiles del modo Android:

- ARTICLE_DWELL_MIN / ARTICLE_DWELL_MAX
- ANDROID_NEWS_CYCLES
- ANDROID_NEWS_MIN_TOP_PX
- ANDROID_NEWS_SCROLL_STEPS_MIN / MAX
- ANDROID_NEWS_RETURN_WAIT_MIN / MAX

## 🛡️ Filtros inteligentes en Android

El selector móvil descarta automáticamente:

- 🔕 tarjetas de anuncios: anuncio, patrocinado, publicidad, sponsored, etc.
- 🎥 tarjetas de video: video, reproducir, play, duración, y sellos como 02:13.
- 🔝 elementos de cabecera superior (evita tocar el buscador).

## 🧾 Logs y salida

Se crea un CSV por cuenta en logs con formato:

```csv
date,account,keyword,url,dwell_seconds
2025-06-01 08:15:32,usuario@ejemplo.com,titular visible,adb://device,10.0
```

## 🧪 Pruebas

```bash
python -m pytest tests/ -v
```

## 🗂️ Estructura del proyecto

```text
autoclicker/
├── autoclicker.py
├── config.py
├── searches.py
├── typer.py
├── logger.py
├── requirements.txt
├── tests/
└── logs/
```

## 🧯 Solución de problemas

### El script toca el buscador superior

- Aumenta ANDROID_NEWS_MIN_TOP_PX en config.py.

### El script no detecta noticias válidas

- Haz un scroll manual en Bing para refrescar cards.
- Verifica que no estés en una pestaña distinta del feed.

### No aparece el teléfono en adb devices

- Revisa cable USB de datos.
- Activa USB debugging.
- Reinstala drivers USB/OEM si aplica.

### Aparece banner de cookies y bloquea flujo

- El script intenta rechazar automáticamente.
- Si cambia el texto del botón, se puede ampliar el matcher.

## ⚠️ Nota de uso

Usa este proyecto bajo tu responsabilidad y respetando los términos y políticas de la plataforma objetivo.