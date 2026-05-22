import os
from pathlib import Path

# Cargar variables de entorno (.env) en la raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent
dotenv_path = BASE_DIR / '.env'
if dotenv_path.exists():
    from dotenv import load_dotenv
    load_dotenv(dotenv_path)

# Configurar Django antes de importar cualquier modelo
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_wms.settings')
import django
django.setup()

import pandas as pd
from decimal import Decimal
from django.db import transaction

# Importar modelos después de que Django esté configurado
from inventario.models import Material, DetalleRecepcion, SalidaMaterial, SalidaMaterialDetalle

def migrar_saldos(file_path='saldos_iniciales.xlsx'):
    """Script para la carga masiva de inventario histórico (Saldos Iniciales).
    Lee el Excel, crea materiales faltantes y registra entradas/salidas usando bulk_create.
    Todo dentro de una única transacción para garantizar rollback ante errores.
    """
    if not os.path.exists(file_path):
        print(f"Error: No se encontró el archivo '{file_path}' en la raíz.")
        return

    print(f"Iniciando migración de saldos desde: {file_path}")

    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        print(f"Error al leer el Excel: {e}")
        return

    df = df.where(pd.notnull(df), None)
    print(f"Procesando {len(df)} filas...")

    # Extraer códigos únicos del Excel para consultar de una sola vez
    codigos_excel = [str(x).strip() for x in df['CÓDIGO'].unique() if pd.notna(x)]

    # Consultar materiales existentes en la base de datos en una sola consulta
    print("Consultando materiales existentes en base de datos...")
    materiales_existentes = {m.codigo: m for m in Material.objects.filter(codigo__in=codigos_excel)}
    print(f"Encontrados {len(materiales_existentes)} materiales en la BD.")

    # Estructuras temporales
    materiales_nuevos_dict = {}     # codigo -> objeto Material
    materiales_actualizar = {}      # codigo -> nuevo stock acumulado (Decimal)
    detalles_a_crear = []
    salidas_a_crear = []
    salidas_detalles_info = []

    try:
        with transaction.atomic():
            for index, row in df.iterrows():
                codigo_mat = str(row.get('CÓDIGO', '')).strip()
                cantidad_sol = row.get('CANTIDAD', 0)
                cantidad_rec_original = row.get('CANT RECIB', 0)
                stock_lote = row.get('STOCK LOTE', None)
                precio = row.get('U.P. REAL', 0)
                nro_em = row.get('N° EM')

                # 1. Buscar o crear Material
                material_obj = materiales_existentes.get(codigo_mat)
                if not material_obj:
                    desc = str(row.get('MATERIAL / DESCRIPCIÓN', '')).strip()
                    if not desc or desc.lower() == 'nan':
                        desc = str(row.get('DESCRIPCION', f"Material Histórico {codigo_mat}")).strip()
                    desc = desc[:255]
                    cargo_row = str(row.get('CARGO', 'OPERACIONES')).strip().upper()
                    if cargo_row not in ['MANTENIMIENTO', 'OPERACIONES', 'TRANSPORTE', 'OTRO']:
                        cargo_row = 'OPERACIONES'
                    cargo_row = cargo_row[:50]
                    tipo_row = str(row.get('TIPO', 'MATERIAL')).strip().upper()
                    if tipo_row not in ['MATERIAL', 'ACTIVOS', 'DIRECTO AL GASTO']:
                        tipo_row = 'MATERIAL'
                    tipo_row = tipo_row[:20]
                    um_row = str(row.get('U.M.', row.get('UM', row.get('U/M', 'C/U')))).strip().upper()
                    if um_row == 'NAN' or not um_row:
                        um_row = 'C/U'
                    um_row = um_row[:20]
                    np_row = str(row.get('N/P', row.get('NRO_PARTE', ''))).strip()
                    if np_row.lower() == 'nan':
                        np_row = ''
                    np_row = np_row[:100]

                    if codigo_mat in materiales_nuevos_dict:
                        # Usar la última versión del material en el Excel
                        material_obj = materiales_nuevos_dict[codigo_mat]
                        material_obj.descripcion = desc
                        material_obj.cargo = cargo_row
                        material_obj.tipo = tipo_row
                        material_obj.unidad_medida = um_row
                        material_obj.nro_parte = np_row
                    else:
                        print(f"Fila {index+2}: Material '{codigo_mat}' no existe en la BD. Agregando a lote de creación...")
                        material_obj = Material(
                            codigo=codigo_mat[:50],
                            descripcion=desc,
                            tipo=tipo_row,
                            cargo=cargo_row,
                            nro_parte=np_row,
                            unidad_medida=um_row,
                            stock_actual=Decimal('0')
                        )
                        materiales_nuevos_dict[codigo_mat] = material_obj

                # 2. Determinar cantidades
                cantidad_original = Decimal(str(cantidad_rec_original)) if pd.notna(cantidad_rec_original) else Decimal('0')
                stock_final = Decimal(str(stock_lote)) if pd.notna(stock_lote) else cantidad_original
                diferencia = cantidad_original - stock_final

                # 3. Preparar DetalleRecepcion (entrada completa)
                if pd.isna(nro_em) or not str(nro_em).strip():
                    nro_control = f"HIST-{index+1:04d}"
                else:
                    nro_control = str(nro_em).strip()
                nro_control = nro_control[:20]

                # Normalizar fecha
                fecha_excel = row.get('FECHA REC.')
                if pd.isna(fecha_excel):
                    fecha_limpia = '2026-01-01'
                else:
                    fecha_str = str(fecha_excel).strip()
                    if ' ' in fecha_str:
                        fecha_str = fecha_str.split()[0]
                    meses_esp = {
                        'ene': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'abr': 'Apr',
                        'may': 'May', 'jun': 'Jun', 'jul': 'Jul', 'ago': 'Aug',
                        'sep': 'Sep', 'oct': 'Oct', 'nov': 'Nov', 'dic': 'Dec'
                    }
                    for esp, eng in meses_esp.items():
                        fecha_str = fecha_str.lower().replace(esp, eng)
                    try:
                        dt_temp = pd.to_datetime(fecha_str, errors='coerce')
                        fecha_limpia = dt_temp.strftime('%Y-%m-%d') if pd.notna(dt_temp) else '2026-01-01'
                    except Exception:
                        fecha_limpia = '2026-01-01'

                precio_dec = Decimal(str(precio)) if pd.notna(precio) else Decimal('0')

                desc_entrada_raw = row.get('MATERIAL / DESCRIPCIÓN') or f"Saldo Inicial - {material_obj.descripcion}"
                desc_entrada = str(desc_entrada_raw)[:500]
                nro_rq = str(row.get('RQ') or '')[:50]
                dept_det = str(row.get('CARGO') or 'OPERACIONES')[:100]
                nro_odc = str(row.get('NO ODC') or 'HISTORICO')[:50]
                prov_det = str(row.get('PROVEEDOR') or 'SALDO INICIAL')[:200]
                moneda_det = str(row.get('MONEDA') or 'USD')[:10]
                nota_det = str(row.get('NOTA ENTREGA') or 'N/A')[:50]
                obs_det = f"Entrada original: {cantidad_original}. Ajuste aplicado: {diferencia}. N/P: {row.get('N/P', '')}".strip()[:255]

                detalle = DetalleRecepcion(
                    material=material_obj,
                    reporte=None,
                    es_saldo_inicial=True,
                    descripcion_entrada=desc_entrada,
                    fecha_recepcion=fecha_limpia,
                    nro_rq=nro_rq,
                    departamento=dept_det,
                    nro_control_entrada=nro_control,
                    nro_odc=nro_odc,
                    proveedor=prov_det,
                    cantidad_solicitada=Decimal(str(cantidad_sol)) if pd.notna(cantidad_sol) else Decimal('0'),
                    cantidad_recibida=cantidad_original,
                    precio_unitario=precio_dec,
                    moneda=moneda_det,
                    nro_nota_entrega=nota_det,
                    observaciones=obs_det
                )
                detalles_a_crear.append(detalle)

                # 4. Ajuste fantasma (si hay diferencia positiva)
                if diferencia > 0:
                    nro_rim = f"AJUSTE-MIG-{index+1:04d}"
                    salida = SalidaMaterial(
                        nro_rim=nro_rim[:50],
                        material=material_obj,
                        departamento="MIGRACIÓN",
                        fecha_despacho=fecha_limpia,
                        cantidad=diferencia
                    )
                    salidas_a_crear.append(salida)
                    salidas_detalles_info.append({
                        'nro_rim': nro_rim,
                        'nro_control_entrada': nro_control,
                        'cantidad': diferencia,
                        'precio_unitario': precio_dec
                    })

                # 5. Acumular stock real del lote usando el código
                if codigo_mat not in materiales_actualizar:
                    materiales_actualizar[codigo_mat] = material_obj.stock_actual
                materiales_actualizar[codigo_mat] += stock_final

            # 6. Persistir usando bulk_create con ignore_conflicts=True y batch_size=200 para evitar timeouts de BD
            materiales_nuevos = list(materiales_nuevos_dict.values())
            if materiales_nuevos:
                Material.objects.bulk_create(materiales_nuevos, batch_size=200, ignore_conflicts=True)
                
                # Recuperar los IDs reales de la base de datos para mapearlos correctamente
                codigos_nuevos = [m.codigo for m in materiales_nuevos]
                materiales_db = {m.codigo: m.id for m in Material.objects.filter(codigo__in=codigos_nuevos)}
                
                creados_count = 0
                ignorados_count = 0
                for nuevo in materiales_nuevos:
                    db_id = materiales_db.get(nuevo.codigo)
                    if db_id:
                        nuevo.id = db_id
                        creados_count += 1
                    else:
                        ignorados_count += 1
                
                print(f"Se procesaron {len(materiales_nuevos)} materiales nuevos: {creados_count} creados, {ignorados_count} ignorados por duplicación.")
                
                # Asignar explícitamente los IDs de los materiales a los detalles y salidas antes de crearlos
                for d in detalles_a_crear:
                    if d.material and d.material.codigo in materiales_db:
                        d.material_id = materiales_db[d.material.codigo]
                
                for s in salidas_a_crear:
                    if s.material and s.material.codigo in materiales_db:
                        s.material_id = materiales_db[s.material.codigo]

            if detalles_a_crear:
                DetalleRecepcion.objects.bulk_create(detalles_a_crear, batch_size=200, ignore_conflicts=True)
                print(f"Se crearon {len(detalles_a_crear)} registros en DetalleRecepcion.")

            if salidas_a_crear:
                SalidaMaterial.objects.bulk_create(salidas_a_crear, batch_size=200, ignore_conflicts=True)
                print(f"Se crearon {len(salidas_a_crear)} registros en SalidaMaterial (Ajustes fantasma).")

                # Vincular Detalles de Salida a sus DetallesRecepcion
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
                    SalidaMaterialDetalle.objects.bulk_create(salidas_detalles_a_crear, batch_size=200, ignore_conflicts=True)
                    print(f"Se vincularon {len(salidas_detalles_a_crear)} detalles de salida.")

            # 7. Actualizar stock de Materiales en la BD de forma masiva (para evitar cortes de red y timeouts)
            codigos_a_actualizar = list(materiales_actualizar.keys())
            materiales_para_actualizar_db = Material.objects.filter(codigo__in=codigos_a_actualizar)
            
            materiales_upd = []
            for m in materiales_para_actualizar_db:
                nuevo_stock = materiales_actualizar.get(m.codigo)
                if nuevo_stock is not None:
                    m.stock_actual = nuevo_stock
                    materiales_upd.append(m)
            
            if materiales_upd:
                Material.objects.bulk_update(materiales_upd, ['stock_actual'], batch_size=200)
            print(f"Stock de {len(materiales_upd)} materiales actualizado masivamente en base de datos.")

    except Exception as e:
        print(f"Error crítico durante la transacción: {e}")
        # El atomic garantiza rollback automático

if __name__ == "__main__":
    migrar_saldos()