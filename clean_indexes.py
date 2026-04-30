import os, django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sistema_wms.settings')
django.setup()

from django.db import connection

queries = [
    'DROP INDEX IF EXISTS inventario_detallerecepcion_nro_control_entrada_d53cbe36;',
    'DROP INDEX IF EXISTS inventario_detallerecepcion_nro_control_entrada_d53cbe36_like;',
    'DROP INDEX IF EXISTS inventario_detallerecepcion_nro_odc_49089025;',
    'DROP INDEX IF EXISTS inventario_detallerecepcion_nro_odc_49089025_like;',
    'DROP INDEX IF EXISTS inventario_reporterecepcion_estado_f553a1ec;',
    'DROP INDEX IF EXISTS inventario_reporterecepcion_estado_f553a1ec_like;',
    'DROP INDEX IF EXISTS inventario_guiatraslado_taladro_destino_083ec0e3;',
    'DROP INDEX IF EXISTS inventario_guiatraslado_taladro_destino_083ec0e3_like;',
    'DROP INDEX IF EXISTS inventario_salidamaterial_nro_rim_77f43399;',
    'DROP INDEX IF EXISTS inventario_salidamaterial_nro_rim_77f43399_like;',
    'DROP INDEX IF EXISTS inventario_salidamaterial_departamento_d161d99e;',
    'DROP INDEX IF EXISTS inventario_salidamaterial_departamento_d161d99e_like;',
]

with connection.cursor() as cursor:
    for sql in queries:
        try:
            cursor.execute(sql)
            print('Executed:', sql)
        except Exception as e:
            pass

    try:
        cursor.execute("""
            SELECT indexname
            FROM pg_indexes
            WHERE tablename LIKE 'inventario_%'
            AND (indexname LIKE '%fecha%' OR indexname LIKE '%nro%' OR indexname LIKE '%estado%' OR indexname LIKE '%taladro%' OR indexname LIKE '%departamento%')
            AND indexname NOT LIKE '%pkey'
            AND indexname NOT LIKE '%key';
        """)
        rows = cursor.fetchall()
        for r in rows:
            cursor.execute(f'DROP INDEX IF EXISTS {r[0]};')
            print(f'Dropped dynamically {r[0]}')
    except Exception as e:
        print('Error dropping dynamically:', e)
