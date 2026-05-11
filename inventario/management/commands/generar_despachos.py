import random
import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from inventario.models import (
    Material, CentroCosto, SalidaMaterial, 
    SalidaMaterialDetalle, DetalleRecepcion, PresupuestoAnual
)

class Command(BaseCommand):
    help = 'Genera 50 despachos simulados para pruebas de estrés de la tabla de Consumo Anual.'

    def handle(self, *args, **options):
        # 1. Verificación de Pre-requisitos
        materiales = list(Material.objects.all())
        centros = list(CentroCosto.objects.all())

        if not materiales:
            self.stdout.write(self.style.ERROR('Error: No hay Materiales registrados. Cree uno antes de continuar.'))
            return
        
        if not centros:
            self.stdout.write(self.style.ERROR('Error: No hay Centros de Costo registrados. Cree uno antes de continuar.'))
            return

        self.stdout.write(self.style.WARNING('Iniciando la generación de 50 registros de prueba...'))
        
        año_actual = datetime.date.today().year
        departamentos_demo = ['AIT', 'SIAHO', 'OPERACIONES', 'LOGISTICA', 'GERENCIA']
        creados = 0

        for i in range(50):
            try:
                with transaction.atomic():
                    # Selección aleatoria
                    material = random.choice(materiales)
                    centro = random.choice(centros)
                    departamento = random.choice(departamentos_demo)
                    
                    # Generación de cantidad y fecha aleatoria
                    cantidad = Decimal(random.randint(1, 15))
                    mes = random.randint(1, 12)
                    dia = random.randint(1, 28)
                    fecha_simulada = datetime.date(año_actual, mes, dia)

                    # Formato de RIM válido: DPT-000-AÑO
                    prefix = departamento[:3].upper() if len(departamento) >= 3 else "RIM"
                    nro_rim = f"{prefix}-{random.randint(100, 999)}-{año_actual}"

                    # --- GARANTÍA DE STOCK FIFO PARA LA PRUEBA ---
                    # Para que el método save() de SalidaMaterial no falle, 
                    # nos aseguramos de que el material tenga al menos un lote con stock.
                    lote_disponible = material.entradas.filter(cantidad_recibida__gt=0).first()
                    
                    if not lote_disponible:
                        # Si no hay stock, creamos un "Lote de Inyección QA"
                        lote_disponible = DetalleRecepcion.objects.create(
                            material=material,
                            nro_odc=f"ODC-QA-{random.randint(1000, 9999)}",
                            cantidad_recibida=Decimal('1000.00'),
                            fecha_recepcion=datetime.date(año_actual, 1, 1),
                            precio_unitario=Decimal(random.uniform(10.0, 500.0)).quantize(Decimal('0.00'))
                        )
                        # Actualizamos el stock maestro para que pase el clean()
                        material.stock_actual += Decimal('1000.00')
                        material.save()

                    # Creación del objeto SalidaMaterial
                    # El método save() disparará automáticamente la creación de SalidaMaterialDetalle
                    despacho = SalidaMaterial(
                        material=material,
                        fecha_despacho=fecha_simulada,
                        nro_rim=nro_rim,
                        cantidad=cantidad,
                        departamento=departamento,
                        centro_costo=centro,
                        nro_sm=f"SM-{random.randint(10000, 99999)}",
                        # Campos contables simulados
                        cuenta_contable=f"4.1.02.{random.randint(10, 99)}",
                        descripcion_cuenta=f"Gasto Operativo - {departamento}",
                        partida_presupuestaria=f"3.02.{random.randint(100, 999)}",
                        rubro_1="MATERIALES DE CONSUMO",
                        rubro_2="OPERACIONES VENEZUELA"
                    )
                    
                    # Ejecutamos el guardado (esto resta stock y crea detalles FIFO)
                    despacho.save()
                    creados += 1

            except Exception as e:
                self.stdout.write(self.style.NOTICE(f'Omitiendo registro {i+1} por validación: {e}'))

        self.stdout.write(self.style.SUCCESS(f'¡Éxito! Se han inyectado {creados} despachos simulados en el sistema.'))
        self.stdout.write(self.style.MIGRATE_LABEL('Ahora puede verificar los resultados en el módulo de Consumo Anual.'))
