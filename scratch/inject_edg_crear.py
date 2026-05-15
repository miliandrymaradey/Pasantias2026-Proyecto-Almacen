import os

path = r'd:\Usuarios\Miliandry\OneDrive\Desktop\PROYECTO_ALMACEN\Pasantias2026-Proyecto-Almacen\inventario\views.py'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if 'detalle.save()' in line and i < 450 and 'crear_recepcion' in ''.join(lines[331:i]):
        # We found the end of the loop in crear_recepcion
        new_lines.append(line)
        # Check if the next non-empty line is the return redirect
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j < len(lines) and 'return redirect(\'lista_entradas\')' in lines[j]:
            # Add the EDG block
            new_lines.append("\n")
            new_lines.append("                # B. Procesar ítems desde Arrays Directos (POST dinámico EDG)\n")
            new_lines.append("                if codigos_edg:\n")
            new_lines.append("                    descripciones_edg = request.POST.getlist('descripcion_edg[]')\n")
            new_lines.append("                    ums_edg = request.POST.getlist('um_edg[]')\n")
            new_lines.append("                    cargos_edg = request.POST.getlist('cargo_edg[]')\n")
            new_lines.append("                    cantidades_edg = request.POST.getlist('cantidad_edg[]')\n")
            new_lines.append("                    precios_edg = request.POST.getlist('precio_edg[]')\n")
            new_lines.append("                    odcs_edg = request.POST.getlist('odc_edg[]')\n")
            new_lines.append("                    notas_edg = request.POST.getlist('nota_edg[]')\n")
            new_lines.append("\n")
            new_lines.append("                    for cod, desc, um, cargo, cant, precio, odc, nota in zip(\n")
            new_lines.append("                        codigos_edg, descripciones_edg, ums_edg, cargos_edg, \n")
            new_lines.append("                        cantidades_edg, precios_edg, odcs_edg, notas_edg\n")
            new_lines.append("                    ):\n")
            new_lines.append("                        if not cod or not desc: continue\n")
            new_lines.append("                        \n")
            new_lines.append("                        material_edg, _ = Material.objects.get_or_create(\n")
            new_lines.append("                            codigo=cod.strip().upper(),\n")
            new_lines.append("                            defaults={\n")
            new_lines.append("                                'descripcion': desc.strip().upper(),\n")
            new_lines.append("                                'tipo': 'DIRECTO AL GASTO',\n")
            new_lines.append("                                'unidad_medida': um.strip().upper(),\n")
            new_lines.append("                                'cargo': cargo.strip().upper(),\n")
            new_lines.append("                                'stock_actual': 0\n")
            new_lines.append("                            }\n")
            new_lines.append("                        )\n")
            new_lines.append("\n")
            new_lines.append("                        detalle = DetalleRecepcion(\n")
            new_lines.append("                            reporte=reporte,\n")
            new_lines.append("                            material=material_edg,\n")
            new_lines.append("                            tipo_ingreso='Directo al Gasto',\n")
            new_lines.append("                            nro_odc=odc.strip().upper(),\n")
            new_lines.append("                            fecha_recepcion=reporte.fecha_recepcion,\n")
            new_lines.append("                            cantidad_recibida=Decimal(cant or '0'),\n")
            new_lines.append("                            precio_unitario=Decimal(precio or '0'),\n")
            new_lines.append("                            nro_nota_entrega=nota.strip().upper()\n")
            new_lines.append("                        )\n")
            new_lines.append("                        detalle._tipo_entrada_manual = 'DIRECTO AL GASTO'\n")
            new_lines.append("                        detalle.save()\n")
    else:
        new_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
