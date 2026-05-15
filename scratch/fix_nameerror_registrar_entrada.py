import os

path = r'd:\Usuarios\Miliandry\OneDrive\Desktop\PROYECTO_ALMACEN\Pasantias2026-Proyecto-Almacen\inventario\views.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

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

        # --- LÓGICA DE CAPTURA PARA EDG (Arrays directos) ---
        codigos_edg = request.POST.getlist('codigo_edg[]')

        if items_carrito or codigos_edg:
            with transaction.atomic():
                reporte_id = request.POST.get('reporte_id')
                reporte_obj = None
                if reporte_id:
                    reporte_obj = ReporteRecepcion.objects.filter(id=reporte_id).first()

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
                        raise ValidationError(f"Error: La ODC '{nro_odc_item}' no cumple el formato nuevo ni existe en el historico.")

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

                        # Intentar buscar reporte asociado a la ODC
                        rep_item = reporte_obj
                        if not rep_item and odc:
                            sibling = DetalleRecepcion.objects.filter(nro_odc=odc.strip().upper(), reporte__isnull=False).first()
                            if sibling:
                                rep_item = sibling.reporte

                        detalle = DetalleRecepcion(
                            reporte=rep_item,
                            gasto_directo=gd_obj,
                            tipo_ingreso='Directo al Gasto',
                            nro_odc=odc.strip().upper(),
                            fecha_recepcion=timezone.now().date(),
                            cantidad_recibida=Decimal(cant or '0'),
                            precio_unitario=Decimal(precio or '0'),
                            nro_nota_entrega=nota.strip().upper()
                        )
                        detalle._tipo_entrada_manual = 'DIRECTO AL GASTO'
                        detalle.save()

            return redirect('lista_entradas')"""

def replace_block(content, start_marker, end_marker, new_block):
    if start_marker in content and end_marker in content:
        # Buscamos la última ocurrencia del end_marker ANTES de la siguiente función o final
        # Pero aquí registrar_entrada termina con return render(...)
        # El marker original termina con return redirect('lista_entradas') para el bloque POST
        pre = content.split(start_marker)[0]
        post = content.split(start_marker)[1].split("return render(request, 'inventario/registrar_entrada.html', contexto)")[1]
        
        # Necesitamos mantener el resto de la función (el contexto y render)
        middle = """
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
        
        return pre + new_block + middle + post
    return content

content = replace_block(content, "def registrar_entrada(request):", "return render(request, 'inventario/registrar_entrada.html', contexto)", registrar_entrada_new)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
