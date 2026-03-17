# Descargar-videos
 ## Descripción
 
 Aplicación de escritorio para descargar videos de YouTube en formato MP3 (solo audio) o MP4 (video completo). Proporciona una interfaz gráfica intuitiva con monitoreo de progreso en tiempo real, opciones de calidad personalizables y cancelación de descargas.
 
 ## Características
 
 - **Descarga en MP3 o MP4**: Extrae solo audio o video completo según tus necesidades
 - **Selección de calidad**: Elige desde 360p hasta 2160p (4K) para MP4
 - **Interfaz gráfica moderna**: Diseño oscuro profesional con Tkinter
 - **Monitoreo en tiempo real**: Barra de progreso, velocidad de descarga y ETA
 - **Cancelación de descargas**: Detén el proceso en cualquier momento
 - **Gestión de carpetas**: Selecciona la ubicación de destino fácilmente
 - **Registro detallado**: Log completo de todas las operaciones
 - **Persistencia de configuración**: Guarda automáticamente tus preferencias
 
 ## Requisitos previos
 
 - **Python 3.8 o superior**
 - **FFmpeg**: Instalado y disponible en el PATH del sistema
	 - Windows: Descargalo desde [ffmpeg.org](https://ffmpeg.org/download.html)
	 - macOS: `brew install ffmpeg`
	 - Linux: `sudo apt-get install ffmpeg`
 
 ## Instalación
 
 1. Clona o descarga este repositorio
 2. Instala las dependencias:
		```bash
		pip install -r requirements.txt
		```
 3. Asegúrate de que FFmpeg esté correctamente instalado
 
 ## Uso
 
 Ejecuta la aplicación:
 ```bash
 python DVideoaudio.py
 ```
 
 1. Ingresa la URL del video de YouTube
 2. Selecciona la carpeta destino
 3. Elige el formato (MP3 o MP4) y la calidad si es necesario
 4. Haz clic en "Descargar"
 5. Monitorea el progreso en la barra y el registro
 
 ## Estructura del proyecto
 
 - `DVideoaudio.py`: Aplicación principal con interfaz gráfica
 - `Descarga.py`: Módulo complementario (disponible si es necesario)
 - `yt_downloader_config.json`: Archivo de configuración automático
 - `LICENSE`: Licencia del proyecto
 
 ## Notas técnicas
 
 - Utiliza **yt-dlp** para descargas confiables y compatibles
 - La aplicación evita descargas de playlists (solo video único)
 - Los errores se registran en `errores.txt` dentro de la carpeta destino
 - Los nombres de archivo se sanitizan automáticamente
 
 ## Desarrollo
 
 Desarrollador: William Martínez  
 GitHub: [Pendragon503](https://github.com/Pendragon503)
