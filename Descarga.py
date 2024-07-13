import tkinter as tk
from tkinter import messagebox
from tkinter import filedialog
from pytube import YouTube
from urllib.error import HTTPError
import os

def descargar_video(url, ubicacion, formato):
    try:
        yt = YouTube(url)
        streams = yt.streams.filter(progressive=True).order_by('resolution').desc()

        if not streams:
            messagebox.showerror("Error", "No se encontró un formato de video progresivo disponible para descargar.")
            return

        # Mostrar los formatos disponibles y preguntar al usuario cuál desea descargar
        opciones_formato = [stream.mime_type.split("/")[-1] for stream in streams]
        seleccionado = messagebox.askquestion("Seleccionar formato", 
                                              f"Formatos disponibles: {', '.join(opciones_formato)}\n"
                                              f"¿Deseas descargar en formato {formato}?")

        if seleccionado == 'yes':
            video = streams.first()
            # Descargar el video
            print(f"Descargando {yt.title} en formato {video.mime_type}...")
            video.download(output_path=ubicacion)
            print("Descarga completada.")

            # Mostrar mensaje de éxito
            messagebox.showinfo("Descarga completada", f"Se ha descargado {yt.title} correctamente en {ubicacion}.")
        else:
            messagebox.showinfo("Descarga cancelada", "Descarga cancelada por el usuario.")

    except HTTPError as e:
        messagebox.showerror("Error", f"Ocurrió un error HTTP: {str(e)}.\nEl video podría no estar disponible.")
    except Exception as e:
        messagebox.showerror("Error", f"Ocurrió un error: {str(e)}")

def seleccionar_ubicacion():
    ubicacion = filedialog.askdirectory()
    if ubicacion:
        entry_ubicacion.delete(0, tk.END)
        entry_ubicacion.insert(0, ubicacion)

# Crear la ventana principal
root = tk.Tk()
root.title("Descargar Video")

# Función para manejar la descarga
def manejar_descarga():
    url = entry_url.get()
    ubicacion = entry_ubicacion.get()

    if not url or not ubicacion:
        messagebox.showerror("Error", "Por favor ingresa la URL del video y selecciona la ubicación de descarga.")
        return

    # Preseleccionar formato como mp4
    formato = "mp4"

    descargar_video(url, ubicacion, formato)

# Obtener la ruta del escritorio
desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")

# Crear y posicionar los elementos en la ventana
label_url = tk.Label(root, text="URL del video:")
label_url.pack()
entry_url = tk.Entry(root, width=50)
entry_url.pack()

label_ubicacion = tk.Label(root, text="Ubicación de descarga:")
label_ubicacion.pack()

entry_ubicacion = tk.Entry(root, width=50)
entry_ubicacion.insert(0, desktop_path)  # Establecer la ubicación predeterminada al escritorio
entry_ubicacion.pack()

btn_seleccionar_ubicacion = tk.Button(root, text="Seleccionar ubicación", command=seleccionar_ubicacion)
btn_seleccionar_ubicacion.pack()

# Botón para descargar
btn_descargar = tk.Button(root, text="Descargar", command=manejar_descarga)
btn_descargar.pack()

# Ejecutar la interfaz
root.mainloop()
