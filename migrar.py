import os
import django
import pandas as pd

# 1. CONECTAR ESTE SCRIPT CON TU PROYECTO DJANGO
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_wms.settings')
django.setup()

# 2. IMPORTAR EL MODELO MAESTRO
from inventario.models import Material

def importar_excel():
    print("Iniciando migración desde Excel al Registro Maestro...")
    
    try:
        # 3. LEER EL EXCEL (fillna('') evita errores con celdas vacías)
        df = pd.read_excel('inventario.xlsx').fillna('')
        
        contador_nuevos = 0
        contador_actualizados = 0

        # 4. RECORRER CADA FILA
        for index, fila in df.iterrows():
            
            # Pequeño filtro de seguridad para el CARGO
            cargo_excel = str(fila.get('CARGO', 'OTRO')).strip().upper()
            if cargo_excel not in ['MANTENIMIENTO', 'OPERACIONES', 'TRANSPORTE', 'OTRO']:
                cargo_excel = 'OTRO' # Si escribieron mal la palabra en Excel, le pone OTRO para que no explote

            # Guardar o Actualizar en la Base de Datos
            material, creado = Material.objects.update_or_create(
                codigo=str(fila['CODIGO']).strip(),
                defaults={
                    'descripcion': str(fila['DESCRIPCION']).strip(),
                    'tipo': str(fila['TIPO']).strip().upper(),
                    'cargo': cargo_excel, # <--- EL CAMPO NUEVO
                    'nro_parte': str(fila['NRO_PARTE']).strip(),
                    'unidad_medida': str(fila['UM']).strip().upper(),
                    'ubicacion': str(fila['UBICACION']).strip(),
                    'stock_actual': float(fila['STOCK']) if fila['STOCK'] else 0.0,
                }
            )
            
            if creado:
                contador_nuevos += 1
                print(f"✅ Creado: {material.codigo}")
            else:
                contador_actualizados += 1
                print(f"🔄 Actualizado: {material.codigo}")

        print("=======================================")
        print("🎉 ¡MIGRACIÓN COMPLETADA CON ÉXITO! 🎉")
        print(f"Materiales Nuevos: {contador_nuevos}")
        print(f"Materiales Actualizados: {contador_actualizados}")
        print("=======================================")

    except KeyError as e:
        print(f"❌ ERROR: No se encontró la columna {e} en tu Excel.")
        print("Asegúrate de que los encabezados se llamen exactamente: CODIGO, DESCRIPCION, TIPO, CARGO, NRO_PARTE, UM, UBICACION, STOCK")
    except Exception as e:
        print(f"❌ Ocurrió un error inesperado: {e}")
        print("Asegúrate de que el archivo se llame 'inventario.xlsx' y esté cerrado.")

if __name__ == '__main__':
    importar_excel()