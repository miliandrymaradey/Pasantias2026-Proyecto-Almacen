import os
import django
import pandas as pd

# 1. CONECTAR CON DJANGO
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_wms.settings')
django.setup()

from inventario.models import Material, SalidaMaterial
from django.utils.dateparse import parse_date
import datetime

def importar_salidas():
    print("Iniciando migración del historial de Salidas (RIM)...")
    
    try:
        # Leer el Excel. Tratamos las fechas como datetime para evitar errores
        df = pd.read_excel('salidas.xlsx').fillna('')
        
        nuevas_salidas = []
        errores = 0

        for index, fila in df.iterrows():
            codigo_excel = str(fila['CODIGO_MATERIAL']).strip()
            
            # Buscar si el material existe en nuestra base de datos
            try:
                material_db = Material.objects.get(codigo=codigo_excel)
            except Material.DoesNotExist:
                print(f"⚠️ Fila {index+2} omitida: El código {codigo_excel} no existe en el Registro Maestro.")
                errores += 1
                continue # Salta a la siguiente fila

            # Convertir la fecha de Pandas a fecha de Python
            fecha_excel = fila['FECHA']
            if pd.api.types.is_datetime64_any_dtype(fecha_excel):
                fecha_limpia = fecha_excel.date()
            else:
                fecha_limpia = datetime.date.today() # Si no hay fecha, pone la de hoy

            # PREPARAR EL REGISTRO (Sin guardarlo todavía)
            salida = SalidaMaterial(
                material=material_db,
                fecha_despacho=fecha_limpia,
                nro_rim=str(fila['RIM']).strip(),
                cantidad=float(fila['CANTIDAD']) if fila['CANTIDAD'] else 0.0,
                centro_costo=str(fila['CENTRO_COSTO']).strip(),
                cuenta_contable=str(fila['CUENTA_CONTABLE']).strip(),
                partida_presupuestaria=str(fila['PARTIDA']).strip(),
            )
            nuevas_salidas.append(salida)

        # INYECCIÓN MASIVA (bulk_create): 
        # Guarda miles de registros en 1 segundo y NO ejecuta el .save() individual,
        # por lo tanto, NO resta el stock de nuevo (evitando la trampa del doble descuento).
        if nuevas_salidas:
            SalidaMaterial.objects.bulk_create(nuevas_salidas)
            print(f"✅ ¡ÉXITO! Se migraron {len(nuevas_salidas)} despachos históricos.")
        
        if errores > 0:
            print(f"⚠️ Hubo {errores} filas que no se migraron porque el código del material no existía.")

    except KeyError as e:
        print(f"❌ ERROR: No se encontró la columna {e} en tu Excel.")
        print("Asegúrate de que los encabezados sean: FECHA, RIM, CODIGO_MATERIAL, CANTIDAD, CENTRO_COSTO, CUENTA_CONTABLE, PARTIDA")
    except Exception as e:
        print(f"❌ Ocurrió un error inesperado: {e}")

if __name__ == '__main__':
    importar_salidas()