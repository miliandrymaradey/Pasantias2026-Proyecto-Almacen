from .models import SalidaMaterial, Material
from django import forms
from .models import ReporteRecepcion, DetalleRecepcion
from .models import GuiaTraslado, CentroCosto
import re

class ReporteRecepcionForm(forms.ModelForm):
    class Meta:
        model = ReporteRecepcion
        fields = ['fecha_recepcion', 'descripcion']
        widgets = {
        
        'fecha_recepcion': forms.DateInput(attrs={'type': 'date', 'class': 'form-control bg-dark text-white border-secondary'}),
        'descripcion': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Ej. Recepción de repuestos mecánicos...'}),
        
        }

class ReporteRecepcionEditForm(forms.ModelForm):
    """Formulario para editar el encabezado del reporte diario (RP)."""
    def __init__(self, *args, **kwargs):
        super(ReporteRecepcionEditForm, self).__init__(*args, **kwargs)
        self.fields['nro_reporte'].widget.attrs.update({
            'class': 'form-control bg-secondary text-white border-secondary',
            'readonly': 'readonly'
        })
        self.fields['fecha_recepcion'].widget = forms.DateInput(attrs={
            'type': 'date', 
            'class': 'form-control bg-dark text-white border-secondary'
        })
        self.fields['descripcion'].widget.attrs.update({
            'class': 'form-control bg-dark text-white border-secondary'
        })

    class Meta:
        model = ReporteRecepcion
        fields = ['nro_reporte', 'fecha_recepcion', 'descripcion']

class DetalleRecepcionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(DetalleRecepcionForm, self).__init__(*args, **kwargs)
        try:
            from .models import PresupuestoAnual
            deptos = list(PresupuestoAnual.objects.values_list('departamento', flat=True).distinct().order_by('departamento'))
            if self.instance and self.instance.pk and self.instance.departamento:
                if self.instance.departamento not in deptos:
                    deptos.append(self.instance.departamento)
                    deptos.sort()
            opciones_deptos = [('', '--- Seleccione departamento ---')] + [(d, d) for d in deptos if d]
        except Exception:
            opciones_deptos = [('', '--- Seleccione departamento ---')]

        self.fields['departamento'] = forms.ChoiceField(
            choices=opciones_deptos,
            required=False,
            label='BASE (Ubicación / Dpto.)',
            widget=forms.Select(attrs={
                'class': 'form-select bg-dark text-white border-secondary',
                'id': 'id_departamento'
            })
        )

    class Meta:
        model = DetalleRecepcion
        fields = ['fecha_recepcion', 'nro_rq', 'departamento', 'material', 'nro_odc', 'nro_nota_entrega', 'proveedor', 'cantidad_solicitada', 'cantidad_recibida', 'precio_unitario', 'observaciones']
        widgets = {
            'material': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'nro_odc': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'nro_nota_entrega': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'proveedor': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'cantidad_solicitada': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'cantidad_recibida': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'precio_unitario': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'observaciones': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Opcional...'}),
            'nro_rq': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
        }

    def clean_nro_odc(self):
        nro_odc = self.cleaned_data.get('nro_odc')
        if not nro_odc:
            return nro_odc
            
        nro_odc = nro_odc.strip()
        patron = r'^PRSV-\d{4}-\d{10}$'
        
        # 1. ¿Cumple el formato nuevo?
        if re.match(patron, nro_odc):
            return nro_odc
            
        # 2. ¿Es un dato histórico (ya existe)?
        existe = DetalleRecepcion.objects.filter(nro_odc=nro_odc).exists()
        if existe:
            return nro_odc
            
        # 3. Si no es ninguna de las anteriores
        raise forms.ValidationError(
            "Formato de ODC inválido. Solo se permiten formatos nuevos (PRSV-AÑO-10dígitos) "
            "o números de ODC ya registrados en el histórico."
        )

class DetalleRecepcionEditForm(forms.ModelForm):
    """Formulario para editar entradas sin tocar material ni cantidad."""
    def __init__(self, *args, **kwargs):
        super(DetalleRecepcionEditForm, self).__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control bg-dark text-white border-secondary'})
            
        try:
            from .models import PresupuestoAnual
            deptos = list(PresupuestoAnual.objects.values_list('departamento', flat=True).distinct().order_by('departamento'))
            if self.instance and self.instance.pk and self.instance.departamento:
                if self.instance.departamento not in deptos:
                    deptos.append(self.instance.departamento)
                    deptos.sort()
            opciones_deptos = [('', '--- Seleccione departamento ---')] + [(d, d) for d in deptos if d]
        except Exception:
            opciones_deptos = [('', '--- Seleccione departamento ---')]

        self.fields['departamento'] = forms.ChoiceField(
            choices=opciones_deptos,
            required=False,
            label='Dpto / Equipo',
            widget=forms.Select(attrs={
                'class': 'form-select bg-dark text-white border-secondary'
            })
        )
            
    class Meta:
        model = DetalleRecepcion
        fields = [
            'fecha_recepcion', 'nro_control_entrada', 'nro_odc', 'nro_nota_entrega', 
            'proveedor', 'nro_rq', 'departamento', 'volumen_carpeta', 'observaciones'
        ]
        widgets = {
            'fecha_recepcion': forms.DateInput(attrs={'type': 'date'}),
        }

class SalidaMaterialForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(SalidaMaterialForm, self).__init__(*args, **kwargs)

        # --- DEPARTAMENTO: quién solicita → filtra las partidas presupuestarias ---
        try:
            from .models import PresupuestoAnual
            deptos = PresupuestoAnual.objects.values_list('departamento', flat=True).distinct().order_by('departamento')
            opciones_deptos = [('', '--- Seleccione departamento ---')] + [(d, d) for d in deptos if d]
        except:
            opciones_deptos = [('', '--- Seleccione departamento ---')]

        self.fields['departamento'] = forms.ChoiceField(
            choices=opciones_deptos, required=False,
            label='Departamento Solicitante',
            widget=forms.Select(attrs={
                'class': 'form-select bg-dark text-white border-secondary',
                'id': 'id_departamento'
            })
        )

        # --- CENTRO DE COSTO: hacia dónde va → campo independiente ---
        self.fields['centro_costo'] = forms.ModelChoiceField(
            queryset=CentroCosto.objects.all().order_by('nombre'),
            required=False,
            label='Centro de Costo (Destino)',
            empty_label='--- Seleccione ---',
            widget=forms.Select(attrs={
                'class': 'form-select bg-dark text-white border-secondary',
                'id': 'id_centro_costo'
            })
        )

        # --- CUENTA CONTABLE: readonly, la llena el JS al elegir partida ---
        self.fields['cuenta_contable'] = forms.CharField(
            required=False,
            widget=forms.TextInput(attrs={
                'class': 'form-control bg-secondary text-white border-secondary',
                'id': 'id_cuenta_contable',
                'readonly': 'readonly',
                'placeholder': 'Auto...',
                'style': 'cursor: not-allowed;'
            })
        )

        # --- RUBRO 1: readonly ---
        self.fields['rubro_1'] = forms.CharField(
            required=False,
            widget=forms.TextInput(attrs={
                'class': 'form-control bg-secondary text-white border-secondary',
                'id': 'id_rubro_1',
                'readonly': 'readonly',
                'placeholder': 'Auto...',
                'style': 'cursor: not-allowed;'
            })
        )

        # --- RUBRO 2: readonly ---
        self.fields['rubro_2'] = forms.CharField(
            required=False,
            widget=forms.TextInput(attrs={
                'class': 'form-control bg-secondary text-white border-secondary',
                'id': 'id_rubro_2',
                'readonly': 'readonly',
                'placeholder': 'Auto...',
                'style': 'cursor: not-allowed;'
            })
        )

        # --- PARTIDA PRESUPUESTARIA: menú vacío que JS puebla dinámicamente ---
        self.fields['partida_presupuestaria'] = forms.CharField(
            required=False,
            widget=forms.Select(attrs={
                'class': 'form-select bg-dark text-white border-secondary',
                'id': 'id_partida_presupuestaria'
            })
        )

        # --- TIPO DE SALIDA (SM, SA, SDG) ---
        self.fields['tipo_salida'] = forms.ChoiceField(
            choices=[('SM', 'SM - Materiales'), ('SA', 'SA - Activos'), ('SDG', 'SDG - Directo al Gasto')],
            initial='SM',
            widget=forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary', 'id': 'id_tipo_salida'})
        )

        # --- NÚMERO CORRELATIVO (4 DÍGITOS) ---
        self.fields['numero_salida_correlativo'] = forms.CharField(
            max_length=4, min_length=4, required=False,
            widget=forms.TextInput(attrs={
                'class': 'form-control bg-dark text-white border-secondary',
                'id': 'id_numero_salida_correlativo',
                'placeholder': 'Ej: 0012',
                'pattern': r'\d{4}',
                'title': 'Debe ingresar exactamente 4 números'
            })
        )

        # --- OPCIÓN: ¿Necesita Guía de Traslado? ---
        self.fields['necesita_guia'] = forms.BooleanField(
            required=False,
            label='¿Requiere Guía de Traslado?',
            widget=forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'necesita_guia_check'
            })
        )

    def clean_nro_rim(self):
        data = self.cleaned_data.get('nro_rim')
        if not re.match(r'^[A-Z]{3,4}-\d{3}-\d{4}$', data):
            raise forms.ValidationError("El formato del Nro. RIM es inválido. Debe seguir el patrón DPT-000-AÑO (Ej. OPE-001-2026).")
        return data

    class Meta:
        model = SalidaMaterial
        fields = ['fecha_despacho', 'nro_rim', 'material', 'cantidad']
        widgets = {
            'fecha_despacho': forms.DateInput(attrs={'type': 'date', 'class': 'form-control bg-dark text-white border-secondary'}),
            'nro_rim': forms.TextInput(attrs={
                'class': 'form-control bg-dark text-white border-secondary', 
                'placeholder': 'Ej. OPE-001-2026',
                'pattern': r'[A-Z]{3,4}-\d{3}-\d{4}',
                'title': 'Formato: DPT-000-AÑO (Ej. OPE-001-2026)'
            }),
            'material': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
        }

class SalidaMaterialEditForm(forms.ModelForm):
    """Formulario especializado para editar despachos sin tocar stock."""
    
    def __init__(self, *args, **kwargs):
        super(SalidaMaterialEditForm, self).__init__(*args, **kwargs)
        
        # Estilos comunes para todos los campos
        for field in self.fields:
            if not isinstance(self.fields[field].widget, forms.CheckboxInput):
                self.fields[field].widget.attrs.update({'class': 'form-control bg-dark text-white border-secondary'})
        
        # Selects específicos
        self.fields['tipo_salida'].widget = forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})
        self.fields['centro_costo'].widget = forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'})

    class Meta:
        model = SalidaMaterial
        fields = [
            'fecha_despacho', 'nro_rim', 'tipo_salida', 'numero_salida_correlativo',
            'departamento', 'centro_costo', 'partida_presupuestaria', 
            'cuenta_contable', 'descripcion_cuenta', 'rubro_1', 'rubro_2'
        ]
        widgets = {
            'fecha_despacho': forms.DateInput(attrs={'type': 'date'}),
        }

class GuiaTrasladoForm(forms.ModelForm):
    class Meta:
        model = GuiaTraslado
        fields = ['taladro_destino', 'fecha', 'hora', 'direccion', 'ciudad', 'conductor', 'ci_conductor', 'vehiculo', 'color', 'placa', 'marca', 'modelo', 'observaciones', 'nombre_entregado', 'nombre_aprobador']
        widgets = {
            'taladro_destino': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control bg-dark text-white border-secondary'}),
            'hora': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control bg-dark text-white border-secondary'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'ciudad': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'conductor': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'ci_conductor': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'vehiculo': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'color': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'placa': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'marca': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control bg-dark text-white border-secondary', 'rows': 3}),
            'nombre_entregado': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'nombre_aprobador': forms.TextInput(attrs={
                'class': 'form-control bg-dark text-white border-secondary', 
                'placeholder': 'Nombre de quien aprueba'
            }),
        }
        labels = {
            'nombre_aprobador': 'Aprobado en Almacén por:',
        }

class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ['codigo', 'descripcion', 'tipo', 'unidad_medida', 'cargo', 'ubicacion', 'nro_parte']
        exclude = ['stock_actual']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Ej. MAT-001'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Ej. Filtro de aceite...'}),
            'tipo': forms.Select(choices=[
                ('MATERIAL', 'EM - Material'),
                ('ACTIVOS', 'EA - Activo'),
                ('DIRECTO AL GASTO', 'EDG - Directo al Gasto')
            ], attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'unidad_medida': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Ej. UNID, MTS, LTS'}),
            'cargo': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'ubicacion': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Ej. Estante A-1'}),
            'nro_parte': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Opcional'}),
        }


# ==========================================
# FORMULARIOS: ACTUALIZACIÓN DE PERFIL
# ==========================================
from django.contrib.auth.models import User
from .models import PerfilUsuario

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Ej. JUAN'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Ej. PÉREZ'}),
            'email': forms.EmailInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Ej. juan.perez@perforosven.com'}),
        }
        labels = {
            'first_name': 'Nombres',
            'last_name': 'Apellidos',
            'email': 'Correo Electrónico',
        }

class PerfilUpdateForm(forms.ModelForm):
    class Meta:
        model = PerfilUsuario
        fields = ['foto']
        widgets = {
            'foto': forms.FileInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'accept': 'image/*'}),
        }
        labels = {
            'foto': 'Actualizar Foto de Perfil',
        }


# ==========================================
# FORMULARIOS: EDICIÓN DE REGISTRO MAESTRO
# ==========================================
from .models import Activo

class MaterialUpdateForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(MaterialUpdateForm, self).__init__(*args, **kwargs)
        # Código de material inmutable para mantener consistencia histórica
        self.fields['codigo'].widget.attrs.update({
            'class': 'form-control bg-secondary text-white border-secondary',
            'readonly': 'readonly',
            'style': 'cursor: not-allowed;'
        })
        for field in self.fields:
            if field != 'codigo' and field != 'tipo':
                self.fields[field].widget.attrs.update({'class': 'form-control bg-dark text-white border-secondary'})
        if 'tipo' in self.fields:
            self.fields['tipo'].widget = forms.Select(choices=[
                ('MATERIAL', 'EM - Material'),
                ('ACTIVOS', 'EA - Activo'),
                ('DIRECTO AL GASTO', 'EDG - Directo al Gasto')
            ], attrs={'class': 'form-select bg-dark text-white border-secondary'})

    class Meta:
        model = Material
        fields = ['codigo', 'descripcion', 'tipo', 'unidad_medida', 'cargo', 'ubicacion', 'nro_parte']
        exclude = ['stock_actual']

class ActivoUpdateForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(ActivoUpdateForm, self).__init__(*args, **kwargs)
        # Código de activo inmutable para mantener consistencia histórica
        self.fields['codigo_activo'].widget.attrs.update({
            'class': 'form-control bg-secondary text-white border-secondary',
            'readonly': 'readonly',
            'style': 'cursor: not-allowed;'
        })
        for field in self.fields:
            if field != 'codigo_activo':
                self.fields[field].widget.attrs.update({'class': 'form-control bg-dark text-white border-secondary'})

    class Meta:
        model = Activo
        fields = ['codigo_activo', 'descripcion', 'marca', 'modelo', 'serial', 'unidad_medida_ac', 'nro_parte_ac', 'cargo_ac', 'ubicacion']
        exclude = ['stock']
