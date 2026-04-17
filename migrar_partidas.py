import os
import django
import pandas as pd
import datetime

# 1. CONECTAR CON DJANGO
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_wms.settings')
django.setup()

# Importamos tu tabla financiera
from inventario.models import PresupuestoAnual

def importar_partidas():
    print("Iniciando carga del Maestro de Partidas Presupuestarias...")
    
    try:
        # Leemos el archivo excel
        df = pd.read_excel('partidas.xlsx').fillna('')
        
        # Tomamos el año actual para asignarlo al presupuesto
        anio_actual = datetime.date.today().year
        contador_nuevos = 0

        for index, fila in df.iterrows():
            # Si el departamento está vacío, saltamos la fila
            departamento = str(fila.get('DEPARTAMENTO', '')).strip()
            if not departamento:
                continue

            # Creamos o actualizamos la partida en la base de datos
            partida_db, creado = PresupuestoAnual.objects.update_or_create(
                anio=anio_actual,
                departamento=departamento,
                cuenta_contable=str(fila.get('CUENTA_CONTABLE', '')).strip(),
                partida=str(fila.get('PARTIDA_PRESUPUESTARIA', '')).strip(),
                defaults={
                    'descripcion_cuenta': str(fila.get('DESCRIPCION_CUENTA', '')).strip()
                }
            )
            
            if creado:
                contador_nuevos += 1

        print("=======================================")
        print(f"✅ ¡ÉXITO! Se cargaron {contador_nuevos} reglas financieras a la base de datos.")
        print("=======================================")

    except KeyError as e:
        print(f"❌ ERROR: No se encontró la columna {e} en tu Excel.")
        print("Asegúrate de que los encabezados sean: PARTIDA_PRESUPUESTARIA, CUENTA_CONTABLE, DESCRIPCION_CUENTA, DEPARTAMENTO")
    except Exception as e:
        print(f"❌ Ocurrió un error inesperado: {e}")
        print("Asegúrate de que el archivo se llame 'partidas.xlsx' y esté cerrado.")

if __name__ == '__main__':
    importar_partidas()