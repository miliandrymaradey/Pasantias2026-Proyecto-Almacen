import os

path = r'd:\Usuarios\Miliandry\OneDrive\Desktop\PROYECTO_ALMACEN\Pasantias2026-Proyecto-Almacen\inventario\models.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Definición del nuevo modelo GastoDirecto (antes de DetalleRecepcion)
gasto_directo_model = """
# ==========================================
# 1C. REGISTRO DE GASTO DIRECTO (EDG)
# ==========================================
class GastoDirecto(models.Model):
    \"\"\"
    Modelo para el catálogo de artículos 'Directo al Gasto' (EDG).
    Conectado a la tabla manual 'inventario_DG' en Supabase.
    \"\"\"
    codigo_dg = models.CharField(max_length=50, unique=True, verbose_name="Código DG")
    descripcion = models.CharField(max_length=255, verbose_name="Descripción")
    unidad_medida_dg = models.CharField(max_length=20, verbose_name="U.M.")
    nro_parte_dg = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nro. Parte")
    cargo_dg = models.CharField(max_length=50, verbose_name="Cargo")
    stock = models.IntegerField(default=0, verbose_name="Stock")

    class Meta:
        db_table = 'inventario_DG'
        managed = False # La tabla ya existe en Supabase
        verbose_name = "Artículo Directo al Gasto"
        verbose_name_plural = "1C. Catálogo de Gasto Directo (EDG)"

    def __str__(self):
        return f"{self.codigo_dg} - {self.descripcion}"
"""

# Insertamos GastoDirecto antes de DetalleRecepcion (que empieza en la línea 237 aprox)
if "class GastoDirecto" not in content:
    content = content.replace("class DetalleRecepcion", gasto_directo_model + "\n\nclass DetalleRecepcion")

# 2. Actualizar DetalleRecepcion (max_length y FK)
# Buscamos tipo_ingreso
content = content.replace("tipo_ingreso = models.CharField(max_length=10", "tipo_ingreso = models.CharField(max_length=30")

# Buscamos donde insertar la FK (después de material o activo)
if "gasto_directo =" not in content:
    content = content.replace("activo = models.ForeignKey(Activo", "gasto_directo = models.ForeignKey(GastoDirecto, on_delete=models.SET_NULL, null=True, blank=True, related_name='entradas', verbose_name='Gasto Directo (Cód. DG)')\n    activo = models.ForeignKey(Activo")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
