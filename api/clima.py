import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from boletin.web import consultar  # noqa: E402

ESTATICO = RAIZ / "src" / "boletin" / "estatico"
ARCHIVOS = {
    "/": (ESTATICO / "index.html", "text/html; charset=utf-8"),
    "/index.html": (ESTATICO / "index.html", "text/html; charset=utf-8"),
    "/charts.js": (ESTATICO / "charts.js", "text/javascript; charset=utf-8"),
}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        ruta = urlparse(self.path)
        if ruta.path in ARCHIVOS:
            archivo, tipo = ARCHIVOS[ruta.path]
            cuerpo = archivo.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)
            return
        consulta = parse_qs(ruta.query)
        ciudad = (consulta.get("ciudad") or [""])[0]
        pais = (consulta.get("pais") or [""])[0] or None
        estado, cuerpo = consultar(ciudad, pais)
        datos = json.dumps(cuerpo).encode()
        self.send_response(estado)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)
