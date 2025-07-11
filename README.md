# Descargador YouTube (Video MP4 + Audio MP3) - zkingStudios

Aplicación de escritorio para Windows que descarga videos de YouTube en MP4 (video) y MP3 (audio) con soporte para aceleración por hardware (NVIDIA, AMD, Intel) usando FFmpeg.

## Características
- Descarga videos y playlists de YouTube.
- Convierte video a MP4 (H.264) y audio a MP3 (320kbps).
- Selección de resolución y encoder (NVIDIA, AMD, Intel, CPU).
- Descarga automática de FFmpeg si no está presente.
- Historial de descargas.
- Interfaz gráfica amigable (Tkinter).

## Versiones disponibles

- **Versión 1.1 (Python):**  
  Ejecuta directamente con Python. Funciona sin compilar y es menos propensa a ser bloqueada por antivirus.  
  Ideal para usuarios que solo quieren descargar videos o audio por separado.

- **Versión EXE (fusión de video y audio):**  
  Permite fusionar automáticamente video y audio en un solo archivo MP4.  
  **IMPORTANTE:** Windows Defender y otros antivirus pueden detectar el EXE como sospechoso (falso positivo). Si confías en el programa, añade una excepción en tu antivirus.

## Requisitos
- Windows 10/11
- Python 3.9 o superior
- Conexión a internet (para descargar dependencias y FFmpeg)
- FFmpeg (se descarga automáticamente si no está presente)

## Instalación
Lee el archivo [`instalacion.txt`](instalacion.txt) para instrucciones detalladas.

## Compilación a EXE
Lee el archivo [`compilar.txt`](compilar.txt) si quieres la versión con fusión de video y audio.

## Uso
1. Ejecuta `ZkingDownload.py` con Python o usa el ejecutable si lo compilaste.
2. Pega la URL de YouTube, selecciona formato y descarga.

## Advertencia sobre antivirus

- El ejecutable EXE puede ser detectado como sospechoso por Windows Defender u otros antivirus.  
- Esto es un **falso positivo** común en programas compilados con PyInstaller.  
- Si confías en el programa, añade una excepción en tu antivirus para la carpeta donde está el EXE.

## Licencia

Este software es gratuito y de uso libre para fines personales, educativos y no comerciales.  
Consulta el archivo [`LICENSE`](LICENSE) para más detalles.

---

**Desarrollado por zkingStudios**