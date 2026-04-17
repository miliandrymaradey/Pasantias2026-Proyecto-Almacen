import os
import django
import pandas as pd

# 1. CONECTAR CON DJANGO
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_wms.settings')
django.setup()

from inventario.models import CentroCosto

def importar_centros():
    print("Iniciando carga de Centros de Costo...")
    
    try:
        # Leemos el archivo excel
        df = pd.read_excel('centros_costo.xlsx').fillna('')
        
        contador_nuevos = 0
        contador_actualizados = 0

        for index, fila in df.iterrows():
            nombre = str(fila.get('NOMBRE', '')).strip()
            
            # Si el nombre está vacío, saltamos la fila
            if not nombre:
                print(f"  ⚠ Fila {index + 2} saltada: nombre vacío.")
                continue

            descripcion = str(fila.get('DESCRIPCION', '')).strip()

            # Creamos o actualizamos el centro en la base de datos
            centro, creado = CentroCosto.objects.update_or_create(
                nombre=nombre,
                defaults={
                    'descripcion': descripcion or None
                }
            )
            
            if creado:
                contador_nuevos += 1
                print(f"  ✅ NUEVO: {nombre}")
            else:
                contador_actualizados += 1
                print(f"  🔄 ACTUALIZADO: {nombre}")

        print("=======================================")
        print(f"✅ ÉXITO: {contador_nuevos} nuevos, {contador_actualizados} actualizados.")
        print("=======================================")

    except FileNotFoundError:
        print("❌ ERROR: No se encontró el archivo 'centros_costo.xlsx'.")
        print("   Asegúrate de que el archivo esté en la carpeta raíz del proyecto.")
    except KeyError as e:
        print(f"❌ ERROR: No se encontró la columna {e} en el Excel.")
        print("   Los encabezados deben ser: NOMBRE | DESCRIPCION")
    except Exception as e:
        print(f"❌ Error inesperado: {e}")

if __name__ == '__main__':
    importar_centros()
