import os
import django
import pandas as pd

# 1. CONECTAR ESTE SCRIPT CON TU PROYECTO DJANGO
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_wms.settings')
django.setup()

# 2. IMPORTAR EL MODELO MAESTRO
from inventario.models import Material

def importar_excel():
    print("Iniciando migración desde Excel...")
    
    try:
        # 3. LEER EL EXCEL CON PANDAS
        # fillna('') reemplaza las celdas vacías por texto en blanco para evitar errores
        df = pd.read_excel('inventario.xlsx').fillna('')
        
        contador_nuevos = 0
        contador_actualizados = 0

        # 4. RECORRER CADA FILA DEL EXCEL
        for index, fila in df.iterrows():
            # update_or_create: Busca si el código ya existe. Si existe lo actualiza, si no, lo crea.
            material, creado = Material.objects.update_or_create(
                codigo=str(fila['CODIGO']).strip(),
                defaults={
                    'descripcion': str(fila['DESCRIPCION']).strip(),
                    'tipo': str(fila['TIPO']).strip().upper(),
                    'nro_parte': str(fila['NRO_PARTE']).strip(),
                    'unidad_medida': str(fila['UM']).strip().upper(),
                    'ubicacion': str(fila['UBICACION']).strip(),
                    'stock_actual': float(fila['STOCK']) if fila['STOCK'] else 0.0,
                }
            )
            
            if creado:
                contador_nuevos += 1
                print(f"✅ Creado: {material.codigo} - {material.descripcion}")
            else:
                contador_actualizados += 1
                print(f"🔄 Actualizado: {material.codigo}")

        print("=======================================")
        print("🎉 ¡MIGRACIÓN COMPLETADA CON ÉXITO! 🎉")
        print(f"Materiales Nuevos: {contador_nuevos}")
        print(f"Materiales Actualizados: {contador_actualizados}")
        print("=======================================")

    except Exception as e:
        print(f"❌ Ocurrió un error: {e}")
        print("Asegúrate de que el archivo se llame 'inventario.xlsx' y esté cerrado en Excel.")

if __name__ == '__main__':
    importar_excel()
    