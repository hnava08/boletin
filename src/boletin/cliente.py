import json
from datetime import date
from typing import Optional

import httpx

from boletin.errores import CiudadNoEncontrada, RespuestaInesperada, ServicioNoDisponible
from boletin.modelos import Clima, Dia, Hora, Tablero

DIAS = "lun mar mié jue vie sáb dom".split()

GEO = "https://geocoding-api.open-meteo.com/v1/search"
PRONOSTICO = "https://api.open-meteo.com/v1/forecast"

CIELOS = {
    0: "despejado",
    1: "mayormente despejado",
    2: "parcialmente nublado",
    3: "nublado",
    45: "niebla",
    48: "niebla",
    51: "llovizna",
    53: "llovizna",
    55: "llovizna",
    56: "llovizna helada",
    57: "llovizna helada",
    61: "lluvia",
    63: "lluvia",
    65: "lluvia fuerte",
    66: "lluvia helada",
    67: "lluvia helada",
    71: "nieve",
    73: "nieve",
    75: "nieve",
    77: "nieve",
    80: "chubascos",
    81: "chubascos",
    82: "chubascos fuertes",
    85: "chubascos de nieve",
    86: "chubascos de nieve",
    95: "tormenta",
    96: "tormenta",
    99: "tormenta",
}


class Cliente:
    def __init__(self, transporte: Optional[httpx.BaseTransport] = None, tiempo: float = 5.0, reintentos: int = 1):
        self._reintentos = reintentos
        self._http = httpx.Client(
            transport=transporte,
            timeout=tiempo,
            headers={"User-Agent": "boletin/0.1"},
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "Cliente":
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    def clima(self, ciudad: str, pais: Optional[str] = None) -> Clima:
        nombre = ciudad.strip()
        if not nombre:
            raise CiudadNoEncontrada("Falta el nombre de la ciudad.")
        codigo = pais.strip().upper() if pais else None
        if codigo is not None and len(codigo) != 2:
            raise CiudadNoEncontrada("El país se indica con dos letras, por ejemplo BO.")
        lugar = self._lugar(nombre, codigo)
        return self._clima_de(self._pronostico(lugar, False))

    def tablero(self, ciudad: str, pais: Optional[str] = None) -> Tablero:
        nombre = ciudad.strip()
        if not nombre:
            raise CiudadNoEncontrada("Falta el nombre de la ciudad.")
        codigo = pais.strip().upper() if pais else None
        if codigo is not None and len(codigo) != 2:
            raise CiudadNoEncontrada("El país se indica con dos letras, por ejemplo BO.")
        lugar = self._lugar(nombre, codigo)
        datos = self._pronostico(lugar, True)
        clima = self._clima_de(datos)
        horas, indice = self._horas(datos, clima.observado)
        return Tablero(
            clima=clima,
            hallazgo=armar_hallazgo(clima.temperatura_c, horas, indice, self._lluvia(datos, clima.observado)),
            horas=tuple(horas),
            ahora_indice=indice,
            ahora_etiqueta="Ahora " + clima.observado[11:16],
            dias=tuple(self._dias(datos, clima.observado[:10])),
        )

    def _lugar(self, ciudad: str, pais: Optional[str]) -> dict:
        params = {"name": ciudad, "count": 20, "language": "es", "format": "json"}
        if pais:
            params["countryCode"] = pais
        datos = self._pedir(GEO, params)
        resultados = datos.get("results") or []
        if not resultados:
            raise CiudadNoEncontrada(f"No hay una ciudad llamada {ciudad}.")
        return max(resultados, key=lambda fila: fila.get("population") or 0)

    def _pronostico(self, lugar: dict, completo: bool) -> dict:
        try:
            latitud = lugar["latitude"]
            longitud = lugar["longitude"]
            zona = lugar["timezone"]
        except KeyError as exc:
            raise RespuestaInesperada("Open-Meteo devolvió un lugar incompleto.") from exc
        params = {
            "latitude": latitud,
            "longitude": longitud,
            "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m,is_day",
            "timezone": zona,
            "wind_speed_unit": "kmh",
        }
        if completo:
            params["hourly"] = "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation_probability"
            params["daily"] = "weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset"
            params["forecast_days"] = 7
        datos = self._pedir(PRONOSTICO, params)
        datos["_lugar"] = lugar
        return datos

    def _clima_de(self, datos: dict) -> Clima:
        lugar = datos["_lugar"]
        actual = datos.get("current")
        if not isinstance(actual, dict):
            raise RespuestaInesperada("Open-Meteo no trajo el clima actual.")
        try:
            codigo = int(actual["weather_code"])
            observado = str(actual["time"])
            cielo = CIELOS.get(codigo, f"código {codigo}")
            if actual.get("is_day") is None:
                reloj = _reloj(observado)
                es_dia = reloj is not None and 6 * 60 <= reloj < 19 * 60
            else:
                es_dia = bool(int(actual["is_day"]))
            salida, puesta = self._sol(datos, observado)
            return Clima(
                ciudad=str(lugar.get("name") or ""),
                pais=str(lugar.get("country_code") or ""),
                region=str(lugar.get("admin1") or ""),
                temperatura_c=float(actual["temperature_2m"]),
                humedad=int(actual["relative_humidity_2m"]),
                viento_kmh=float(actual["wind_speed_10m"]),
                cielo=cielo,
                observado=observado,
                es_dia=es_dia,
                momento=momento_de(observado, es_dia, salida, puesta),
                escena=escena_de(cielo),
                salida=salida,
                puesta=puesta,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RespuestaInesperada("Open-Meteo no trajo el clima actual.") from exc

    def _horas(self, datos: dict, observado: str):
        hourly = datos.get("hourly") or {}
        tiempos = hourly.get("time") or []
        temps = hourly.get("temperature_2m") or []
        humedades = hourly.get("relative_humidity_2m") or []
        vientos = hourly.get("wind_speed_10m") or []
        probs = hourly.get("precipitation_probability") or []
        dia = observado[:10]
        horas = []
        indice = 0
        hora_actual = observado[11:13]
        for i, (momento, temp) in enumerate(zip(tiempos, temps)):
            if not str(momento).startswith(dia):
                continue
            etiqueta = str(momento)[11:16]
            if etiqueta[:2] == hora_actual:
                indice = len(horas)
            horas.append(Hora(
                etiqueta=etiqueta,
                temperatura_c=float(temp),
                humedad=_entero(humedades, i),
                viento_kmh=_decimal(vientos, i),
                lluvia=_entero(probs, i),
            ))
        if not horas:
            raise RespuestaInesperada("Open-Meteo no trajo las horas del día.")
        return horas, indice

    def _lluvia(self, datos: dict, observado: str):
        hourly = datos.get("hourly") or {}
        tiempos = hourly.get("time") or []
        probs = hourly.get("precipitation_probability") or []
        dia = observado[:10]
        corte = observado[:16]
        salidas = []
        for momento, prob in zip(tiempos, probs):
            texto = str(momento)
            if texto.startswith(dia) and texto[:16] >= corte and prob is not None and int(prob) >= 40:
                salidas.append(texto[11:16])
        return salidas

    def _dias(self, datos: dict, hoy: str):
        daily = datos.get("daily") or {}
        fechas = daily.get("time") or []
        maximas = daily.get("temperature_2m_max") or []
        minimas = daily.get("temperature_2m_min") or []
        codigos = daily.get("weather_code") or []
        if not fechas:
            raise RespuestaInesperada("Open-Meteo no trajo los días.")
        salida = []
        for fecha, maxima, minima, codigo in zip(fechas, maximas, minimas, codigos):
            marca = date.fromisoformat(str(fecha))
            salida.append(
                Dia(
                    etiqueta=f"{DIAS[marca.weekday()]} {marca.day}",
                    cielo=CIELOS.get(int(codigo), f"código {codigo}"),
                    minima=float(minima),
                    maxima=float(maxima),
                    hoy=str(fecha) == hoy,
                )
            )
        return salida

    def _sol(self, datos: dict, observado: str):
        daily = datos.get("daily") or {}
        fechas = [str(fecha) for fecha in (daily.get("time") or [])]
        dia = observado[:10]
        if dia not in fechas:
            return "", ""
        indice = fechas.index(dia)
        salidas = daily.get("sunrise") or []
        puestas = daily.get("sunset") or []
        salida = salidas[indice] if indice < len(salidas) else ""
        puesta = puestas[indice] if indice < len(puestas) else ""
        return _hora(salida), _hora(puesta)

    def _pedir(self, url: str, params: dict) -> dict:
        intento = 0
        while True:
            try:
                respuesta = self._http.get(url, params=params)
            except httpx.TransportError as exc:
                if intento >= self._reintentos:
                    raise ServicioNoDisponible("Open-Meteo no respondió.") from exc
                intento += 1
                continue
            if respuesta.status_code == 429 or respuesta.status_code >= 500:
                if intento >= self._reintentos:
                    raise ServicioNoDisponible("Open-Meteo no respondió.")
                intento += 1
                continue
            if respuesta.status_code >= 400:
                raise RespuestaInesperada("Open-Meteo rechazó la consulta.")
            try:
                datos = respuesta.json()
            except json.JSONDecodeError as exc:
                raise RespuestaInesperada("Open-Meteo devolvió una respuesta ilegible.") from exc
            if not isinstance(datos, dict):
                raise RespuestaInesperada("Open-Meteo devolvió una respuesta ilegible.")
            return datos


ESCENAS = {
    "despejado": "despejado",
    "mayormente despejado": "claro",
    "parcialmente nublado": "claro",
    "nublado": "nublado",
    "niebla": "niebla",
    "llovizna": "llovizna",
    "llovizna helada": "llovizna",
    "lluvia": "lluvia",
    "lluvia fuerte": "lluvia-fuerte",
    "lluvia helada": "lluvia",
    "nieve": "nieve",
    "chubascos": "chubascos",
    "chubascos fuertes": "lluvia-fuerte",
    "chubascos de nieve": "chubascos-nieve",
    "tormenta": "tormenta",
}


def _entero(serie, indice):
    if indice >= len(serie) or serie[indice] is None:
        return None
    return int(serie[indice])


def _decimal(serie, indice):
    if indice >= len(serie) or serie[indice] is None:
        return None
    return float(serie[indice])


def escena_de(cielo: str) -> str:
    return ESCENAS.get(cielo, "nublado")


def _reloj(texto: str) -> Optional[int]:
    if not texto:
        return None
    marca = str(texto)
    if "T" in marca and len(marca) >= 16:
        hora, minuto = marca[11:13], marca[14:16]
    elif len(marca) >= 5 and marca[2] == ":":
        hora, minuto = marca[0:2], marca[3:5]
    else:
        return None
    return int(hora) * 60 + int(minuto)


def _hora(texto) -> str:
    reloj = _reloj(str(texto or ""))
    if reloj is None:
        return ""
    return f"{reloj // 60:02d}:{reloj % 60:02d}"


def momento_de(observado: str, es_dia: bool, salida: str, puesta: str) -> str:
    ahora = _reloj(observado)
    sale = _reloj(salida)
    pone = _reloj(puesta)
    if ahora is not None and sale is not None and abs(ahora - sale) <= 40:
        return "amanecer"
    if ahora is not None and pone is not None and abs(ahora - pone) <= 40:
        return "atardecer"
    return "dia" if es_dia else "noche"


def _grados(valor: float) -> str:
    return f"{valor:.1f}".replace(".", ",")


def armar_hallazgo(actual: float, horas, indice: int, lluvias) -> str:
    resto = list(horas[indice:]) or list(horas)
    pico = max(resto, key=lambda hora: hora.temperatura_c)
    piso = min(resto, key=lambda hora: hora.temperatura_c)
    if pico.temperatura_c >= actual + 0.5 and pico.etiqueta != resto[0].etiqueta:
        frase = f"Sigue subiendo: lo más alto que queda es {_grados(pico.temperatura_c)} °C a las {pico.etiqueta}."
    else:
        frase = f"Lo más cálido del tramo ya pasó. De aquí baja hasta {_grados(piso.temperatura_c)} °C a las {piso.etiqueta}."
    if lluvias:
        frase = frase[:-1] + f", con chance de lluvia a las {lluvias[0]}."
    return frase
