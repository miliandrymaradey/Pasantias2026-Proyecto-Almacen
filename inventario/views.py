from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.shortcuts import render, redirect, get_object_or_404 # <--- Agrega get_object_or_404
from .models import Material, ReporteRecepcion, DetalleRecepcion, SalidaMaterial, GuiaTraslado
from .forms import ReporteRecepcionForm, DetalleRecepcionForm, SalidaMaterialForm, GuiaTrasladoForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.utils import timezone


# Función para saber si el usuario es Operador o Jefe
def es_almacenista(user):
    return user.is_staff or user.is_superuser

# VISTA 1: El Dashboard (Gráficas y Resumen)
@login_required(login_url='login')
def dashboard(request):
    total_materiales = Material.objects.count()
    # Contamos cuántos materiales tienen stock crítico (menor a 5)
    alertas_stock = Material.objects.filter(stock_actual__lt=5).count()
    # Entradas de hoy (RP)
    entradas_hoy = ReporteRecepcion.objects.filter(fecha_recepcion=timezone.now()).count()

    contexto = {
        'total_materiales': total_materiales,
        'alertas_stock': alertas_stock,
        'entradas_hoy': entradas_hoy
    }
    return render(request, 'inventario/dashboard.html', contexto)

# VISTA 2: Registro Maestro (La tabla pura)
@login_required(login_url='login')
def lista_materiales(request):
    query = request.GET.get('buscar', '').strip()
    buscar_codigo = request.GET.get('buscar_codigo', '').strip()
    buscar_descripcion = request.GET.get('buscar_descripcion', '').strip()
    buscar_odc = request.GET.get('buscar_odc', '').strip()
    buscar_em = request.GET.get('buscar_em', '').strip()

    materiales_qs = Material.objects.all()

    if query:
        materiales_qs = materiales_qs.filter(
            Q(codigo__icontains=query) |
            Q(descripcion__icontains=query) |
            Q(detallerecepcion__nro_odc__icontains=query) |
            Q(detallerecepcion__nro_control_entrada__icontains=query)
        )

    if buscar_codigo:
        materiales_qs = materiales_qs.filter(codigo__icontains=buscar_codigo)
    if buscar_descripcion:
        materiales_qs = materiales_qs.filter(descripcion__icontains=buscar_descripcion)
    if buscar_odc:
        materiales_qs = materiales_qs.filter(detallerecepcion__nro_odc__icontains=buscar_odc)
    if buscar_em:
        materiales_qs = materiales_qs.filter(detallerecepcion__nro_control_entrada__icontains=buscar_em)

    materiales_qs = materiales_qs.order_by('codigo').prefetch_related('detallerecepcion_set').distinct()

    paginator = Paginator(materiales_qs, 50)
    page_number = request.GET.get('page')
    materiales_paginados = paginator.get_page(page_number)

    query_params = request.GET.copy()
    if 'page' in query_params:
        del query_params['page']
    querystring = query_params.urlencode()
    query_prefix = f"{querystring}&" if querystring else ''

    contexto = {
        'materiales': materiales_paginados,
        'query': query,
        'buscar_codigo': buscar_codigo,
        'buscar_descripcion': buscar_descripcion,
        'buscar_odc': buscar_odc,
        'buscar_em': buscar_em,
        'querystring': querystring,
        'query_prefix': query_prefix
    }
    return render(request, 'inventario/lista_materiales.html', contexto)

# Vista 3: Lista de Reportes de Entrada (CON BUSCADOR)
@login_required(login_url='login')
def lista_entradas(request):
    query = request.GET.get('buscar', '')
    
    # Buscamos en los Ítems (DetalleRecepcion)
    if query:
        from django.db.models import Q
        recepciones_lista = DetalleRecepcion.objects.select_related('material', 'reporte').filter(
            Q(material__codigo__icontains=query) | 
            Q(material__descripcion__icontains=query) |
            Q(nro_odc__icontains=query) |
            Q(nro_nota_entrega__icontains=query) |
            Q(proveedor__icontains=query)
        ).order_by('-fecha_recepcion', '-id')
    else:
        recepciones_lista = DetalleRecepcion.objects.select_related('material', 'reporte').all().order_by('-fecha_recepcion', '-id')
        
    # Paginación
    from django.core.paginator import Paginator
    paginator = Paginator(recepciones_lista, 50) 
    page_number = request.GET.get('page')
    recepciones_paginadas = paginator.get_page(page_number)

    # ENVIAMOS LA VARIABLE 'recepciones' AL HTML
    contexto = {'recepciones': recepciones_paginadas, 'query': query} 
    return render(request, 'inventario/lista_entradas.html', contexto)

# Vista 4: Crear Reporte (RP-00X) y carga múltiple de ítems por carrito
@login_required(login_url='login')
@user_passes_test(es_almacenista, login_url='lista_entradas') 
def crear_recepcion(request):
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

        if form.is_valid() and items_carrito:
            with transaction.atomic():
                reporte = form.save()
                
                for item in items_carrito:
                    codigo_material = item.get('material', '').split(' - ')[0].replace('[MATERIAL]', '').replace('[ACTIVOS]', '').replace('[DIRECTO AL GASTO]', '').strip()
                    try:
                        material_obj = Material.objects.get(codigo=codigo_material)
                    except Material.DoesNotExist:
                        continue # Saltamos o manejamos error
                    
                    detalle = DetalleRecepcion(
                        reporte=reporte,
                        material=material_obj,
                        nro_odc=item.get('nro_odc'),
                        fecha_recepcion=reporte.fecha_recepcion, # Heredado del reporte
                        nro_rq=item.get('nro_rq'),
                        departamento=item.get('departamento'),
                        proveedor=item.get('proveedor'),
                        moneda=item.get('moneda', 'USD'),
                        eta=item.get('eta') or None,
                        nro_nota_entrega=item.get('nro_nota_entrega'),
                        cantidad_solicitada=Decimal(item.get('cantidad_solicitada') or '0'),
                        cantidad_recibida=Decimal(item.get('cantidad_recibida') or '0'),
                        precio_unitario=Decimal(item.get('precio_unitario') or '0'),
                        observaciones=item.get('observaciones')
                    )
                    detalle.save() # Llama la lógica de autogeneración de EM/EA
                    
            return redirect('detalle_recepcion', reporte_id=reporte.id)
        else:
            # Si el carrito está vacío o el form falla, recargamos
            pass
            
    else:
        form = ReporteRecepcionForm()

    form_detalle = DetalleRecepcionForm()
    odcs_existentes = list(DetalleRecepcion.objects.exclude(nro_odc__isnull=True).exclude(nro_odc__exact='').values_list('nro_odc', flat=True).distinct())

    contexto = {
        'form': form, 
        'form_detalle': form_detalle,
        'odcs_existentes': odcs_existentes
    }
    return render(request, 'inventario/crear_recepcion.html', contexto)

# Vista 5: Llenar el Reporte con Ítems (EM26001)
@login_required(login_url='login')
def detalle_recepcion(request, reporte_id):
    reporte = get_object_or_404(ReporteRecepcion, id=reporte_id)
    
    # --- LÓGICA DEL FILTRO ---
    # Si la URL dice ?filtro=diferencias, filtramos la lista
    filtro_activo = request.GET.get('filtro')
    
    if filtro_activo == 'diferencias':
        from django.db.models import F
        # Trae solo los ítems donde lo recibido NO es igual a lo solicitado
        items = DetalleRecepcion.objects.filter(reporte=reporte).exclude(cantidad_solicitada=F('cantidad_recibida')).order_by('-id')
    else:
        # Trae todos normalmente
        items = DetalleRecepcion.objects.filter(reporte=reporte).order_by('-id')

    if request.method == 'POST':
        form = DetalleRecepcionForm(request.POST)
        if form.is_valid():
            nuevo_item = form.save(commit=False)
            nuevo_item.reporte = reporte
            nuevo_item.save()
            return redirect('detalle_recepcion', reporte_id=reporte.id)
    else:
        form = DetalleRecepcionForm()

    contexto = {
        'reporte': reporte,
        'items': items,
        'form': form,
        'filtro_activo': filtro_activo # Pasamos esto al HTML para saber si el botón está encendido
    }
    return render(request, 'inventario/detalle_recepcion.html', contexto)

# VISTA 6: Lista de Despachos (RIM)
@login_required(login_url='login')
def lista_salidas(request):
    salidas = SalidaMaterial.objects.all().order_by('-fecha_despacho', '-id')
    contexto = {'salidas': salidas}
    return render(request, 'inventario/lista_salidas.html', contexto)

# VISTA 7: Registrar un Nuevo Despacho (RIM)
@login_required(login_url='login')
@user_passes_test(es_almacenista, login_url='lista_entradas') # <--- ESCUDO NUEVO
def crear_salida(request):
    if request.method == 'POST':
        form = SalidaMaterialForm(request.POST)
        if form.is_valid():
            # Si hay stock suficiente, Django lo guarda y resta automáticamente
            form.save()
            return redirect('lista_salidas')
        # Si NO hay stock, form.is_valid() será Falso y mostrará el error en pantalla
    else:
        form = SalidaMaterialForm()

    contexto = {'form': form}
    return render(request, 'inventario/crear_salida.html', contexto)

# VISTA 8: Generar PDF de la Nota de Despacho (RIM)
@login_required(login_url='login')
def generar_pdf_salida(request, salida_id):
    # 1. Buscamos el despacho específico
    salida = get_object_or_404(SalidaMaterial, id=salida_id)
    
    # 2. Le decimos qué plantilla HTML vamos a usar para el diseño del PDF
    template_path = 'inventario/pdf_salida.html'
    context = {'salida': salida}
    
    # 3. Configuramos la respuesta del navegador para que sepa que es un PDF
    response = HttpResponse(content_type='application/pdf')
    # Si quieres que se descargue automáticamente, quita el "#" de la siguiente línea:
    # response['Content-Disposition'] = f'attachment; filename="Despacho_{salida.nro_rim}.pdf"'
    
    # 4. Renderizamos (dibujamos) el HTML y lo convertimos a PDF
    template = get_template(template_path)
    html = template.render(context)
    
    # Creamos el PDF
    pisa_status = pisa.CreatePDF(html, dest=response)
    
    if pisa_status.err:
        return HttpResponse('Tuvimos errores al generar el PDF: <pre>' + html + '</pre>')
    return response

# VISTA 9: Lista de Guías de Traslado
@login_required(login_url='login')
def lista_guias(request):
    guias = GuiaTraslado.objects.all().order_by('-fecha', '-id')
    contexto = {'guias': guias}
    return render(request, 'inventario/lista_guias.html', contexto)

# VISTA 10: Crear el encabezado de la Guía (El camión)
@login_required(login_url='login')
@user_passes_test(es_almacenista, login_url='lista_entradas') # <--- ESCUDO NUEVO
def crear_guia(request):
    if request.method == 'POST':
        form = GuiaTrasladoForm(request.POST)
        if form.is_valid():
            guia = form.save()
            # Al guardar, lo enviamos directo a la pantalla para meterle los materiales
            return redirect('detalle_guia', guia_id=guia.id) 
    else:
        form = GuiaTrasladoForm()
    return render(request, 'inventario/crear_guia.html', {'form': form})

# VISTA 11: Armar la Guía (La magia de los checkboxes)
@login_required(login_url='login')
def detalle_guia(request, guia_id):
    guia = get_object_or_404(GuiaTraslado, id=guia_id)
    
    # 1. Traemos los materiales que YA ESTÁN en este camión
    items_en_guia = SalidaMaterial.objects.filter(guia=guia)
    
    # 2. Traemos los RIMs que están "Huérfanos" (Que salieron del almacén pero no tienen guía)
    items_pendientes = SalidaMaterial.objects.filter(guia__isnull=True).order_by('-fecha_despacho')

    if request.method == 'POST':
        # Recibimos la lista de los IDs que el usuario marcó con el Checkbox (✔)
        ids_seleccionados = request.POST.getlist('rims_seleccionados')
        if ids_seleccionados:
            # Actualizamos esos RIMs en la base de datos para decirles: "Ahora pertenecen a esta Guía"
            SalidaMaterial.objects.filter(id__in=ids_seleccionados).update(guia=guia)
        
        return redirect('detalle_guia', guia_id=guia.id)

    contexto = {
        'guia': guia,
        'items_en_guia': items_en_guia,
        'items_pendientes': items_pendientes
    }
    return render(request, 'inventario/detalle_guia.html', contexto)

# ==================================================
# VISTA:12 Generar PDF de la Guía de Traslado (ALM-FORM-002)
# ==================================================
@login_required(login_url='login')
def generar_pdf_guia(request, guia_id):
    # 1. Buscamos la guía específica (El camión)
    guia = get_object_or_404(GuiaTraslado, id=guia_id)
    
    # 2. Buscamos todos los ítems (RIMs) que marcaste para subirse a esta guía
    items = SalidaMaterial.objects.filter(guia=guia)
    
    # 3. Le decimos qué plantilla de diseño usar (El formato ALM-FORM-002)
    template_path = 'inventario/alm_form_002.html'
    context = {'guia': guia, 'items': items}
    
    # 4. Preparamos el PDF
    response = HttpResponse(content_type='application/pdf')
    # response['Content-Disposition'] = f'attachment; filename="{guia.nro_guia}.pdf"'
    
    template = get_template(template_path)
    html = template.render(context)
    
    # 5. Creamos el PDF con xhtml2pdf
    pisa_status = pisa.CreatePDF(html, dest=response)
    
    if pisa_status.err:
        return HttpResponse('Tuvimos errores al generar el PDF: <pre>' + html + '</pre>')
    return response

# ==================================================
# VISTA 13: Data Procura (Historial de Entradas)
# ==================================================
@login_required(login_url='login')
def data_procura(request):
    query = request.GET.get('buscar', '').strip()
    
    # Traemos todos los detalles de recepción con su material
    items_qs = DetalleRecepcion.objects.select_related('material', 'reporte').all().order_by('-fecha_recepcion', '-id')

    if query:
        items_qs = items_qs.filter(
            Q(material__codigo__icontains=query) |
            Q(material__descripcion__icontains=query) |
            Q(nro_odc__icontains=query) |
            Q(nro_rq__icontains=query) |
            Q(proveedor__icontains=query) |
            Q(nro_nota_entrega__icontains=query)
        )

    # Paginar resultados
    paginator = Paginator(items_qs, 50)
    page_number = request.GET.get('page')
    items_paginados = paginator.get_page(page_number)

    contexto = {
        'items': items_paginados,
        'query': query
    }
    return render(request, 'inventario/data_procura.html', contexto)

# ==================================================
# VISTA 14: Reportes (Listado detallado con botones)
# ==================================================
@login_required(login_url='login')
def reportes(request):
    query = request.GET.get('buscar', '').strip()
    
    # Traemos todos los detalles de recepción con su material
    items_qs = DetalleRecepcion.objects.select_related('material', 'reporte').all().order_by('-fecha_recepcion', '-id')

    if query:
        items_qs = items_qs.filter(
            Q(material__codigo__icontains=query) |
            Q(material__descripcion__icontains=query) |
            Q(nro_odc__icontains=query) |
            Q(nro_rq__icontains=query) |
            Q(proveedor__icontains=query) |
            Q(nro_nota_entrega__icontains=query) |
            Q(departamento__icontains=query)
        )

    # Paginar resultados
    paginator = Paginator(items_qs, 50)
    page_number = request.GET.get('page')
    items_paginados = paginator.get_page(page_number)

    contexto = {
        'reportes': items_paginados,
        'query': query
    }
    return render(request, 'inventario/reportes.html', contexto)

# ==================================================
# API: Obtener datos de Material por AJAX
# ==================================================
@login_required(login_url='login')
def get_material_info(request, material_id):
    from django.http import JsonResponse
    try:
        material = Material.objects.get(id=material_id)
        data = {
            'descripcion': material.descripcion,
            'nro_parte': material.nro_parte or 'N/A',
            'unidad_medida': material.unidad_medida,
            'cargo': material.cargo
        }
        return JsonResponse(data)
    except Material.DoesNotExist:
        return JsonResponse({'error': 'Material no encontrado'}, status=404)