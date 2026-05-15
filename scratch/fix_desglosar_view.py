import os

path = r'd:\Usuarios\Miliandry\OneDrive\Desktop\PROYECTO_ALMACEN\Pasantias2026-Proyecto-Almacen\inventario\views.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = '''                for item in items_carrito:
                    codigo_material = item.get('material', '').split(' - ')[0].replace('[MATERIAL]', '').replace('[ACTIVOS]', '').replace('[DIRECTO AL GASTO]', '').strip()
                    
                    material_obj = Material.objects.filter(codigo=codigo_material).first()
                    activo_obj = None
                    if not material_obj:
                        activo_obj = Activo.objects.filter(codigo_activo=codigo_material).first()

                    if not material_obj and not activo_obj: 
                        continue

                    nuevo_detalle = DetalleRecepcion(
                        reporte=reporte_obj,
                        material=material_obj,
                        activo=activo_obj,
                        tipo_ingreso='Material' if material_obj else 'Activo','''

new = '''                for item in items_carrito:
                    # --- LÓGICA DIRECTO AL GASTO (EDG) ---
                    es_edg_item = item.get('es_edg') is True or str(item.get('es_edg')).lower() == 'true'
                    material_obj = None
                    activo_obj = None
                    tipo_ingreso = 'Material'

                    if es_edg_item:
                        tipo_ingreso = 'Directo al Gasto'
                        cod_edg = item.get('codigo_edg', '').strip().upper()
                        desc_edg = item.get('descripcion_edg', '').strip().upper()
                        um_edg = item.get('um_edg', '').strip().upper()
                        cargo_edg = item.get('cargo_edg', 'OPERACIONES')

                        if cod_edg and desc_edg:
                            material_obj, _ = Material.objects.get_or_create(
                                codigo=cod_edg,
                                defaults={
                                    'descripcion': desc_edg,
                                    'tipo': 'DIRECTO AL GASTO',
                                    'unidad_medida': um_edg,
                                    'cargo': cargo_edg,
                                    'stock_actual': 0
                                }
                            )
                    else:
                        codigo_material = item.get('material', '').split(' - ')[0].replace('[MATERIAL]', '').replace('[ACTIVOS]', '').replace('[DIRECTO AL GASTO]', '').strip()
                        material_obj = Material.objects.filter(codigo=codigo_material).first()
                        if not material_obj:
                            activo_obj = Activo.objects.filter(codigo_activo=codigo_material).first()
                        tipo_ingreso = 'Material' if material_obj else 'Activo'

                    if not material_obj and not activo_obj: 
                        continue

                    nuevo_detalle = DetalleRecepcion(
                        reporte=reporte_obj,
                        material=material_obj,
                        activo=activo_obj,
                        tipo_ingreso=tipo_ingreso,'''

content = content.replace(old, new)
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
