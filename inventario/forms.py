from .models import SalidaMaterial
from django import forms
from .models import ReporteRecepcion, DetalleRecepcion
from .models import GuiaTraslado, CentroCosto

class ReporteRecepcionForm(forms.ModelForm):
    class Meta:
        model = ReporteRecepcion
        fields = ['fecha_recepcion', 'descripcion']
        widgets = {
        
        'fecha_recepcion': forms.DateInput(attrs={'type': 'date', 'class': 'form-control bg-dark text-white border-secondary'}),
        'descripcion': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Ej. Recepción de repuestos mecánicos...'}),
        
        }

class DetalleRecepcionForm(forms.ModelForm):
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
            # Campo manual nuevo:
            'observaciones': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Opcional...'}),
            'nro_rq': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'departamento': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
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
        try:
            centros = CentroCosto.objects.all().order_by('nombre')
            opciones_centros = [('', '--- Seleccione ---')] + [(c.nombre, c.nombre) for c in centros]
        except:
            opciones_centros = [('', '--- Seleccione ---')]

        self.fields['centro_costo'] = forms.ChoiceField(
            choices=opciones_centros, required=False,
            label='Centro de Costo (Destino)',
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

        # --- PARTIDA PRESUPUESTARIA: menú vacío que JS puebla dinámicamente ---
        self.fields['partida_presupuestaria'] = forms.CharField(
            required=False,
            widget=forms.Select(attrs={
                'class': 'form-select bg-dark text-white border-secondary',
                'id': 'id_partida_presupuestaria'
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

    class Meta:
        model = SalidaMaterial
        fields = ['fecha_despacho', 'nro_rim', 'material', 'cantidad']
        widgets = {
            'fecha_despacho': forms.DateInput(attrs={'type': 'date', 'class': 'form-control bg-dark text-white border-secondary'}),
            'nro_rim': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Ej. RIM-001'}),
            'material': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
        }

class GuiaTrasladoForm(forms.ModelForm):
    class Meta:
        model = GuiaTraslado
        fields = ['taladro_destino', 'fecha', 'hora', 'direccion', 'ciudad', 'conductor', 'ci_conductor', 'vehiculo', 'color', 'placa', 'marca_modelo', 'observaciones', 'nombre_entregado']
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
            'marca_modelo': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control bg-dark text-white border-secondary', 'rows': 3}),
            'nombre_entregado': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
        }