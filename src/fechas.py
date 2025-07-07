from datetime import datetime

# Fecha de inicio (formato: 'YYYY-MM-DD')
fecha_inicio_str = "2025-02-14"
fecha_inicio = datetime.strptime(fecha_inicio_str, "%Y-%m-%d")

# Fecha de fin (formato: 'YYYY-MM-DD')
fecha_fin_str = "2025-08-22"  # Cambia esta fecha según necesites
fecha_fin = datetime.strptime(fecha_fin_str, "%Y-%m-%d")

# Fecha de hoy
hoy = datetime.today()

# Diferencia en días
dias_diferencia = (fecha_fin - fecha_inicio).days

# Cantidad de semanas completas
semanas = dias_diferencia / 7

print(f"Han pasado {semanas} semanas desde {fecha_inicio_str} hasta {fecha_fin_str}.")
print(f"(Total de {dias_diferencia} días)")