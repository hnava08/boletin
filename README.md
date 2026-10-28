# Boletín

Cliente de Open-Meteo. Quien lo usa pide una ciudad y recibe el clima actual. El paquete hace la búsqueda y el pronóstico, y no deja salir la forma cruda de esas dos respuestas.

Harold Nava

## Instalar

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

El comando queda en el entorno:

```bash
.venv/bin/boletin "Santa Cruz" --pais BO
.venv/bin/boletin-pantalla
```

La pantalla queda en `http://127.0.0.1:8020`. Arriba está el cielo de la ciudad: cambia con el estado (despejado, nublado, lluvia, nieve, niebla, tormenta) y con la hora (día, noche, amanecer, atardecer). La salida y la puesta salen de Open-Meteo. Debajo, la curva de las horas y la mínima y máxima de siete días.

Desde Python:

```python
from boletin import Cliente

with Cliente() as cliente:
    parte = cliente.clima("Santa Cruz", "BO")

print(parte.ciudad, parte.temperatura_c, parte.cielo)
```

`pais` son dos letras. Con un nombre repetido, como Santa Cruz, hace falta: sin él, Open-Meteo puede devolver otra ciudad. Si hay varias en el mismo país, se queda la de mayor población.

## Qué esconde

La consulta pública son dos GET. El primero busca el lugar en `geocoding-api.open-meteo.com`. El segundo pide el clima actual, las horas del día y los siete días en `api.open-meteo.com`. El comando de terminal devuelve un `Clima`. La pantalla pide el parte completo: horas, días y una frase calculada a partir de esas horas.

Si el servicio responde 429 o 500, se reintenta una vez. Si sigue sin responder, sale `ServicioNoDisponible`. Un cuerpo ilegible sale como `RespuestaInesperada`. Una ciudad que no está sale como `CiudadNoEncontrada`. El comando devuelve 2, 3 o 4 en ese orden.

## Pruebas

```bash
.venv/bin/pytest
```

Las pruebas usan un transporte falso. No llaman a Open-Meteo.
