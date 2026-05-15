import os

path = r'd:\Usuarios\Miliandry\OneDrive\Desktop\PROYECTO_ALMACEN\Pasantias2026-Proyecto-Almacen\inventario\views.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. ACTUALIZAR crear_recepcion (Línea 331)
crear_recepcion_new = """def crear_recepcion(request):
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

        # Lógica de detección de ítems (Arrays directos POST para EDG)
        codigos_edg = request.POST.getlist('codigo_edg[]')
        
        if form.is_valid() and (items_carrito or codigos_edg):
            with transaction.atomic():
                reporte = form.save()

                # A. Procesar ítems desde el Carrito (JSON)
                for item in items_carrito:
                    tipo_ingreso_raw = item.get('tipo_entrada', 'MATERIAL')
                    mapeo_tipos = {
                        'MATERIAL': 'Material',
                        'ACTIVOS': 'Activo',
                        'DIRECTO AL GASTO': 'Directo al Gasto'
                    }
                    tipo_ingreso = mapeo_tipos.get(tipo_ingreso_raw, 'Material')
                    
                    material_obj = None
                    activo_obj = None
                    gasto_directo_obj = None
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
                                gasto_directo_obj, _ = GastoDirecto.objects.get_or_create(
                                    codigo_dg=cod_edg,
                                    defaults={
                                        'descripcion': desc_edg,
                                        'unidad_medida_dg': um_edg,
                                        'cargo_dg': cargo_edg,
                                        'stock': 0 # Stock pasajero
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
                        gasto_directo=gasto_directo_obj,
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
                        
                        gd_obj, _ = GastoDirecto.objects.get_or_create(
                            codigo_dg=cod.strip().upper(),
                            defaults={
                                'descripcion': desc.strip().upper(),
                                'unidad_medida_dg': um.strip().upper(),
                                'cargo_dg': cargo.strip().upper(),
                                'stock': 0
                            }
                        )

                        detalle = DetalleRecepcion(
                            reporte=reporte,
                            gasto_directo=gd_obj,
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

# 2. ACTUALIZAR registrar_entrada (Línea 423)
registrar_entrada_new = """def registrar_entrada(request):
    from django.db import transaction
    import json
    from decimal import Decimal

    if request.method == 'POST':
        carrito_json = request.POST.get('carrito_datos', '[]')
        
        try:
            items_carrito = json.loads(carrito_json)
        except json.JSONDecodeError:
            items_carrito = []

        if items_carrito:
            with transaction.atomic():
                reporte_id = request.POST.get('reporte_id')
                reporte_obj = None
                if reporte_id:
                    reporte_obj = ReporteRecepcion.objects.filter(id=reporte_id).first()

                for item in items_carrito:
                    tipo_ingreso_raw = item.get('tipo_entrada', 'MATERIAL')
                    mapeo_tipos = {
                        'MATERIAL': 'Material',
                        'ACTIVOS': 'Activo',
                        'DIRECTO AL GASTO': 'Directo al Gasto'
                    }
                    tipo_ingreso = mapeo_tipos.get(tipo_ingreso_raw, 'Material')
                    
                    material_obj = None
                    activo_obj = None
                    gasto_directo_obj = None
                    cant_recibida = Decimal(item.get('cantidad_recibida') or '0')

                    if tipo_ingreso == 'Directo al Gasto':
                        cod_edg = item.get('codigo_edg', '').strip().upper()
                        desc_edg = item.get('descripcion_edg', '').strip().upper()
                        um_edg = item.get('um_edg', '').strip().upper()
                        cargo_edg = item.get('cargo_edg', 'OPERACIONES')

                        if cod_edg and desc_edg:
                            gasto_directo_obj, _ = GastoDirecto.objects.get_or_create(
                                codigo_dg=cod_edg,
                                defaults={
                                    'descripcion': desc_edg,
                                    'unidad_medida_dg': um_edg,
                                    'cargo_dg': cargo_edg,
                                    'stock': 0 # Stock pasajero
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

                    rep_final = reporte_obj
                    if rep_final is None:
                        nro_odc_item = item.get('nro_odc', '').strip()
                        nro_nota_item = item.get('nro_nota_entrega', '').strip()
                        
                        if nro_odc_item and nro_nota_item:
                            sibling = DetalleRecepcion.objects.filter(
                                nro_odc=nro_odc_item,
                                nro_nota_entrega=nro_nota_item,
                                reporte__isnull=False
                            ).select_related('reporte').first()
                            if sibling:
                                rep_final = sibling.reporte
                        elif nro_odc_item:
                            sibling = DetalleRecepcion.objects.filter(
                                nro_odc=nro_odc_item,
                                reporte__isnull=False
                            ).select_related('reporte').first()
                            if sibling:
                                rep_final = sibling.reporte

                    fecha_entrada_str = item.get('fecha_entrada')
                    import datetime as dt
                    if fecha_entrada_str:
                        try:
                            fecha_para_codigo = dt.date.fromisoformat(fecha_entrada_str)
                        except ValueError:
                            fecha_para_codigo = timezone.now().date()
                    else:
                        fecha_para_codigo = timezone.now().date()

                    import re
                    patron_odc = r'^PRSV-\\d{4}-\\d{10}$'
                    nro_odc_item = item.get('nro_odc', '').strip()
                    if not re.match(patron_odc, nro_odc_item) and not DetalleRecepcion.objects.filter(nro_odc=nro_odc_item).exists():
                        from django.core.exceptions import ValidationError
                        raise ValidationError(f"Error: La ODC '{nro_odc_item}' no cumple el formato nuevo ni existe en el histrico.")

                    detalle = DetalleRecepcion(
                        reporte=rep_final,
                        material=material_obj,
                        activo=activo_obj,
                        gasto_directo=gasto_directo_obj,
                        tipo_ingreso=tipo_ingreso,
                        descripcion_entrada=item.get('descripcion_entrada') or item.get('material_texto'),
                        nro_odc=nro_odc_item,
                        fecha_recepcion=fecha_para_codigo,
                        nro_rq=item.get('nro_rq'),
                        departamento=item.get('base'),
                        proveedor=item.get('proveedor'),
                        moneda=item.get('moneda', 'USD'),
                        eta=item.get('eta') or None,
                        nro_nota_entrega=item.get('nro_nota_entrega'),
                        cantidad_solicitada=Decimal(item.get('cantidad_solicitada') or '0'),
                        cantidad_recibida=cant_recibida,
                        precio_unitario=Decimal(item.get('precio_unitario') or '0'),
                        observaciones=item.get('observaciones')
                    )

                    detalle._tipo_entrada_manual = item.get('tipo_entrada')
                    detalle.save()
            return redirect('lista_entradas')
            
    form_detalle = DetalleRecepcionForm()
    odcs_existentes = list(DetalleRecepcion.objects.exclude(nro_odc__isnull=True).exclude(nro_odc__exact='').values_list('nro_odc', flat=True).distinct())
    reportes_recientes = ReporteRecepcion.objects.all().order_by('-fecha_recepcion', '-id')[:30]
    departamentos = PresupuestoAnual.objects.values_list('departamento', flat=True).distinct().order_by('departamento')

    contexto = {
        'form_detalle': form_detalle,
        'odcs_existentes': odcs_existentes,
        'reportes_recientes': reportes_recientes,
        'materiales': Material.objects.all(),
        'activos': Activo.objects.all(),
        'departamentos': departamentos,
    }
    return render(request, 'inventario/registrar_entrada.html', contexto)"""

# 3. ACTUALIZAR desglosar_entrada (Línea 1541)
desglosar_entrada_new = """def desglosar_entrada(request, detalle_id):
    monedero = get_object_or_404(DetalleRecepcion, id=detalle_id)
    
    if request.method == 'POST':
        carrito_json = request.POST.get('carrito_datos', '[]')
        try:
            items_carrito = json.loads(carrito_json)
        except:
            items_carrito = []

        # Detección de ítems por array directo (EDG)
        codigos_edg = request.POST.getlist('codigo_edg[]')

        if items_carrito or codigos_edg:
            with transaction.atomic():
                reporte_obj = ReporteRecepcion.objects.filter(estado='ABIERTO').first()
                if not reporte_obj:
                    reporte_obj = ReporteRecepcion.objects.create(estado='ABIERTO')

                for item in items_carrito:
                    es_edg_item = item.get('es_edg') is True or str(item.get('es_edg')).lower() == 'true'
                    material_obj = None
                    activo_obj = None
                    gasto_directo_obj = None
                    tipo_ingreso = 'Material'

                    if es_edg_item:
                        tipo_ingreso = 'Directo al Gasto'
                        cod_edg = item.get('codigo_edg', '').strip().upper()
                        desc_edg = item.get('descripcion_edg', '').strip().upper()
                        um_edg = item.get('um_edg', '').strip().upper()
                        cargo_edg = item.get('cargo_edg', 'OPERACIONES')

                        if cod_edg and desc_edg:
                            gd_obj, _ = GastoDirecto.objects.get_or_create(
                                codigo_dg=cod_edg,
                                defaults={
                                    'descripcion': desc_edg,
                                    'unidad_medida_dg': um_edg,
                                    'cargo_dg': cargo_edg,
                                    'stock': 0
                                }
                            )
                            gasto_directo_obj = gd_obj
                    else:
                        codigo_material = item.get('material', '').split(' - ')[0].replace('[MATERIAL]', '').replace('[ACTIVOS]', '').replace('[DIRECTO AL GASTO]', '').strip()
                        material_obj = Material.objects.filter(codigo=codigo_material).first()
                        if not material_obj:
                            activo_obj = Activo.objects.filter(codigo_activo=codigo_material).first()
                        tipo_ingreso = 'Material' if material_obj else 'Activo'

                    if not material_obj and not activo_obj and not gasto_directo_obj: 
                        continue

                    nuevo_detalle = DetalleRecepcion(
                        reporte=reporte_obj,
                        material=material_obj,
                        activo=activo_obj,
                        gasto_directo=gasto_directo_obj,
                        tipo_ingreso=tipo_ingreso,
                        nro_control_entrada=monedero.nro_control_entrada,
                        nro_rq=item.get('nro_rq') or monedero.nro_rq,
                        departamento=item.get('departamento') or monedero.departamento,
                        nro_odc=item.get('nro_odc') or monedero.nro_odc,
                        nro_nota_entrega=item.get('nro_nota_entrega') or monedero.nro_nota_entrega,
                        proveedor=item.get('proveedor') or monedero.proveedor,
                        fecha_recepcion=monedero.fecha_recepcion,
                        cantidad_solicitada=Decimal(item.get('cantidad_solicitada') or '0'),
                        cantidad_recibida=Decimal(item.get('cantidad_recibida') or '0'),
                        precio_unitario=Decimal(item.get('precio_unitario') or '0'),
                        moneda=monedero.moneda or 'USD',
                        descripcion_entrada=monedero.descripcion_entrada,
                        observaciones=monedero.observaciones
                    )
                    nuevo_detalle.save()

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

                        gd_obj, _ = GastoDirecto.objects.get_or_create(
                            codigo_dg=cod.strip().upper(),
                            defaults={
                                'descripcion': desc.strip().upper(),
                                'unidad_medida_dg': um.strip().upper(),
                                'cargo_dg': cargo.strip().upper(),
                                'stock': 0
                            }
                        )

                        nuevo_detalle = DetalleRecepcion(
                            reporte=reporte_obj,
                            gasto_directo=gd_obj,
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

                monedero.delete()
            return redirect('reportes_pendientes')"""

import re
# Reemplazar funciones
content = re.sub(r'def crear_recepcion\(request\):.*?return render\(request, \'inventario/crear_recepcion\.html\', contexto\)', crear_recepcion_new, content, flags=re.DOTALL)
content = re.sub(r'def registrar_entrada\(request\):.*?return render\(request, \'inventario/registrar_entrada\.html\', contexto\)', registrar_entrada_new, content, flags=re.DOTALL)
content = re.sub(r'def desglosar_entrada\(request, detalle_id\):.*?return redirect\(\'reportes_pendientes\'\)', desglosar_entrada_new, content, flags=re.DOTALL)

# Re-aplicar filtros de exclusión
content = content.replace("materiales_qs = Material.objects.all()", "materiales_qs = Material.objects.exclude(tipo='DIRECTO AL GASTO')")
content = content.replace("items = Material.objects.all().order_by('codigo')", "items = Material.objects.exclude(tipo='DIRECTO AL GASTO').order_by('codigo')")

# Aplicar filtros en Consumo Anual (Línea 1890 aprox)
old_consumo = """    despachos_list = SalidaMaterialDetalle.objects.exclude(
        Q(salida__nro_rim__startswith='AJUSTE-MIG') | Q(salida__departamento='MIGRACIÓN')
    ).select_related("""

new_consumo = """    despachos_list = SalidaMaterialDetalle.objects.exclude(
        Q(salida__nro_rim__startswith='AJUSTE-MIG') | 
        Q(salida__departamento='MIGRACIÓN') |
        Q(salida__material__tipo='DIRECTO AL GASTO')
    ).select_related("""

content = content.replace(old_consumo, new_consumo)

# Aplicar filtros en Exportar Consumo Anual (Línea 1983 aprox)
old_export_consumo = """    despachos = SalidaMaterialDetalle.objects.exclude(
        Q(salida__nro_rim__startswith='AJUSTE-MIG') | Q(salida__departamento='MIGRACIÓN')
    ).select_related("""

content = content.replace(old_export_consumo, new_consumo.replace("despachos_list", "despachos"))

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
