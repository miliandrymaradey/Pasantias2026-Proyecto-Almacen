import re

file = 'inventario/migrations/0020_pilar_2_3_4_5_correcciones_v3.py'
with open(file, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace AddField for centro_costo_texto with RenameField
content = re.sub(
    r"migrations\.AddField\(\s*model_name='salidamaterial',\s*name='centro_costo_texto',\s*field=models\.CharField\(blank=True, max_length=100, null=True, verbose_name='Centro de Costo \(Texto\)'\),\s*\),",
    "migrations.RenameField(model_name='salidamaterial', old_name='centro_costo', new_name='centro_costo_texto'),",
    content
)

# Replace AlterField for centro_costo with AddField
content = re.sub(
    r"migrations\.AlterField\(\s*model_name='salidamaterial',\s*name='centro_costo',\s*field=models\.ForeignKey\(blank=True, null=True, on_delete=django\.db\.models\.deletion\.SET_NULL, related_name='salidas', to='inventario\.centrocosto', verbose_name='Centro de Costo'\),\s*\),",
    "migrations.AddField(model_name='salidamaterial', name='centro_costo', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='salidas', to='inventario.centrocosto', verbose_name='Centro de Costo')),",
    content
)

with open(file, 'w', encoding='utf-8') as f:
    f.write(content)
print('Migration fixed')
