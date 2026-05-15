import os
from decimal import Decimal

path = r'd:\Usuarios\Miliandry\OneDrive\Desktop\PROYECTO_ALMACEN\Pasantias2026-Proyecto-Almacen\inventario\views.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update desglosar_entrada condition
old_desglosar = '''        carrito_json = request.POST.get('carrito_datos', '[]')
        try:
            items_carrito = json.loads(carrito_json)
        except:
            items_carrito = []

        if items_carrito:'''

new_desglosar = '''        carrito_json = request.POST.get('carrito_datos', '[]')
        try:
            items_carrito = json.loads(carrito_json)
        except:
            items_carrito = []

        # Detección de ítems por array directo (EDG)
        codigos_edg = request.POST.getlist('codigo_edg[]')

        if items_carrito or codigos_edg:'''

content = content.replace(old_desglosar, new_desglosar)

# 2. Add the EDG Array loop to desglosar_entrada
# I'll find where the items_carrito loop ends and add the codigos_edg loop.
# The items_carrito loop ends before monedero.delete()

old_desglosar_end = '''                    nuevo_detalle.save()
                monedero.delete()'''

new_desglosar_end = '''                    nuevo_detalle.save()

                # B. Procesar ítems desde Arrays Directos (EDG)
                if codigos_edg:
                    descripciones_edg = request.POST.getlist('descripcion_edg[]')
                    ums_edg = request.POST.getlist('um_edg[]')
                    cargos_edg = request.POST.getlist('cargo_edg[]')
                    cantidades_edg = request.POST.getlist('cantidad_edg[]')
                    precios_edg = request.POST.getlist('precio_edg[]')
                    odcs_edg = request.POST.getlist('odc_edg[]')
                    notas_edg = request.POST.getlist('nota_edg[]')

                    for cod, desc, um, cargo, cant, precio, odc, nota in zip(
                        codigos_edg, descripciones_edg, ums_edg, cargos_edg, 
                        cantidades_edg, precios_edg, odcs_edg, notas_edg
                    ):
                        if not cod or not desc: continue

                        material_edg, _ = Material.objects.get_or_create(
                            codigo=cod.strip().upper(),
                            defaults={
                                'descripcion': desc.strip().upper(),
                                'tipo': 'DIRECTO AL GASTO',
                                'unidad_medida': um.strip().upper(),
                                'cargo': cargo.strip().upper(),
                                'stock_actual': 0
                            }
                        )

                        nuevo_detalle = DetalleRecepcion(
                            reporte=reporte_obj,
                            material=material_edg,
                            tipo_ingreso='Directo al Gasto',
                            nro_control_entrada=monedero.nro_control_entrada,
                            nro_rq=monedero.nro_rq,
                            departamento=monedero.departamento,
                            nro_odc=odc.strip().upper() or monedero.nro_odc,
                            nro_nota_entrega=nota.strip().upper() or monedero.nro_nota_entrega,
                            proveedor=monedero.proveedor,
                            fecha_recepcion=monedero.fecha_recepcion,
                            cantidad_recibida=Decimal(cant or '0'),
                            precio_unitario=Decimal(precio or '0'),
                            moneda=monedero.moneda or 'USD',
                            descripcion_entrada=monedero.descripcion_entrada,
                            observaciones=monedero.observaciones
                        )
                        nuevo_detalle._tipo_entrada_manual = 'DIRECTO AL GASTO'
                        nuevo_detalle.save()

                monedero.delete()'''

content = content.replace(old_desglosar_end, new_desglosar_end)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
