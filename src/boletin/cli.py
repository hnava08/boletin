import argparse
import sys

from boletin.cliente import Cliente
from boletin.errores import CiudadNoEncontrada, RespuestaInesperada, ServicioNoDisponible
from boletin.modelos import Clima


def formatear(parte: Clima) -> str:
    lugar = parte.ciudad
    if parte.region:
        lugar = f"{lugar}, {parte.region}"
    return (
        f"{lugar}\n"
        f"{parte.temperatura_c:.1f} °C · {parte.cielo}\n"
        f"Humedad {parte.humedad} % · viento {parte.viento_kmh:.1f} km/h\n"
        f"Observado {parte.observado}"
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="boletin", description="Clima actual de una ciudad.")
    parser.add_argument("ciudad", help="Nombre de la ciudad")
    parser.add_argument("--pais", help="Código de dos letras, por ejemplo BO")
    args = parser.parse_args(argv)
    cliente = Cliente()
    try:
        print(formatear(cliente.clima(args.ciudad, args.pais)))
        return 0
    except CiudadNoEncontrada as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except ServicioNoDisponible as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except RespuestaInesperada as exc:
        print(str(exc), file=sys.stderr)
        return 4
    finally:
        cliente.close()
