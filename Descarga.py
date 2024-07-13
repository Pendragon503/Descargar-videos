from pytube import YouTube
import os

def descargar_video(url, ubicacion, formato):
    try:
        yt = YouTube(url)
        video = yt.streams.filter(file_extension=formato).first()
        if video:
            print(f"Descargando {yt.title}...")
            video.download(output_path=ubicacion)
            print("Descarga completada.")
        else:
            print(f"No se encontró un video en formato {formato}.")
    except Exception as e:
        print(f"Ocurrió un error: {str(e)}")

if __name__ == "__main__":
    url = input("Ingresa la URL del video: ")
    ubicacion = input("Ingresa la ubicación donde deseas guardar el video: ")
    formato = input("Ingresa el formato del video (ej. mp4): ")

    descargar_video(url, ubicacion, formato)
