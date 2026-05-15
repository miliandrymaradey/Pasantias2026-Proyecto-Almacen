import os

path = r'd:\Usuarios\Miliandry\OneDrive\Desktop\PROYECTO_ALMACEN\Pasantias2026-Proyecto-Almacen\inventario\templates\inventario\reportes_pendientes.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = '''                        <td class="fw-bold text-success fs-5 bg-success bg-opacity-10">
                            ${{ item.valor_recibido|floatformat:2 }}
                        </td>

                    </tr>'''

new = '''                        <td class="fw-bold text-success fs-5 bg-success bg-opacity-10">
                            ${{ item.valor_recibido|floatformat:2 }}
                        </td>
                        <td>
                            <button type="button" 
                                class="btn btn-warning fw-bold text-dark shadow-sm btn-desglosar"
                                data-id="{{ item.id }}"
                                data-odc="{{ item.nro_odc }}"
                                data-proveedor="{{ item.proveedor }}"
                                data-nota="{{ item.nro_nota_entrega }}"
                                data-rq="{{ item.nro_rq|default:'' }}"
                                data-depto="{{ item.departamento|default:'' }}"
                                data-valor="{{ item.valor_recibido }}"
                                data-tipo="{{ item.tipo_ingreso }}">
                                <i class="bi bi-calculator me-1"></i> Desglosar
                            </button>
                        </td>
                    </tr>'''

new_content = content.replace(old, new)
with open(path, 'w', encoding='utf-8') as f:
    f.write(new_content)
