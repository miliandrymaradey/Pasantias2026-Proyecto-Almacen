from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.shortcuts import render, redirect, get_object_or_404 # <--- Agrega get_object_or_404
from .models import Material, ReporteRecepcion, DetalleRecepcion, SalidaMaterial, GuiaTraslado, PresupuestoAnual
from .forms import ReporteRecepcionForm, DetalleRecepcionForm, SalidaMaterialForm, GuiaTrasladoForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.utils import timezone
from django.db import transaction
import json
from decimal import Decimal


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
    # 1. Obtener parámetros de filtro por columna
    f_rq = request.GET.get('f_rq', '').strip()
    f_codigo = request.GET.get('f_codigo', '').strip()
    f_desc = request.GET.get('f_desc', '').strip()
    f_np = request.GET.get('f_np', '').strip()
    f_odc = request.GET.get('f_odc', '').strip()
    f_em = request.GET.get('f_em', '').strip()
    f_prov = request.GET.get('f_prov', '').strip()
    f_tipo = request.GET.get('f_tipo', '').strip()
    f_cargo = request.GET.get('f_cargo', '').strip()
    f_nota = request.GET.get('f_nota', '').strip()

    materiales_qs = Material.objects.all()

    # 2. Aplicar filtros condicionales (Server-side)
    if f_rq:
        materiales_qs = materiales_qs.filter(detallerecepcion__nro_rq__icontains=f_rq)
    if f_codigo:
        materiales_qs = materiales_qs.filter(codigo__icontains=f_codigo)
    if f_desc:
        materiales_qs = materiales_qs.filter(descripcion__icontains=f_desc)
    if f_np:
        materiales_qs = materiales_qs.filter(nro_parte__icontains=f_np)
    if f_odc:
        materiales_qs = materiales_qs.filter(detallerecepcion__nro_odc__icontains=f_odc)
    if f_em:
        materiales_qs = materiales_qs.filter(detallerecepcion__nro_control_entrada__icontains=f_em)
    if f_prov:
        materiales_qs = materiales_qs.filter(detallerecepcion__proveedor__icontains=f_prov)
    if f_tipo:
        materiales_qs = materiales_qs.filter(tipo__icontains=f_tipo)
    if f_cargo:
        materiales_qs = materiales_qs.filter(cargo__icontains=f_cargo)
    if f_nota:
        materiales_qs = materiales_qs.filter(detallerecepcion__nro_nota_entrega__icontains=f_nota)

    # 3. Optimización y Paginación
    from django.db.models import Prefetch
    materiales_qs = materiales_qs.order_by('codigo').prefetch_related(
        Prefetch('detallerecepcion_set', queryset=DetalleRecepcion.objects.order_by('fecha_recepcion', 'id')),
        'detallerecepcion_set__salidamaterialdetalle_set'
    ).distinct()

    paginator = Paginator(materiales_qs, 50)
    page_number = request.GET.get('page')
    materiales_paginados = paginator.get_page(page_number)

    # 4. Preservar estado para el HTML y enlaces de página
    query_params = request.GET.copy()
    if 'page' in query_params:
        del query_params['page']
    querystring = query_params.urlencode()
    query_prefix = f"{querystring}&" if querystring else ''

    contexto = {
        'materiales': materiales_paginados,
        'query_prefix': query_prefix,
        'filtros': {
            'rq': f_rq, 'codigo': f_codigo, 'desc': f_desc, 'np': f_np,
            'odc': f_odc, 'em': f_em, 'prov': f_prov, 'tipo': f_tipo,
            'cargo': f_cargo, 'nota': f_nota
        }
    }
    return render(request, 'inventario/lista_materiales.html', contexto)

# Vista 3: Lista de Reportes de Entrada (CON BUSCADOR)
@login_required(login_url='login')
def lista_entradas(request):
    from django.db.models import Q, Sum, F, Max, DecimalField
    # 1. Capturar filtros por columna (TODOS)
    f_base = request.GET.get('f_base', '').strip()
    f_em = request.GET.get('f_em', '').strip()
    f_fecha_rep = request.GET.get('f_fecha_rep', '').strip()
    f_fecha_ent = request.GET.get('f_fecha_ent', '').strip()
    f_odc = request.GET.get('f_odc', '').strip()
    f_nota = request.GET.get('f_nota', '').strip()
    f_prov = request.GET.get('f_prov', '').strip()
    f_mat = request.GET.get('f_mat', '').strip()
    f_obs = request.GET.get('f_obs', '').strip()
    f_rm = request.GET.get('f_rm', '').strip()
    f_vol = request.GET.get('f_vol', '').strip()

    # 2. Obtener los IDs de los registros representativos
    ids_unicos = DetalleRecepcion.objects.exclude(es_saldo_inicial=True).values('nro_control_entrada').annotate(max_id=Max('id')).values_list('max_id', flat=True)
    
    # 3. QuerySet Base
    recepciones_lista = DetalleRecepcion.objects.exclude(es_saldo_inicial=True).select_related('material', 'reporte').filter(id__in=ids_unicos)

    # 4. Aplicar filtros condicionales
    if f_base:
        recepciones_lista = recepciones_lista.filter(departamento__icontains=f_base)
    if f_em:
        recepciones_lista = recepciones_lista.filter(nro_control_entrada__icontains=f_em)
    if f_fecha_rep:
        recepciones_lista = recepciones_lista.filter(reporte__fecha_recepcion__icontains=f_fecha_rep)
    if f_fecha_ent:
        recepciones_lista = recepciones_lista.filter(fecha_recepcion__icontains=f_fecha_ent)
    if f_odc:
        recepciones_lista = recepciones_lista.filter(nro_odc__icontains=f_odc)
    if f_nota:
        recepciones_lista = recepciones_lista.filter(nro_nota_entrega__icontains=f_nota)
    if f_prov:
        recepciones_lista = recepciones_lista.filter(proveedor__icontains=f_prov)
    if f_mat:
        recepciones_lista = recepciones_lista.filter(
            Q(material__codigo__icontains=f_mat) | Q(material__descripcion__icontains=f_mat) | Q(descripcion_entrada__icontains=f_mat)
        )
    if f_obs:
        recepciones_lista = recepciones_lista.filter(observaciones__icontains=f_obs)
    if f_rm:
        recepciones_lista = recepciones_lista.filter(reporte__nro_reporte__icontains=f_rm)
    if f_vol:
        recepciones_lista = recepciones_lista.filter(volumen_carpeta__icontains=f_vol)

    recepciones_lista = recepciones_lista.order_by('-fecha_recepcion', '-id')

    # Para el cálculo del total agrupado, lo haremos in-memory o con una anotación pesada.
    # Dado que es SQLite y queremos mantener objetos, usaremos una anotación con Subquery o simplemente
    # calcularemos los totales después de filtrar.
    
    # Optamos por anotar el total agrupado para que el template lo use directamente.
    from django.db.models import OuterRef, Subquery
    
    totales_qs = DetalleRecepcion.objects.filter(
        nro_control_entrada=OuterRef('nro_control_entrada')
    ).values('nro_control_entrada').annotate(
        total=Sum(F('cantidad_recibida') * F('precio_unitario'), output_field=DecimalField())
    ).values('total')

    recepciones_lista = recepciones_lista.annotate(costo_total_agrupado=Subquery(totales_qs))
        
    # Paginación
    from django.core.paginator import Paginator
    paginator = Paginator(recepciones_lista, 50) 
    page_number = request.GET.get('page')
    recepciones_paginadas = paginator.get_page(page_number)

    # 6. Preservar estado
    query_params = request.GET.copy()
    if 'page' in query_params:
        del query_params['page']
    query_prefix = query_params.urlencode() + '&' if query_params else ''

    contexto = {
        'recepciones': recepciones_paginadas,
        'query_prefix': query_prefix,
        'filtros': {
            'base': f_base, 'em': f_em, 'fecha_rep': f_fecha_rep, 'fecha_ent': f_fecha_ent,
            'odc': f_odc, 'nota': f_nota, 'prov': f_prov, 'mat': f_mat,
            'obs': f_obs, 'rm': f_rm, 'vol': f_vol
        }
    }
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
                        continue

                    detalle = DetalleRecepcion(
                        reporte=reporte,
                        material=material_obj,
                        nro_odc=item.get('nro_odc'),
                        fecha_recepcion=reporte.fecha_recepcion,
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
    }
    return render(request, 'inventario/crear_recepcion.html', contexto)

# Vista 4B: Formulario independiente para registrar entradas (EM)
@login_required(login_url='login')
@user_passes_test(es_almacenista, login_url='lista_entradas') 
def registrar_entrada(request):
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
                    # -------------------------------------------------------
                    # La entrada usa descripcion libre, material es opcional
                    # -------------------------------------------------------
                    codigo_material = item.get('material', '').split(' - ')[0].replace('[MATERIAL]', '').replace('[ACTIVOS]', '').replace('[DIRECTO AL GASTO]', '').strip()
                    material_obj = None
                    if codigo_material:
                        material_obj = Material.objects.filter(codigo=codigo_material).first()
                    
                    # Auto-matcheo con reporte existente si tienen misma ODC y Nota de Entrega
                    rep_final = reporte_obj
                    if rep_final is None:
                        nro_odc_item = item.get('nro_odc', '').strip()
                        nro_nota_item = item.get('nro_nota_entrega', '').strip()
                        
                        if nro_odc_item and nro_nota_item:
                            # Buscar un hermano que comparta ODC + Nota de Entrega y ya tenga reporte
                            sibling = DetalleRecepcion.objects.filter(
                                nro_odc=nro_odc_item,
                                nro_nota_entrega=nro_nota_item,
                                reporte__isnull=False
                            ).select_related('reporte').first()
                            if sibling:
                                rep_final = sibling.reporte
                        elif nro_odc_item:
                            # Fallback: solo ODC si no hay nota de entrega
                            sibling = DetalleRecepcion.objects.filter(
                                nro_odc=nro_odc_item,
                                reporte__isnull=False
                            ).select_related('reporte').first()
                            if sibling:
                                rep_final = sibling.reporte

                    # ---------------------------------------------------
                    # GENERAR CÓDIGO SEGÚN TIPO SELECCIONADO POR USUARIO
                    # ---------------------------------------------------
                    import datetime as dt
                    tipo_entrada = item.get('tipo_entrada', 'MATERIAL')
                    mapa_prefijos = {
                        'MATERIAL': 'EM',
                        'ACTIVOS': 'EA',
                        'DIRECTO AL GASTO': 'EDG'
                    }
                    prefijo = mapa_prefijos.get(tipo_entrada, 'EM')
                    
                    fecha_entrada_str = item.get('fecha_entrada')
                    if fecha_entrada_str:
                        try:
                            fecha_para_codigo = dt.date.fromisoformat(fecha_entrada_str)
                        except ValueError:
                            fecha_para_codigo = timezone.now().date()
                    else:
                        fecha_para_codigo = timezone.now().date()
                    
                    año_corto = fecha_para_codigo.strftime('%y')
                    inicio_codigo = f"{prefijo}{año_corto}"
                    
                    ultimo_detalle = DetalleRecepcion.objects.filter(
                        nro_control_entrada__startswith=inicio_codigo
                    ).order_by('id').last()
                    
                    if ultimo_detalle and ultimo_detalle.nro_control_entrada:
                        try:
                            ultimo_num = int(ultimo_detalle.nro_control_entrada[-4:])
                            nuevo_num = ultimo_num + 1
                        except ValueError:
                            nuevo_num = 1
                    else:
                        nuevo_num = 1
                    
                    nro_control_generado = f"{inicio_codigo}{nuevo_num:04d}"

                    detalle = DetalleRecepcion(
                        reporte=rep_final,
                        material=material_obj,  # Puede ser None si no hay en catálogo
                        descripcion_entrada=item.get('descripcion_entrada') or item.get('material_texto'),
                        nro_control_entrada=nro_control_generado,
                        nro_odc=item.get('nro_odc'),
                        fecha_recepcion=fecha_para_codigo,
                        nro_rq=item.get('nro_rq'),
                        departamento=item.get('base'),
                        proveedor=item.get('proveedor'),
                        moneda=item.get('moneda', 'USD'),
                        eta=item.get('eta') or None,
                        nro_nota_entrega=item.get('nro_nota_entrega'),
                        cantidad_solicitada=Decimal(item.get('cantidad_solicitada') or '0'),
                        cantidad_recibida=Decimal(item.get('cantidad_recibida') or '0'),
                        precio_unitario=Decimal(item.get('precio_unitario') or '0'),
                        observaciones=item.get('observaciones')
                    )
                    detalle.save()  # nro_control_entrada ya viene seteado, el modelo no lo regen
            return redirect('lista_entradas')
            
    form_detalle = DetalleRecepcionForm()
    odcs_existentes = list(DetalleRecepcion.objects.exclude(nro_odc__isnull=True).exclude(nro_odc__exact='').values_list('nro_odc', flat=True).distinct())
    reportes_recientes = ReporteRecepcion.objects.all().order_by('-fecha_recepcion', '-id')[:30]

    contexto = {
        'form_detalle': form_detalle,
        'odcs_existentes': odcs_existentes,
        'reportes_recientes': reportes_recientes
    }
    return render(request, 'inventario/registrar_entrada.html', contexto)

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
            return redirect('lista_entradas')
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
    # 1. Capturar filtros (TODOS)
    f_fecha = request.GET.get('f_fecha', '').strip()
    f_rim = request.GET.get('f_rim', '').strip()
    f_mat = request.GET.get('f_mat', '').strip()
    f_cant = request.GET.get('f_cant', '').strip()
    f_um = request.GET.get('f_um', '').strip()
    f_depto = request.GET.get('f_depto', '').strip()
    f_cc = request.GET.get('f_cc', '').strip()

    # 2. QuerySet Base
    salidas_qs = SalidaMaterial.objects.exclude(
        Q(nro_rim__startswith='AJUSTE-MIG') | Q(departamento='MIGRACIÓN')
    ).select_related('material').all()

    # 3. Filtros
    if f_fecha:
        salidas_qs = salidas_qs.filter(fecha_despacho__icontains=f_fecha)
    if f_rim:
        salidas_qs = salidas_qs.filter(nro_rim__icontains=f_rim)
    if f_mat:
        salidas_qs = salidas_qs.filter(
            Q(material__codigo__icontains=f_mat) | Q(material__descripcion__icontains=f_mat)
        )
    if f_cant:
        salidas_qs = salidas_qs.filter(cantidad__icontains=f_cant)
    if f_um:
        salidas_qs = salidas_qs.filter(material__unidad_medida__icontains=f_um)
    if f_depto:
        salidas_qs = salidas_qs.filter(departamento__icontains=f_depto)
    if f_cc:
        salidas_qs = salidas_qs.filter(centro_costo__icontains=f_cc)

    salidas_qs = salidas_qs.order_by('-fecha_despacho', '-id')

    paginator = Paginator(salidas_qs, 50)
    page_number = request.GET.get('page')
    salidas_paginadas = paginator.get_page(page_number)

    query_params = request.GET.copy()
    if 'page' in query_params:
        del query_params['page']
    query_prefix = query_params.urlencode() + '&' if query_params else ''

    contexto = {
        'salidas': salidas_paginadas,
        'query_prefix': query_prefix,
        'filtros': {
            'fecha': f_fecha, 'rim': f_rim, 'mat': f_mat, 'cant': f_cant,
            'um': f_um, 'depto': f_depto, 'cc': f_cc
        }
    }
    return render(request, 'inventario/lista_salidas.html', contexto)

# VISTA 7: Registrar un Nuevo Despacho (RIM)
@login_required(login_url='login')
@user_passes_test(es_almacenista, login_url='lista_entradas') # <--- ESCUDO NUEVO
def crear_salida(request):
    if request.method == 'POST':
        form = SalidaMaterialForm(request.POST)
        if form.is_valid():
            # Guardamos la instancia SIN commit para poder inyectar los campos extra
            salida = form.save(commit=False)
            # Inyectamos los campos financieros que no están en Meta.fields
            salida.departamento = form.cleaned_data.get('departamento') or None
            salida.centro_costo = form.cleaned_data.get('centro_costo') or None
            salida.cuenta_contable = form.cleaned_data.get('cuenta_contable') or None
            salida.partida_presupuestaria = form.cleaned_data.get('partida_presupuestaria') or None
            salida.save()  # Aquí se dispara la lógica FIFO y de stock
            
            if form.cleaned_data.get('necesita_guia'):
                return redirect('crear_guia')
                
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
    salida_base = get_object_or_404(SalidaMaterial, id=salida_id)
    
    # 2. Si el usuario quiere ver TODO el RIM agrupado (todos los materiales del mismo nro_rim)
    # buscamos todos los registros que compartan el nro_rim
    salidas_agrupadas = SalidaMaterial.objects.filter(
        nro_rim=salida_base.nro_rim,
        fecha_despacho=salida_base.fecha_despacho
    ).prefetch_related('detalles__detalle_recepcion')
    
    # 3. Le decimos qué plantilla HTML vamos a usar
    template_path = 'inventario/pdf_salida.html'
    context = {
        'salida': salida_base,
        'salidas_agrupadas': salidas_agrupadas,
    }
    
    # 4. Configuramos la respuesta del navegador
    response = HttpResponse(content_type='application/pdf')
    
    # 5. Renderizamos el HTML
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
# VISTA 14: Reportes (Listado detallado con botones)
# ==================================================
@login_required(login_url='login')
def reportes(request):
    query = request.GET.get('buscar', '').strip()
    
    # EXCLUSIÓN DE MIGRACIÓN: Ocultamos saldos iniciales
    items_qs = DetalleRecepcion.objects.exclude(es_saldo_inicial=True).select_related('material', 'reporte').all().order_by('-fecha_recepcion', '-id')

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

    # Auditoría: Conteo de entradas sin material asignado (Monederos)
    total_pendientes = DetalleRecepcion.objects.filter(material__isnull=True).count()

    # --- LÓGICA CENTRALIZADA: Garantizar que siempre haya uno ABIERTO ---
    if not ReporteRecepcion.objects.filter(estado='ABIERTO').exists():
        ReporteRecepcion.objects.create(estado='ABIERTO')
    
    hay_reportes_abiertos = True

    contexto = {
        'reportes': items_paginados,
        'query': query,
        'total_pendientes': total_pendientes,
        'hay_reportes_abiertos': hay_reportes_abiertos
    }
    return render(request, 'inventario/reportes.html', contexto)
# ==========================================
# NUEVA VISTA: BANDEJA DE ENTRADA DEL JEFE
# ==========================================
@login_required(login_url='login')
@user_passes_test(es_almacenista, login_url='reportes')
def reportes_pendientes(request):
    # Traemos SOLO los registros globales (Monederos) que no han sido desglosados
    pendientes = DetalleRecepcion.objects.filter(
        material__isnull=True
    ).select_related('reporte').order_by('fecha_recepcion', '-id')

    # Formularios para el desglose (se usarán vía JS en la misma página)
    form = ReporteRecepcionForm()
    form_detalle = DetalleRecepcionForm()
    
    # Lista de materiales para el Select2
    materiales = Material.objects.all().order_by('codigo')

    contexto = {
        'pendientes': pendientes,
        'total_pendientes': pendientes.count(),
        'form': form,
        'form_detalle': form_detalle,
        'materiales': materiales
    }
    return render(request, 'inventario/reportes_pendientes.html', contexto)
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


# ==================================================
# API: Obtener desglose de LOTES (FIFO) de un Material
# ==================================================
@login_required(login_url='login')
def api_lotes_material(request, material_id):
    from django.http import JsonResponse
    material = get_object_or_404(Material, id=material_id)
    
    # Obtenemos todos los lotes que tienen stock disponible
    lotes_qs = material.detallerecepcion_set.filter(
        cantidad_recibida__gt=0
    ).order_by('fecha_recepcion', 'id')
    
    lotes = []
    for lote in lotes_qs:
        # Solo incluimos lotes con disponibilidad real
        if lote.cantidad_disponible > 0:
            lotes.append({
                'em': lote.nro_control_entrada,
                'fecha': lote.fecha_recepcion.strftime('%d/%m/%Y'),
                'odc': lote.nro_odc,
                'recibido': float(lote.cantidad_recibida),
                'disponible': float(lote.cantidad_disponible),
                'precio': float(lote.precio_unitario or 0),
                'total': float(lote.valor_recibido),
            })
    
    return JsonResponse({
        'codigo': material.codigo,
        'descripcion': material.descripcion,
        'stock_total': float(material.stock_actual),
        'lotes': lotes
    })


# ==================================================
# API: Obtener partidas presupuestarias por departamento (AJAX)
# ==================================================
@login_required(login_url='login')
def api_partidas_por_departamento(request):
    from django.http import JsonResponse
    import datetime
    
    departamento = request.GET.get('departamento', '').strip()
    anio = datetime.date.today().year
    
    if not departamento:
        return JsonResponse([], safe=False)
    
    partidas = PresupuestoAnual.objects.filter(
        departamento__iexact=departamento,
        anio=anio
    ).values('id', 'partida', 'cuenta_contable', 'descripcion_cuenta')
    
    return JsonResponse(list(partidas), safe=False)


# ==================================================
# API: Historial de una ODC + Nota de Entrega (Para el panel lateral en Entradas)
# Devuelve todos los DetalleRecepcion con la misma ODC y Nota de Entrega,
# tanto entradas simples como ítems de reportes.
# ==================================================
@login_required(login_url='login')
def api_historial_odc(request):
    from django.http import JsonResponse

    odc = request.GET.get('odc', '').strip()
    nota = request.GET.get('nota', '').strip()

    if not odc:
        return JsonResponse({'entradas': [], 'reportes': []})

    # Filtrar por ODC (obligatorio) y nota de entrega si viene
    filtro = Q(nro_odc=odc)
    if nota:
        filtro &= Q(nro_nota_entrega=nota)

    registros = DetalleRecepcion.objects.filter(filtro).select_related('material', 'reporte').order_by('fecha_recepcion', 'id')

    entradas = []
    reportes_vistos = set()
    reportes_lista = []

    for r in registros:
        desc = r.descripcion_entrada or (r.material.descripcion if r.material else '-')
        em = r.nro_control_entrada or '-'
        entradas.append({
            'em': em,
            'fecha': r.fecha_recepcion.strftime('%d/%m/%Y') if r.fecha_recepcion else '-',
            'odc': r.nro_odc or '-',
            'nota': r.nro_nota_entrega or '-',
            'proveedor': r.proveedor or '-',
            'descripcion': desc,
            'costo': str(r.precio_unitario or '0.00'),
            'reporte': r.reporte.nro_reporte if r.reporte else None,
        })
        if r.reporte and r.reporte.id not in reportes_vistos:
            reportes_vistos.add(r.reporte.id)
            reportes_lista.append({
                'nro_reporte': r.reporte.nro_reporte,
                'fecha': r.reporte.fecha_recepcion.strftime('%d/%m/%Y') if r.reporte.fecha_recepcion else '-',
            })

    return JsonResponse({'entradas': entradas, 'reportes': reportes_lista})

@login_required(login_url='login')
@user_passes_test(es_almacenista, login_url='reportes')
def desglosar_entrada(request, detalle_id):
    monedero = get_object_or_404(DetalleRecepcion, id=detalle_id)
    
    if request.method == 'POST':
        carrito_json = request.POST.get('carrito_datos', '[]')
        try:
            items_carrito = json.loads(carrito_json)
        except:
            items_carrito = []

        if items_carrito:
            with transaction.atomic():
                # --- LÓGICA CENTRALIZADA: Buscar el único reporte ABIERTO ---
                reporte_obj = ReporteRecepcion.objects.filter(estado='ABIERTO').first()
                if not reporte_obj:
                    reporte_obj = ReporteRecepcion.objects.create(estado='ABIERTO')

                for item in items_carrito:
                    codigo_material = item.get('material', '').split(' - ')[0].replace('[MATERIAL]', '').replace('[ACTIVOS]', '').replace('[DIRECTO AL GASTO]', '').strip()
                    material_obj = Material.objects.filter(codigo=codigo_material).first()
                    if not material_obj: continue

                    nuevo_detalle = DetalleRecepcion(
                        reporte=reporte_obj,
                        material=material_obj,
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
                monedero.delete()
            return redirect('reportes_pendientes')

@login_required(login_url='login')
@user_passes_test(es_almacenista, login_url='reportes')
def cambiar_estado_reportes(request):
    if request.method == 'POST':
        from django.http import JsonResponse
        import json
        try:
            data = json.loads(request.body)
            nuevo_estado = data.get('estado')
            if nuevo_estado == 'CERRADO':
                with transaction.atomic():
                    # 1. Buscamos el reporte que está actualmente abierto
                    reporte_abierto = ReporteRecepcion.objects.filter(estado='ABIERTO').first()
                    if reporte_abierto:
                        reporte_abierto.estado = 'CERRADO'
                        reporte_abierto.save()
                    
                    # 2. Creamos el nuevo reporte para el siguiente ciclo
                    ReporteRecepcion.objects.create(estado='ABIERTO')
                
                return JsonResponse({'status': 'ok', 'mensaje': 'Reporte cerrado y nuevo reporte abierto.'})
            
            return JsonResponse({'status': 'ok'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error'}, status=400)

@login_required(login_url='login')
@user_passes_test(es_almacenista, login_url='reportes')
def actualizar_ubicacion_material(request):
    if request.method == 'POST':
        import json
        from django.http import JsonResponse
        try:
            data = json.loads(request.body)
            material_id = data.get('material_id')
            nueva_ubicacion = data.get('ubicacion')
            
            if material_id:
                material = get_object_or_404(Material, id=material_id)
                material.ubicacion = nueva_ubicacion
                material.save()
                return JsonResponse({'status': 'ok'})
            
            return JsonResponse({'status': 'error', 'message': 'Falta ID de Material'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error'}, status=400)

@login_required(login_url='login')
@user_passes_test(es_almacenista, login_url='reportes')
def actualizar_volumen_carpeta(request):
    if request.method == 'POST':
        import json
        from django.http import JsonResponse
        try:
            data = json.loads(request.body)
            nro_em = data.get('nro_control_entrada')
            nuevo_volumen = data.get('volumen')
            
            if nro_em:
                # Actualizamos todos los registros que compartan ese EM (para el caso de desgloses)
                DetalleRecepcion.objects.filter(nro_control_entrada=nro_em).update(volumen_carpeta=nuevo_volumen)
                return JsonResponse({'status': 'ok'})
            
            return JsonResponse({'status': 'error', 'message': 'Falta Nro. Control'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error'}, status=400)