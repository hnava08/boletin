import json
import os
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from boletin.cliente import Cliente
from boletin.errores import CiudadNoEncontrada, RespuestaInesperada, ServicioNoDisponible

PAGINA = Path(__file__).with_name("estatico") / "index.html"
PUERTO = int(os.environ.get("BOLETIN_PUERTO", "8020"))


class Parte(BaseHTTPRequestHandler):
    def do_GET(self):
        ruta = urlparse(self.path)
        if ruta.path == "/api/clima":
            self._clima(parse_qs(ruta.query))
            return
        if ruta.path == "/charts.js":
            self._archivo(PAGINA.parent / "charts.js", "text/javascript; charset=utf-8")
            return
        if ruta.path in ("/", "/index.html"):
            self._archivo(PAGINA, "text/html; charset=utf-8")
            return
        self.send_error(404)

    def _clima(self, consulta):
        ciudad = (consulta.get("ciudad") or [""])[0]
        pais = (consulta.get("pais") or [""])[0] or None
        estado, cuerpo = consultar(ciudad, pais)
        self._json(estado, cuerpo)

    def _json(self, status, datos):
        cuerpo = json.dumps(datos).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _archivo(self, ruta: Path, tipo: str):
        cuerpo = ruta.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def log_message(self, _formato, *_args):
        return


def consultar(ciudad, pais):
    try:
        with Cliente() as cliente:
            parte = cliente.tablero(ciudad, pais)
    except CiudadNoEncontrada as exc:
        return 404, {"error": str(exc)}
    except ServicioNoDisponible as exc:
        return 503, {"error": str(exc)}
    except RespuestaInesperada as exc:
        return 502, {"error": str(exc)}
    return 200, asdict(parte)


def main():
    servidor = ThreadingHTTPServer(("127.0.0.1", PUERTO), Parte)
    print(f"Boletín en http://127.0.0.1:{PUERTO}")
    servidor.serve_forever()
