import os

path = r'd:\Usuarios\Miliandry\OneDrive\Desktop\PROYECTO_ALMACEN\Pasantias2026-Proyecto-Almacen\inventario\views.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

new_func_body = """def crear_recepcion(request):
    from django.db import transaction
    import json
    from decimal import Decimal

    if request.method == 'POST':
        form = ReporteRecepcionForm(request.POST)
        carrito_json = request.POST.get('carrito_datos', '[]')

        try:
            items_carrito = json.loads(carrito_json)
        except json.JSONDecodeError:
            items_carrito = []

        # Lógica de detección de ítems (JSON o Arrays directos)
        codigos_edg = request.POST.getlist('codigo_edg[]')
        
        if form.is_valid() and (items_carrito or codigos_edg):
            with transaction.atomic():
                reporte = form.save()

                # A. Procesar ítems desde el Carrito (JSON)
                for item in items_carrito:
                    # --- ASOCIACIÓN Y METADATA ---
                    tipo_ingreso_raw = item.get('tipo_entrada', 'MATERIAL')
                    mapeo_tipos = {
                        'MATERIAL': 'Material',
                        'ACTIVOS': 'Activo',
                        'DIRECTO AL GASTO': 'Directo al Gasto'
                    }
                    tipo_ingreso = mapeo_tipos.get(tipo_ingreso_raw, 'Material')
                    
                    material_obj = None
                    activo_obj = None
                    cant_recibida = Decimal(item.get('cantidad_recibida') or '0')

                    # --- LÓGICA DIRECTO AL GASTO (EDG) ---
                    es_edg = item.get('es_edg') is True or str(item.get('es_edg')).lower() == 'true'
                    requiere_rp = item.get('requiere_rp', 'si') 

                    if es_edg:
                        tipo_ingreso = 'Directo al Gasto'
                        if requiere_rp == 'si':
                            material_obj = None
                        else:
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
                    elif tipo_ingreso == 'Material':
                        material_id = item.get('material_id')
                        if material_id:
                            material_obj = Material.objects.get(id=material_id)
                        else:
                            codigo_material = item.get('material', '').split(' - ')[0].replace('[MATERIAL]', '').replace('[ACTIVOS]', '').replace('[DIRECTO AL GASTO]', '').strip()
                            material_obj = Material.objects.filter(codigo=codigo_material).first()
                    elif tipo_ingreso == 'Activo':
                        activo_id = item.get('activo_id')
                        if activo_id:
                            activo_obj = Activo.objects.get(id=activo_id)

                    import re
                    patron_odc = r'^PRSV-\\d{4}-\\d{10}$'
                    nro_odc_item = item.get('nro_odc', '').strip()
                    if not re.match(patron_odc, nro_odc_item) and not DetalleRecepcion.objects.filter(nro_odc=nro_odc_item).exists():
                        from django.core.exceptions import ValidationError
                        raise ValidationError(f"Error: La ODC '{nro_odc_item}' no cumple el formato nuevo ni existe en el histórico.")

                    detalle = DetalleRecepcion(
                        reporte=reporte,
                        material=material_obj,
                        activo=activo_obj,
                        tipo_ingreso=tipo_ingreso,
                        nro_odc=nro_odc_item,
                        fecha_recepcion=reporte.fecha_recepcion,
                        nro_rq=item.get('nro_rq'),
                        departamento=item.get('departamento'),
                        proveedor=item.get('proveedor'),
                        moneda=item.get('moneda', 'USD'),
                        eta=item.get('eta') or None,
                        nro_nota_entrega=item.get('nro_nota_entrega'),
                        cantidad_solicitada=Decimal(item.get('cantidad_solicitada') or '0'),
                        cantidad_recibida=cant_recibida,
                        precio_unitario=Decimal(item.get('precio_unitario') or '0'),
                        observaciones=item.get('observaciones')
                    )
                    detalle._tipo_entrada_manual = 'DIRECTO AL GASTO' if es_edg else item.get('tipo_entrada')
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

            return redirect('lista_entradas')
        else:
            form = ReporteRecepcionForm(request.POST)
    else:
        form = ReporteRecepcionForm()

    form_detalle = DetalleRecepcionForm()
    odcs_existentes = list(DetalleRecepcion.objects.exclude(nro_odc__isnull=True).exclude(nro_odc__exact='').values_list('nro_odc', flat=True).distinct())

    contexto = {
        'form': form,
        'form_detalle': form_detalle,
        'odcs_existentes': odcs_existentes,
        'materiales': Material.objects.all(),
        'activos': Activo.objects.all(),
    }
    return render(request, 'inventario/crear_recepcion.html', contexto)"""

import re
start_marker = "def crear_recepcion(request):"
end_marker = "return render(request, 'inventario/crear_recepcion.html', contexto)"

# Simple string split and join
if start_marker in content and end_marker in content:
    pre = content.split(start_marker)[0]
    post = content.split(end_marker)[1]
    new_content = pre + new_func_body + post
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("Success")
else:
    print("Markers not found")
