from .models import SalidaMaterial
from django import forms
from .models import ReporteRecepcion, DetalleRecepcion
from .models import GuiaTraslado

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
        fields = ['material', 'nro_odc', 'nro_nota_entrega', 'proveedor', 'cantidad_solicitada', 'cantidad_recibida', 'precio_unitario', 'observaciones']
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
        }

class SalidaMaterialForm(forms.ModelForm):
    class Meta:
        model = SalidaMaterial
        fields = ['fecha_despacho', 'nro_rim', 'material', 'cantidad', 'centro_costo', 'cuenta_contable', 'partida_presupuestaria']
        widgets = {
            'fecha_despacho': forms.DateInput(attrs={'type': 'date', 'class': 'form-control bg-dark text-white border-secondary'}),
            'nro_rim': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Ej. RIM-001'}),
            'material': forms.Select(attrs={'class': 'form-select bg-dark text-white border-secondary'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'centro_costo': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Ej. PRV-1 / MANT...'}),
            'cuenta_contable': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'partida_presupuestaria': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary', 'placeholder': 'Ej. Consumibles...'}),
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