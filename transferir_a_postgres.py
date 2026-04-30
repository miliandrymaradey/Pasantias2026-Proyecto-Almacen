"""
╔══════════════════════════════════════════════════════════════════╗
║   SCRIPT DE TRANSFERENCIA: SQLite  ──►  Supabase (PostgreSQL)    ║
║   Sistema WMS Perforosven                                        ║
║                                                                  ║
║   INSTRUCCIONES DE USO:                                          ║
║   Paso 1: Asegúrate de que tu .env apunte a SQLITE (comenta    ║
║            DB_NAME para activar el fallback a SQLite)            ║
║   Paso 2: Ejecuta: python transferir_a_postgres.py              ║
║   Paso 3: El script genera: backup_sqlite.json (el export)      ║
║   Paso 4: Activa tu .env con las credenciales de Supabase        ║
║   Paso 5: Ejecuta: python manage.py migrate                      ║
║   Paso 6: Ejecuta: python transferir_a_postgres.py --cargar     ║
║                                                                  ║
║   ⚠️  USA bulk_create() INTENCIONALMENTE para NO detonar         ║
║       los save() de los modelos y evitar doble conteo de stock   ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import django
import argparse
from decimal import Decimal
from pathlib import Path

# Fix encoding para la consola de Windows (evita UnicodeEncodeError con emojis/simbolos)
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# ─── Configuración del entorno Django ───────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_wms.settings')
django.setup()

# ─── Importaciones de modelos ────────────────────────────────────────────────
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from inventario.models import (
    Material,
    ReporteRecepcion,
    DetalleRecepcion,
    GuiaTraslado,
    SalidaMaterial,
    SalidaMaterialDetalle,
    PresupuestoAnual,
    CentroCosto,
)

ARCHIVO_BACKUP = BASE_DIR / "backup_sqlite.json"


# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 1: EXPORTAR DATOS DESDE SQLITE
# ═══════════════════════════════════════════════════════════════════════════════

def exportar_sqlite():
    """
    Lee todos los datos de la BD actual (SQLite) y los guarda en un
    archivo JSON (backup_sqlite.json). NO modifica ningún dato.
    """
    print("\n" + "═"*60)
    print("  EXPORTANDO DATOS DESDE SQLITE...")
    print("═"*60)
    
    datos = {}

    # ── 1. Usuarios ──────────────────────────────────────────────────────────
    print("  → Exportando Usuarios...")
    datos['usuarios'] = []
    for u in User.objects.all():
        datos['usuarios'].append({
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'first_name': u.first_name,
            'last_name': u.last_name,
            'is_staff': u.is_staff,
            'is_active': u.is_active,
            'is_superuser': u.is_superuser,
            'password': u.password,  # Hash incluido (no es texto plano)
            'date_joined': u.date_joined.isoformat(),
            'last_login': u.last_login.isoformat() if u.last_login else None,
        })
    print(f"     ✓ {len(datos['usuarios'])} usuarios encontrados")

    # ── 2. Materiales (Registro Maestro) ─────────────────────────────────────
    print("  → Exportando Materiales...")
    datos['materiales'] = list(
        Material.objects.values(
            'id', 'codigo', 'descripcion', 'tipo', 'cargo',
            'nro_parte', 'unidad_medida', 'ubicacion', 'stock_actual'
        )
    )
    # Convertir Decimal a string para JSON
    for m in datos['materiales']:
        m['stock_actual'] = str(m['stock_actual'])
    print(f"     ✓ {len(datos['materiales'])} materiales encontrados")

    # ── 3. Reportes de Recepción ─────────────────────────────────────────────
    print("  → Exportando Reportes de Recepción (RP)...")
    datos['reportes'] = []
    for r in ReporteRecepcion.objects.all():
        datos['reportes'].append({
            'id': r.id,
            'nro_reporte': r.nro_reporte,
            'fecha_recepcion': r.fecha_recepcion.isoformat(),
            'descripcion': r.descripcion,
            'estado': r.estado,
        })
    print(f"     ✓ {len(datos['reportes'])} reportes encontrados")

    # ── 4. Detalles de Recepción (Entradas EM) ───────────────────────────────
    print("  → Exportando Detalles de Recepción (EM/EA/EDG)...")
    datos['detalles'] = []
    for d in DetalleRecepcion.objects.all():
        datos['detalles'].append({
            'id': d.id,
            'reporte_id': d.reporte_id,
            'material_id': d.material_id,
            'descripcion_entrada': d.descripcion_entrada,
            'fecha_recepcion': d.fecha_recepcion.isoformat(),
            'nro_rq': d.nro_rq,
            'departamento': d.departamento,
            'nro_control_entrada': d.nro_control_entrada,
            'nro_odc': d.nro_odc,
            'nro_nota_entrega': d.nro_nota_entrega,
            'proveedor': d.proveedor,
            'cantidad_solicitada': str(d.cantidad_solicitada),
            'cantidad_recibida': str(d.cantidad_recibida),
            'precio_unitario': str(d.precio_unitario) if d.precio_unitario else None,
            'moneda': d.moneda,
            'eta': d.eta.isoformat() if d.eta else None,
            'fecha_firma_odc': d.fecha_firma_odc.isoformat() if d.fecha_firma_odc else None,
            'volumen_carpeta': d.volumen_carpeta,
            'es_saldo_inicial': d.es_saldo_inicial,
            'observaciones': d.observaciones,
        })
    print(f"     ✓ {len(datos['detalles'])} entradas encontradas")

    # ── 5. Guías de Traslado ──────────────────────────────────────────────────
    print("  → Exportando Guías de Traslado...")
    datos['guias'] = []
    for g in GuiaTraslado.objects.all():
        datos['guias'].append({
            'id': g.id,
            'nro_guia': g.nro_guia,
            'fecha': g.fecha.isoformat(),
            'hora': g.hora.strftime('%H:%M:%S'),
            'taladro_destino': g.taladro_destino,
            'direccion': g.direccion,
            'ciudad': g.ciudad,
            'conductor': g.conductor,
            'ci_conductor': g.ci_conductor,
            'vehiculo': g.vehiculo,
            'color': g.color,
            'placa': g.placa,
            'marca_modelo': g.marca_modelo,
            'observaciones': g.observaciones,
            'nombre_entregado': g.nombre_entregado,
            'nombre_aprobador': g.nombre_aprobador,
        })
    print(f"     ✓ {len(datos['guias'])} guías encontradas")

    # ── 6. Salidas de Material (RIM) ─────────────────────────────────────────
    print("  → Exportando Salidas (RIM)...")
    datos['salidas'] = []
    for s in SalidaMaterial.objects.all():
        datos['salidas'].append({
            'id': s.id,
            'guia_id': s.guia_id,
            'material_id': s.material_id,
            'fecha_despacho': s.fecha_despacho.isoformat(),
            'nro_rim': s.nro_rim,
            'cantidad': str(s.cantidad),
            'departamento': s.departamento,
            'centro_costo': s.centro_costo,
            'cuenta_contable': s.cuenta_contable,
            'partida_presupuestaria': s.partida_presupuestaria,
        })
    print(f"     ✓ {len(datos['salidas'])} salidas encontradas")

    # ── 7. Detalles de Salida FIFO ───────────────────────────────────────────
    print("  → Exportando Detalles FIFO...")
    datos['salida_detalles'] = []
    for sd in SalidaMaterialDetalle.objects.all():
        datos['salida_detalles'].append({
            'id': sd.id,
            'salida_id': sd.salida_id,
            'detalle_recepcion_id': sd.detalle_recepcion_id,
            'cantidad': str(sd.cantidad),
            'precio_unitario': str(sd.precio_unitario),
            'subtotal': str(sd.subtotal),
        })
    print(f"     ✓ {len(datos['salida_detalles'])} detalles FIFO encontrados")

    # ── 8. Presupuestos Anuales ───────────────────────────────────────────────
    print("  → Exportando Partidas Presupuestarias...")
    datos['presupuestos'] = list(
        PresupuestoAnual.objects.values(
            'id', 'anio', 'departamento', 'cuenta_contable',
            'descripcion_cuenta', 'partida'
        )
    )
    print(f"     ✓ {len(datos['presupuestos'])} partidas encontradas")

    # ── 9. Centros de Costo ───────────────────────────────────────────────────
    print("  → Exportando Centros de Costo...")
    datos['centros_costo'] = list(
        CentroCosto.objects.values('id', 'nombre', 'descripcion')
    )
    print(f"     ✓ {len(datos['centros_costo'])} centros de costo encontrados")

    # ── Guardar el archivo ───────────────────────────────────────────────────
    with open(ARCHIVO_BACKUP, 'w', encoding='utf-8') as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)

    print(f"\n  ✅ EXPORTACIÓN COMPLETA → {ARCHIVO_BACKUP}")
    print("═"*60)
    print("  PRÓXIMOS PASOS:")
    print("  1. Activa las credenciales de Supabase en tu .env")
    print("  2. Ejecuta: python manage.py migrate")
    print("  3. Ejecuta: python transferir_a_postgres.py --cargar")
    print("═"*60 + "\n")


# ═══════════════════════════════════════════════════════════════════════════════
#  PASO 2: CARGAR DATOS EN POSTGRESQL (SUPABASE)
# ═══════════════════════════════════════════════════════════════════════════════

def cargar_postgres():
    """
    Lee el backup_sqlite.json y carga todos los datos en PostgreSQL.
    Usa bulk_create() para EVITAR detonar los save() de los modelos
    y así prevenir el doble conteo de stock.
    """
    if not ARCHIVO_BACKUP.exists():
        print(f"\n  ❌ ERROR: No se encontró el archivo {ARCHIVO_BACKUP}")
        print("     Primero debes exportar con: python transferir_a_postgres.py")
        sys.exit(1)

    print("\n" + "═"*60)
    print("  CARGANDO DATOS EN POSTGRESQL (SUPABASE)...")
    print("═"*60)

    with open(ARCHIVO_BACKUP, 'r', encoding='utf-8') as f:
        datos = json.load(f)

    from django.db import connection

    # ── 1. Usuarios ──────────────────────────────────────────────────────────
    print("  → Cargando Usuarios...")
    from datetime import datetime
    for u_data in datos['usuarios']:
        if not User.objects.filter(username=u_data['username']).exists():
            user = User(
                id=u_data['id'],
                username=u_data['username'],
                email=u_data['email'],
                first_name=u_data['first_name'],
                last_name=u_data['last_name'],
                is_staff=u_data['is_staff'],
                is_active=u_data['is_active'],
                is_superuser=u_data['is_superuser'],
                password=u_data['password'],
            )
            # Usamos save() para usuarios porque no tienen lógica de inventario
            user.save(force_insert=True)
    # Resincronizar la secuencia de IDs en PostgreSQL
    _resetear_secuencia('auth_user', datos['usuarios'])
    print(f"     ✓ {len(datos['usuarios'])} usuarios cargados")

    # ── 2. Materiales ─────────────────────────────────────────────────────────
    print("  → Cargando Materiales...")
    materiales = [
        Material(
            id=m['id'],
            codigo=m['codigo'],
            descripcion=m['descripcion'],
            tipo=m['tipo'],
            cargo=m['cargo'],
            nro_parte=m['nro_parte'],
            unidad_medida=m['unidad_medida'],
            ubicacion=m['ubicacion'],
            stock_actual=Decimal(m['stock_actual']),  # Stock tal cual (fuente de verdad)
        )
        for m in datos['materiales']
    ]
    # ⚠️ bulk_create: NO dispara save(), copia el stock_actual exacto
    Material.objects.bulk_create(materiales, ignore_conflicts=True)
    _resetear_secuencia('inventario_material', datos['materiales'])
    print(f"     ✓ {len(materiales)} materiales cargados")

    # ── 3. Reportes de Recepción ──────────────────────────────────────────────
    print("  → Cargando Reportes de Recepción (RP)...")
    from datetime import date
    reportes = [
        ReporteRecepcion(
            id=r['id'],
            nro_reporte=r['nro_reporte'],
            fecha_recepcion=date.fromisoformat(r['fecha_recepcion']),
            descripcion=r['descripcion'],
            estado=r['estado'],
        )
        for r in datos['reportes']
    ]
    # ⚠️ bulk_create: NO dispara save() (no genera correlativo duplicado)
    ReporteRecepcion.objects.bulk_create(reportes, ignore_conflicts=True)
    _resetear_secuencia('inventario_reporterecepcion', datos['reportes'])
    print(f"     ✓ {len(reportes)} reportes cargados")

    # ── 4. Detalles de Recepción (Entradas) ───────────────────────────────────
    print("  → Cargando Entradas (EM/EA/EDG)...")
    detalles = [
        DetalleRecepcion(
            id=d['id'],
            reporte_id=d['reporte_id'],
            material_id=d['material_id'],
            descripcion_entrada=t(d['descripcion_entrada'], 500),
            fecha_recepcion=date.fromisoformat(d['fecha_recepcion']),
            nro_rq=t(d['nro_rq'], 50),
            departamento=t(d['departamento'], 100),
            nro_control_entrada=t(d['nro_control_entrada'], 20),
            nro_odc=t(d['nro_odc'], 50),
            nro_nota_entrega=t(d['nro_nota_entrega'], 50),
            proveedor=t(d['proveedor'], 200),
            cantidad_solicitada=Decimal(d['cantidad_solicitada']),
            cantidad_recibida=Decimal(d['cantidad_recibida']),
            precio_unitario=Decimal(d['precio_unitario']) if d['precio_unitario'] else None,
            moneda=t(d['moneda'], 10),
            eta=date.fromisoformat(d['eta']) if d['eta'] else None,
            fecha_firma_odc=date.fromisoformat(d['fecha_firma_odc']) if d['fecha_firma_odc'] else None,
            volumen_carpeta=t(d['volumen_carpeta'], 50),
            es_saldo_inicial=d['es_saldo_inicial'],
            observaciones=t(d['observaciones'], 255),
        )
        for d in datos['detalles']
    ]
    # ⚠️ bulk_create: NO dispara save() → NO suma stock (el stock ya es correcto en Material)
    DetalleRecepcion.objects.bulk_create(detalles, ignore_conflicts=True)
    _resetear_secuencia('inventario_detalle_recepcion', datos['detalles'])
    print(f"     ✓ {len(detalles)} entradas cargadas")

    # ── 5. Guías de Traslado ──────────────────────────────────────────────────
    print("  → Cargando Guías de Traslado...")
    from datetime import time
    guias = [
        GuiaTraslado(
            id=g['id'],
            nro_guia=g['nro_guia'],
            fecha=date.fromisoformat(g['fecha']),
            hora=time.fromisoformat(g['hora']),
            taladro_destino=g['taladro_destino'],
            direccion=g['direccion'],
            ciudad=g['ciudad'],
            conductor=g['conductor'],
            ci_conductor=g['ci_conductor'],
            vehiculo=g['vehiculo'],
            color=g['color'],
            placa=g['placa'],
            marca_modelo=g['marca_modelo'],
            observaciones=g['observaciones'],
            nombre_entregado=g['nombre_entregado'],
            nombre_aprobador=g['nombre_aprobador'],
        )
        for g in datos['guias']
    ]
    # ⚠️ bulk_create: NO dispara save() → NO genera código duplicado
    GuiaTraslado.objects.bulk_create(guias, ignore_conflicts=True)
    _resetear_secuencia('inventario_guiatraslado', datos['guias'])
    print(f"     ✓ {len(guias)} guías cargadas")

    # ── 6. Salidas de Material (RIM) ──────────────────────────────────────────
    print("  → Cargando Salidas (RIM)...")
    salidas = [
        SalidaMaterial(
            id=s['id'],
            guia_id=s['guia_id'],
            material_id=s['material_id'],
            fecha_despacho=date.fromisoformat(s['fecha_despacho']),
            nro_rim=s['nro_rim'],
            cantidad=Decimal(s['cantidad']),
            departamento=s['departamento'],
            centro_costo=s['centro_costo'],
            cuenta_contable=s['cuenta_contable'],
            partida_presupuestaria=s['partida_presupuestaria'],
        )
        for s in datos['salidas']
    ]
    # ⚠️ bulk_create: NO dispara save() → NO descuenta stock (ya está descontado)
    SalidaMaterial.objects.bulk_create(salidas, ignore_conflicts=True)
    _resetear_secuencia('inventario_salidamaterial', datos['salidas'])
    print(f"     ✓ {len(salidas)} salidas cargadas")

    # ── 7. Detalles FIFO ──────────────────────────────────────────────────────
    print("  → Cargando Detalles FIFO...")
    salida_detalles = [
        SalidaMaterialDetalle(
            id=sd['id'],
            salida_id=sd['salida_id'],
            detalle_recepcion_id=sd['detalle_recepcion_id'],
            cantidad=Decimal(sd['cantidad']),
            precio_unitario=Decimal(sd['precio_unitario']),
            subtotal=Decimal(sd['subtotal']),
        )
        for sd in datos['salida_detalles']
    ]
    SalidaMaterialDetalle.objects.bulk_create(salida_detalles, ignore_conflicts=True)
    _resetear_secuencia('inventario_salidamaterialdetalle', datos['salida_detalles'])
    print(f"     ✓ {len(salida_detalles)} detalles FIFO cargados")

    # ── 8. Presupuestos Anuales ───────────────────────────────────────────────
    print("  → Cargando Partidas Presupuestarias...")
    presupuestos = [
        PresupuestoAnual(
            id=p['id'],
            anio=p['anio'],
            departamento=p['departamento'],
            cuenta_contable=p['cuenta_contable'],
            descripcion_cuenta=p['descripcion_cuenta'],
            partida=p['partida'],
        )
        for p in datos['presupuestos']
    ]
    PresupuestoAnual.objects.bulk_create(presupuestos, ignore_conflicts=True)
    _resetear_secuencia('inventario_presupuestoanual', datos['presupuestos'])
    print(f"     ✓ {len(presupuestos)} partidas cargadas")

    # ── 9. Centros de Costo ───────────────────────────────────────────────────
    print("  → Cargando Centros de Costo...")
    centros = [
        CentroCosto(
            id=cc['id'],
            nombre=cc['nombre'],
            descripcion=cc['descripcion'],
        )
        for cc in datos['centros_costo']
    ]
    CentroCosto.objects.bulk_create(centros, ignore_conflicts=True)
    _resetear_secuencia('inventario_centrocosto', datos['centros_costo'])
    print(f"     ✓ {len(centros)} centros de costo cargados")

    print("\n  ✅ TRANSFERENCIA COMPLETA — Todos los datos están en Supabase")
    print("═"*60)
    print("  VERIFICACIÓN RECOMENDADA:")
    print(f"  • Materiales:      {Material.objects.count()} registros")
    print(f"  • Entradas (EM):   {DetalleRecepcion.objects.count()} registros")
    print(f"  • Salidas (RIM):   {SalidaMaterial.objects.count()} registros")
    print(f"  • Guías:           {GuiaTraslado.objects.count()} registros")
    print(f"  • Usuarios:        {User.objects.count()} registros")
    print("═"*60 + "\n")


def t(valor, limite):
    """
    Trunca un valor de texto al límite dado.
    PostgreSQL valida estrictamente el max_length de CharField; SQLite no.
    Esta función previene el error 'value too long for type character varying'.
    """
    if valor is None:
        return valor
    return str(valor)[:limite]


def _resetear_secuencia(nombre_tabla, registros):
    """
    PostgreSQL usa secuencias para los IDs auto-incrementales.
    Después de un bulk_create con IDs manuales, hay que resetear
    la secuencia para que el próximo INSERT use el ID correcto.
    """
    if not registros:
        return
    from django.db import connection
    max_id = max(r['id'] for r in registros)
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT setval(pg_get_serial_sequence('\"{nombre_tabla}\"', 'id'), %s, true);",
                [max_id]
            )
    except Exception as e:
        # Si falla (ej. en SQLite durante la exportación), ignorar silenciosamente
        pass


# ═══════════════════════════════════════════════════════════════════════════════
#  PUNTO DE ENTRADA
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Herramienta de transferencia SQLite → Supabase (PostgreSQL)'
    )
    parser.add_argument(
        '--cargar',
        action='store_true',
        help='Carga el backup_sqlite.json en la BD actual (PostgreSQL/Supabase)'
    )
    args = parser.parse_args()

    if args.cargar:
        cargar_postgres()
    else:
        exportar_sqlite()
