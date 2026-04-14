import os
import django
import pandas as pd
import datetime

# 1. CONECTAR CON DJANGO
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_wms.settings')
django.setup()

from inventario.models import Material, ReporteRecepcion, DetalleRecepcion

def importar_entradas():
    print("Iniciando migración del historial de ENTRADAS (RQ)...")
    
    try:
        # Lee el excel
        df = pd.read_excel('entradas.xlsx').fillna('')
        
        nuevos_items = []
        errores = 0
        
        # Diccionario para ir guardando los reportes que vamos creando en memoria
        reportes_creados = {}
        contadores_em = {}

        for index, fila in df.iterrows():
            codigo_excel = str(fila['CODIGO_MATERIAL']).strip()
            
            # Buscar el material
            try:
                material_db = Material.objects.get(codigo=codigo_excel)
            except Material.DoesNotExist:
                # ----------------------------------------------------
                # ¡LA SOLUCIÓN! Si no existe, lo creamos automáticamente
                # ----------------------------------------------------
                material_db = Material.objects.create(
                    codigo=codigo_excel,
                    descripcion="[AUTO-CREADO POR HISTORIAL DE ENTRADA]",
                    tipo='MATERIAL',  # Le ponemos Material por defecto
                    cargo='OTRO',     # Le ponemos Otro por defecto
                    unidad_medida='UNID',
                    stock_actual=0.0
                )
                print(f"✨ Ítem auto-creado en el Maestro: {codigo_excel}")

            # Fecha limpia
            fecha_excel = fila['FECHA']
            if pd.api.types.is_datetime64_any_dtype(fecha_excel):
                fecha_limpia = fecha_excel.date()
            else:
                fecha_limpia = datetime.date.today()

            # --- LA MAGIA DEL REPORTE HISTÓRICO EXACTO ---
            # Leemos el número de reporte desde el Excel
            nro_reporte_excel = str(fila.get('REPORTE', '')).strip()
            if not nro_reporte_excel:
                nro_reporte_excel = f"S/N-{index}" # Por si alguna fila quedó en blanco

            # Si este reporte no lo hemos creado todavía, lo creamos
            if nro_reporte_excel not in reportes_creados:
                # get_or_create busca si ya existe en BD, si no, lo crea con ese número exacto
                reporte_db, created = ReporteRecepcion.objects.get_or_create(
                    nro_reporte=nro_reporte_excel,
                    defaults={
                        'fecha_recepcion': fecha_limpia,
                        'descripcion': "Migración Histórica"
                    }
                )
                reportes_creados[nro_reporte_excel] = reporte_db
            
            reporte_actual = reportes_creados[nro_reporte_excel]

            # GENERAR EL CÓDIGO EM (Ese sí se auto-genera para no chocar)
            mapa_prefijos = {'MATERIAL': 'EM', 'ACTIVOS': 'EA', 'DIRECTO AL GASTO': 'EDC'}
            prefijo = mapa_prefijos.get(material_db.tipo, 'EM')
            año_corto = fecha_limpia.strftime('%y')
            inicio_codigo = f"{prefijo}{año_corto}"

            if inicio_codigo not in contadores_em:
                ultimo_em = DetalleRecepcion.objects.filter(nro_control_entrada__startswith=inicio_codigo).order_by('id').last()
                contadores_em[inicio_codigo] = int(ultimo_em.nro_control_entrada[-4:]) if (ultimo_em and ultimo_em.nro_control_entrada) else 0
            
            contadores_em[inicio_codigo] += 1
            nuevo_nro_em = f"{inicio_codigo}{contadores_em[inicio_codigo]:04d}"

            # PREPARAR EL REGISTRO
            try: cant_sol = float(fila['CANTIDAD_SOLICITADA'])
            except: cant_sol = 0.0
            
            try: cant_rec = float(fila['CANT_RECIBIDA'])
            except: cant_rec = 0.0
            
            try: precio_u = float(fila['PRECIO_UNITARIO'])
            except: precio_u = 0.0

            item = DetalleRecepcion(
                reporte=reporte_actual,
                material=material_db,
                fecha_recepcion=fecha_limpia,
                nro_control_entrada=nuevo_nro_em,
                nro_rq=str(fila.get('RQ', '')).strip(),
                departamento=str(fila.get('DEPARTAMENTO', '')).strip(),
                nro_odc=str(fila.get('ODC', '')).strip(),
                nro_nota_entrega=str(fila.get('NOTA_ENTREGA', '')).strip(),
                proveedor=str(fila.get('PROVEEDOR', '')).strip(),
                cantidad_solicitada=cant_sol,
                cantidad_recibida=cant_rec,
                precio_unitario=precio_u,
                observaciones=str(fila.get('OBSERVACIONES', '')).strip()
            )
            nuevos_items.append(item)

        # INYECCIÓN MASIVA (Mete todo sin tocar el Stock, porque el Maestro ya tiene el stock bien)
        if nuevos_items:
            DetalleRecepcion.objects.bulk_create(nuevos_items)
            print(f"✅ ¡ÉXITO! Se migraron {len(nuevos_items)} ítems de recepción.")
        
        if errores > 0:
            print(f"⚠️ Hubo {errores} filas omitidas.")

    except Exception as e:
        print(f"❌ Ocurrió un error inesperado: {e}")

if __name__ == '__main__':
    importar_entradas()