import sys
import os

def verificar_entorno():
    print("=" * 50)
    print("   DIAGNÓSTICO DEL ENTORNO DE DATA SCIENCE")
    print("=" * 50)
    
    # 1. Versión de Python instalada
    print(f" Versión de Python: {sys.version.split()[0]}")
    
    # 2. Directorio de trabajo actual
    directorio_actual = os.getcwd()
    print(f" Directorio de trabajo: {directorio_actual}")
    
    # 3. Comprobación de librerías esenciales
    librerias = ["pandas", "numpy", "matplotlib", "streamlit"]
    print("\nEstado de librerías base:")
    
    for lib in librerias:
        try:
            __import__(lib)
            print(f"   [OK] {lib} está instalada correctamente.")
        except ImportError:
            print(f"   [X] {lib} NO está instalada.")
            
    print("=" * 50)

if __name__ == "__main__":
    verificar_entorno()