import os
from decimal import Decimal

path = r'd:\Usuarios\Miliandry\OneDrive\Desktop\PROYECTO_ALMACEN\Pasantias2026-Proyecto-Almacen\inventario\views.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update crear_recepcion
old_crear = '''        if form.is_valid() and items_carrito:
            with transaction.atomic():
                reporte = form.save()

                for item in items_carrito:'''

new_crear = '''        # Lógica de detección de ítems (JSON o Arrays directos)
        codigos_edg = request.POST.getlist('codigo_edg[]')
        
        if form.is_valid() and (items_carrito or codigos_edg):
            with transaction.atomic():
                reporte = form.save()

                # A. Procesar ítems desde el Carrito (JSON)
                for item in items_carrito:'''

content = content.replace(old_crear, new_crear)

# 2. Add the EDG Array loop to crear_recepcion
old_crear_end = '''                    detalle._tipo_entrada_manual = 'DIRECTO AL GASTO' if es_edg else item.get('tipo_entrada')
                    detalle.save()
            return redirect('lista_entradas')'''

new_crear_end = '''                    detalle._tipo_entrada_manual = 'DIRECTO AL GASTO' if es_edg else item.get('tipo_entrada')
                    detalle.save()

                # B. Procesar ítems desde Arrays Directos (POST dinámico EDG)
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

                        detalle = DetalleRecepcion(
                            reporte=reporte,
                            material=material_edg,
                            tipo_ingreso='Directo al Gasto',
                            nro_odc=odc.strip().upper(),
                            fecha_recepcion=reporte.fecha_recepcion,
                            cantidad_recibida=Decimal(cant or '0'),
                            precio_unitario=Decimal(precio or '0'),
                            nro_nota_entrega=nota.strip().upper()
                        )
                        detalle._tipo_entrada_manual = 'DIRECTO AL GASTO'
                        detalle.save()
            return redirect('lista_entradas')'''

content = content.replace(old_crear_end, new_crear_end)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
