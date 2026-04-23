import os

import django

import pandas as pd

from decimal import Decimal

from django.db import transaction



# ==============================================================================

# CONFIGURACIÓN DEL ENTORNO DJANGO

# ==============================================================================

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_wms.settings')

django.setup()



from inventario.models import Material, DetalleRecepcion, SalidaMaterial, SalidaMaterialDetalle



def migrar_saldos(file_path='saldos_iniciales.xlsx'):

    """

    Script para la carga masiva de inventario histórico (Saldos Iniciales).

    Mapea materiales por código y crea registros en DetalleRecepcion.

    """

    if not os.path.exists(file_path):

        print(f"❌ Error: No se encontró el archivo '{file_path}' en la raíz.")

        return



    print(f"🚀 Iniciando migración de saldos desde: {file_path}")



    try:

        # Cargar el Excel usando pandas

        df = pd.read_excel(file_path)

    except Exception as e:

        print(f"❌ Error al leer el Excel: {e}")

        return



    # Limpieza básica de datos

    df = df.where(pd.notnull(df), None)



    detalles_a_crear = []
    salidas_a_crear = []
    salidas_detalles_info = []

    materiales_a_actualizar = {} # ID: Nuevo Stock



    print(f"📊 Procesando {len(df)} filas...")



    try:

        with transaction.atomic():

            for index, row in df.iterrows():

                codigo_mat = str(row.get('CÓDIGO', '')).strip()

                cantidad_sol = row.get('CANTIDAD', 0)

                cantidad_rec_original = row.get('CANT RECIB', 0)

                stock_lote = row.get('STOCK LOTE', None) # Nueva columna de stock real actual

                precio = row.get('U.P. REAL', 0)

                nro_em = row.get('N° EM')

               

                # 1. Buscar o Crear Material
                material_obj = Material.objects.filter(codigo=codigo_mat).first()
                if not material_obj:
                    print(f"⚠️ Fila {index+2}: Material '{codigo_mat}' no existe. Creando automáticamente...")
                    
                    desc = str(row.get('MATERIAL / DESCRIPCIÓN', '')).strip()
                    if not desc or desc.lower() == 'nan':
                        desc = str(row.get('DESCRIPCION', f"Material Histórico {codigo_mat}")).strip()

                    cargo_row = str(row.get('CARGO', 'OPERACIONES')).strip().upper()
                    if cargo_row not in ['MANTENIMIENTO', 'OPERACIONES', 'TRANSPORTE', 'OTRO']:
                        cargo_row = 'OPERACIONES'

                    tipo_row = str(row.get('TIPO', 'MATERIAL')).strip().upper()
                    if tipo_row not in ['MATERIAL', 'ACTIVOS', 'DIRECTO AL GASTO']:
                        tipo_row = 'MATERIAL'

                    # Intentamos buscar la U.M. en diferentes variantes posibles del header
                    um_row = str(row.get('U.M.', row.get('UM', row.get('U/M', 'C/U')))).strip().upper()
                    if um_row == 'NAN' or not um_row:
                        um_row = 'C/U'

                    np_row = str(row.get('N/P', row.get('NRO_PARTE', ''))).strip()
                    if np_row.lower() == 'nan':
                        np_row = ''

                    # Creamos el maestro (el stock se inicializa en 0, luego el script lo suma al final)
                    material_obj = Material.objects.create(
                        codigo=codigo_mat,
                        descripcion=desc,
                        tipo=tipo_row,
                        cargo=cargo_row,
                        nro_parte=np_row,
                        unidad_medida=um_row,
                        stock_actual=Decimal('0')
                    )



                # 2. Determinar cantidad original a inyectar (CANT RECIB) y diferencia
                cantidad_original = Decimal(str(cantidad_rec_original)) if pd.notna(cantidad_rec_original) else Decimal('0')
                stock_final = Decimal(str(stock_lote)) if pd.notna(stock_lote) else cantidad_original
                diferencia = cantidad_original - stock_final

                # 3. Preparar Detalle de Recepción (Entrada por el TOTAL original)
                if pd.isna(nro_em) or not str(nro_em).strip():
                    nro_control = f"HIST-{index+1:04d}"
                else:
                    nro_control = str(nro_em).strip()

                fecha_excel = row.get('FECHA REC.')
                fecha_limpia = fecha_excel if pd.notna(fecha_excel) else '2026-01-01'
                precio_dec = Decimal(str(precio)) if pd.notna(precio) else Decimal('0')

                detalle = DetalleRecepcion(
                    material=material_obj,
                    reporte=None,
                    es_saldo_inicial=True,
                    descripcion_entrada=row.get('MATERIAL / DESCRIPCIÓN') or f"Saldo Inicial - {material_obj.descripcion}",
                    fecha_recepcion=fecha_limpia,
                    nro_rq=row.get('RQ'),
                    departamento=row.get('CARGO'),
                    nro_control_entrada=nro_control,
                    nro_odc=row.get('NO ODC') or "HISTORICO",
                    proveedor=row.get('PROVEEDOR') or "SALDO INICIAL",
                    # Guardamos la ODC original en solicitada, y en recibida el TOTAL ORIGINAL (ej. 50)
                    cantidad_solicitada=Decimal(str(cantidad_sol)) if pd.notna(cantidad_sol) else Decimal('0'),
                    cantidad_recibida=cantidad_original,
                    precio_unitario=precio_dec,
                    moneda=row.get('MONEDA') or "USD",
                    nro_nota_entrega=row.get('NOTA ENTREGA') or "N/A",
                    observaciones=f"Entrada original: {cantidad_original}. Ajuste aplicado: {diferencia}. N/P: {row.get('N/P', '')}".strip()
                )
                detalles_a_crear.append(detalle)

                # 4. Ajuste Fantasma (si diferencia > 0)
                if diferencia > 0:
                    nro_rim = f"AJUSTE-MIG-{index+1:04d}"
                    salida = SalidaMaterial(
                        nro_rim=nro_rim,
                        material=material_obj,
                        departamento="MIGRACIÓN",
                        fecha_despacho=fecha_limpia,
                        observaciones=f"Ajuste de inventario histórico. Diferencia calculada: {diferencia}",
                        cantidad=diferencia
                    )
                    salidas_a_crear.append(salida)
                    
                    # Guardamos la información para vincular el detalle más adelante
                    salidas_detalles_info.append({
                        'nro_rim': nro_rim,
                        'nro_control_entrada': nro_control,
                        'cantidad': diferencia,
                        'precio_unitario': precio_dec
                    })

                # 5. Acumular actualización de stock maestro (Solo sumamos el STOCK LOTE real)
                if material_obj.id not in materiales_a_actualizar:
                    materiales_a_actualizar[material_obj.id] = material_obj.stock_actual
                materiales_a_actualizar[material_obj.id] += stock_final

            # 6. Inserción Masiva
            if detalles_a_crear:
                DetalleRecepcion.objects.bulk_create(detalles_a_crear)
                print(f"✅ Se crearon {len(detalles_a_crear)} registros en DetalleRecepcion.")

            if salidas_a_crear:
                SalidaMaterial.objects.bulk_create(salidas_a_crear)
                print(f"✅ Se crearon {len(salidas_a_crear)} registros en SalidaMaterial (Ajustes Fantasma).")

                # Vincular Detalles de Salida
                # Necesitamos recuperar los objetos recién creados de la DB para obtener sus IDs
                nros_control = [info['nro_control_entrada'] for info in salidas_detalles_info]
                nros_rim = [info['nro_rim'] for info in salidas_detalles_info]
                
                detalles_db = {d.nro_control_entrada: d for d in DetalleRecepcion.objects.filter(nro_control_entrada__in=nros_control)}
                salidas_db = {s.nro_rim: s for s in SalidaMaterial.objects.filter(nro_rim__in=nros_rim)}
                
                salidas_detalles_a_crear = []
                for info in salidas_detalles_info:
                    s_obj = salidas_db.get(info['nro_rim'])
                    d_obj = detalles_db.get(info['nro_control_entrada'])
                    if s_obj and d_obj:
                        salidas_detalles_a_crear.append(SalidaMaterialDetalle(
                            salida=s_obj,
                            detalle_recepcion=d_obj,
                            cantidad=info['cantidad'],
                            precio_unitario=info['precio_unitario'],
                            subtotal=info['cantidad'] * info['precio_unitario']
                        ))
                
                if salidas_detalles_a_crear:
                    SalidaMaterialDetalle.objects.bulk_create(salidas_detalles_a_crear)
                    print(f"✅ Se vincularon {len(salidas_detalles_a_crear)} detalles de salida (Lógica FIFO ajustada).")

            # 7. Actualización Masiva de Stock en Materiales
            for mat_id, nuevo_stock in materiales_a_actualizar.items():
                Material.objects.filter(id=mat_id).update(stock_actual=nuevo_stock)
            
            print(f"📦 Stock de {len(materiales_a_actualizar)} materiales actualizado con el stock real.")



    except Exception as e:

        print(f"💥 Error crítico durante la transacción: {e}")

        # El atomic() hará el rollback automáticamente



if __name__ == "__main__":

    migrar_saldos()