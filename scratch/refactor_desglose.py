import os

path = r'd:\Usuarios\Miliandry\OneDrive\Desktop\PROYECTO_ALMACEN\Pasantias2026-Proyecto-Almacen\inventario\templates\inventario\reportes_pendientes.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add EDG Inputs
old_html = '''                        <div class="col-md-3 mb-3">
                            <label id="label_item" class="form-label corp-label small fw-bold">Seleccionar Material</label>
                            
                            <!-- SELECT DE MATERIALES -->
                            <select id="select_material" class="form-select select2-generic">
                                <option value=""></option>
                                {% for m in materiales %}
                                <option value="{{ m.id }}" data-codigo="{{ m.codigo }}" data-desc="{{ m.descripcion }}" data-um="{{ m.unidad_medida }}">{{ m.codigo }} - {{ m.descripcion }}</option>
                                {% endfor %}
                            </select>

                            <!-- SELECT DE ACTIVOS (Oculto por defecto) -->
                            <select id="select_activo" class="form-select select2-generic" style="display: none;" disabled>
                                <option value=""></option>
                                {% for a in activos %}
                                <option value="{{ a.id }}" data-codigo="{{ a.codigo_activo }}" data-desc="{{ a.descripcion }}" data-um="UNID">{{ a.codigo_activo }} - {{ a.descripcion }}</option>
                                {% endfor %}
                            </select>
                        </div>'''

new_html = '''                        <div class="col-md-3 mb-3" id="col_selector_item">
                            <label id="label_item" class="form-label corp-label small fw-bold">Seleccionar Material</label>
                            
                            <!-- SELECT DE MATERIALES -->
                            <select id="select_material" class="form-select select2-generic">
                                <option value=""></option>
                                {% for m in materiales %}
                                <option value="{{ m.id }}" data-codigo="{{ m.codigo }}" data-desc="{{ m.descripcion }}" data-um="{{ m.unidad_medida }}">{{ m.codigo }} - {{ m.descripcion }}</option>
                                {% endfor %}
                            </select>

                            <!-- SELECT DE ACTIVOS (Oculto por defecto) -->
                            <select id="select_activo" class="form-select select2-generic" style="display: none;" disabled>
                                <option value=""></option>
                                {% for a in activos %}
                                <option value="{{ a.id }}" data-codigo="{{ a.codigo_activo }}" data-desc="{{ a.descripcion }}" data-um="UNID">{{ a.codigo_activo }} - {{ a.descripcion }}</option>
                                {% endfor %}
                            </select>
                        </div>

                        <!-- CAMPOS EDG (Ocultos por defecto) -->
                        <div class="col-md-2 mb-3 zona-edg-input" style="display:none;">
                            <label class="form-label corp-label small fw-bold">Código EDG</label>
                            <input type="text" id="id_codigo_edg" name="codigo_edg[]" class="form-control bg-dark text-white border-secondary" placeholder="Ej: EDG-001">
                        </div>
                        <div class="col-md-3 mb-3 zona-edg-input" style="display:none;">
                            <label class="form-label corp-label small fw-bold">Descripción EDG</label>
                            <input type="text" id="id_descripcion_edg" name="descripcion_edg[]" class="form-control bg-dark text-white border-secondary" placeholder="Describa el gasto...">
                        </div>
                        <div class="col-md-1 mb-3 zona-edg-input" style="display:none;">
                            <label class="form-label corp-label small fw-bold">U/M</label>
                            <input type="text" id="id_um_edg" name="um_edg[]" class="form-control bg-dark text-white border-secondary" placeholder="UND">
                        </div>
                        <div class="col-md-2 mb-3 zona-edg-input" style="display:none;">
                            <label class="form-label corp-label small fw-bold">Cargo</label>
                            <select id="id_cargo_edg" name="cargo_edg[]" class="form-select bg-dark text-white border-secondary">
                                <option value="OPERACIONES">OPERACIONES</option>
                                <option value="ADMINISTRACION">ADMINISTRACIÓN</option>
                                <option value="MANTENIMIENTO">MANTENIMIENTO</option>
                                <option value="TALADRO">TALADRO</option>
                            </select>
                        </div>'''

content = content.replace(old_html, new_html)

# 2. Refactor JS: btn-desglosar click
old_js_click = '''        monedero_actual = {
            id: btn.data('id'),
            odc: btn.data('odc'),
            proveedor: btn.data('proveedor'),
            nota: btn.data('nota'),
            rq: btn.data('rq'),
            depto: btn.data('depto'),
            valor: btn.data('valor'),
            em: btn.closest('tr').find('td:nth-child(2)').text().trim()
        };

        // --- LÓGICA DINÁMICA DE SELECCIÓN (EM vs EA) ---
        const prefix = monedero_actual.em.substring(0, 2);
        const label = document.getElementById('label_item');
        const sMaterial = $('#select_material');
        const sActivo = $('#select_activo');

        if (prefix === 'EA') {
            // Es un ACTIVO
            label.innerText = 'SELECCIONAR ACTIVO';
            sMaterial.next('.select2-container').hide();
            sMaterial.prop('disabled', true);
            
            sActivo.next('.select2-container').show();
            sActivo.prop('disabled', false);
        } else {
            // Es un MATERIAL (EM)
            label.innerText = 'SELECCIONAR MATERIAL';
            sActivo.next('.select2-container').hide();
            sActivo.prop('disabled', true);
            
            sMaterial.next('.select2-container').show();
            sMaterial.prop('disabled', false);
        }'''

new_js_click = '''        monedero_actual = {
            id: btn.data('id'),
            odc: btn.data('odc'),
            proveedor: btn.data('proveedor'),
            nota: btn.data('nota'),
            rq: btn.data('rq'),
            depto: btn.data('depto'),
            valor: btn.data('valor'),
            tipo: btn.data('tipo'),
            em: btn.closest('tr').find('td:nth-child(2)').text().trim()
        };

        // --- LÓGICA DINÁMICA DE SELECCIÓN (EM vs EA vs EDG) ---
        const prefix = monedero_actual.em.substring(0, 2);
        const label = document.getElementById('label_item');
        const sMaterial = $('#select_material');
        const sActivo = $('#select_activo');
        const es_edg = monedero_actual.tipo === 'Directo al Gasto';

        // Reset visibilidad
        $('#col_selector_item').show();
        $('.zona-edg-input').hide();
        sMaterial.prop('disabled', false);
        sActivo.prop('disabled', false);

        if (es_edg) {
            // Es DIRECTO AL GASTO
            label.innerText = 'DATOS DEL GASTO (NUEVOS ÍTEMS)';
            $('#col_selector_item').hide();
            $('.zona-edg-input').show();
            sMaterial.prop('disabled', true);
            sActivo.prop('disabled', true);
        } else if (prefix === 'EA') {
            // Es un ACTIVO
            label.innerText = 'SELECCIONAR ACTIVO';
            sMaterial.next('.select2-container').hide();
            sMaterial.prop('disabled', true);
            
            sActivo.next('.select2-container').show();
            sActivo.prop('disabled', false);
        } else {
            // Es un MATERIAL (EM)
            label.innerText = 'SELECCIONAR MATERIAL';
            sActivo.next('.select2-container').hide();
            sActivo.prop('disabled', true);
            
            sMaterial.next('.select2-container').show();
            sMaterial.prop('disabled', false);
        }'''

content = content.replace(old_js_click, new_js_click)

# 3. Refactor JS: btn_add_item click
old_js_add = '''    $('#btn_add_item').click(function() {
        // Detectar cuál select está activo
        let isActivo = $('#select_activo').is(':visible') || !$('#select_activo').prop('disabled');
        let currentSelect = isActivo ? $('#select_activo') : $('#select_material');
        
        let matId = currentSelect.val();
        let cant = $('#id_cantidad_recibida').val();
        let precio = $('#id_precio_unitario').val();

        if (!matId || !cant || cant <= 0) {
            alert("Seleccione un ítem y cantidad válida.");
            return;
        }

        let matOpt = currentSelect.find('option:selected');
        let item = {
            tipo_ingreso: isActivo ? 'Activo' : 'Material',
            material_id: isActivo ? null : matId,
            activo_id: isActivo ? matId : null,
            material: matOpt.text(),
            cantidad_recibida: cant,
            precio_unitario: precio,
            cantidad_solicitada: $('#id_cantidad_solicitada').val() || cant,
            nro_odc: monedero_actual.odc,
            proveedor: monedero_actual.proveedor,
            nro_nota_entrega: monedero_actual.nota,
            nro_rq: $('#id_rq_txt').val(),
            departamento: monedero_actual.depto
        };

        carrito_desglose.push(item);
        renderDesglose();

        // Reset campos item
        currentSelect.val(null).trigger('change');
        $('#id_cantidad_solicitada').val('');
        $('#id_cantidad_recibida').val('');
        $('#id_precio_unitario').val('');
        $('#subtotal_item').text('$0.00');
    });'''

new_js_add = '''    $('#btn_add_item').click(function() {
        const es_edg = monedero_actual.tipo === 'Directo al Gasto';
        let item = null;
        let cant = $('#id_cantidad_recibida').val();
        let precio = $('#id_precio_unitario').val();

        if (es_edg) {
            let cod = $('#id_codigo_edg').val();
            let desc = $('#id_descripcion_edg').val();
            let um = $('#id_um_edg').val();
            let cargo = $('#id_cargo_edg').val();

            if (!cod || !desc || !cant || cant <= 0) {
                alert("Complete todos los campos del gasto y una cantidad válida.");
                return;
            }

            item = {
                es_edg: true,
                requiere_rp: 'no',
                codigo_edg: cod,
                descripcion_edg: desc,
                um_edg: um,
                cargo_edg: cargo,
                material: cod + ' - ' + desc,
                cantidad_recibida: cant,
                precio_unitario: precio,
                cantidad_solicitada: $('#id_cantidad_solicitada').val() || cant,
                tipo_ingreso: 'Directo al Gasto'
            };
        } else {
            let isActivo = $('#select_activo').is(':visible') || !$('#select_activo').prop('disabled');
            let currentSelect = isActivo ? $('#select_activo') : $('#select_material');
            let matId = currentSelect.val();

            if (!matId || !cant || cant <= 0) {
                alert("Seleccione un ítem y cantidad válida.");
                return;
            }

            let matOpt = currentSelect.find('option:selected');
            item = {
                tipo_ingreso: isActivo ? 'Activo' : 'Material',
                material_id: isActivo ? null : matId,
                activo_id: isActivo ? matId : null,
                material: matOpt.text(),
                cantidad_recibida: cant,
                precio_unitario: precio,
                cantidad_solicitada: $('#id_cantidad_solicitada').val() || cant
            };
        }

        item.nro_odc = monedero_actual.odc;
        item.proveedor = monedero_actual.proveedor;
        item.nro_nota_entrega = monedero_actual.nota;
        item.nro_rq = $('#id_rq_txt').val();
        item.departamento = monedero_actual.depto;

        carrito_desglose.push(item);
        renderDesglose();

        if (es_edg) {
            $('#id_codigo_edg').val('');
            $('#id_descripcion_edg').val('');
            $('#id_um_edg').val('');
        } else {
            let currentSelect = $('#select_activo').is(':visible') ? $('#select_activo') : $('#select_material');
            currentSelect.val(null).trigger('change');
        }
        $('#id_cantidad_solicitada').val('');
        $('#id_cantidad_recibida').val('');
        $('#id_precio_unitario').val('');
        $('#subtotal_item').text('$0.00');
    });'''

content = content.replace(old_js_add, new_js_add)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
