import httpx

from boletin import CiudadNoEncontrada, Cliente, RespuestaInesperada, ServicioNoDisponible
from boletin.cli import formatear
from boletin.modelos import Clima


LUGAR = {
    "name": "Santa Cruz de la Sierra",
    "country_code": "BO",
    "admin1": "Departamento de Santa Cruz",
    "latitude": -17.78,
    "longitude": -63.18,
    "timezone": "America/La_Paz",
    "population": 1831434,
}

ACTUAL = {
    "time": "2026-10-28T18:15",
    "temperature_2m": 19.9,
    "relative_humidity_2m": 82,
    "weather_code": 3,
    "wind_speed_10m": 13.6,
}


def transporte(handler):
    return httpx.MockTransport(handler)


def test_elige_la_ciudad_mas_poblada_y_oculta_las_dos_apis():
    vistos = []

    def handler(request: httpx.Request) -> httpx.Response:
        vistos.append(request.url.host)
        if "geocoding" in request.url.host:
            assert request.url.params["countryCode"] == "BO"
            return httpx.Response(
                200,
                json={
                    "results": [
                        {**LUGAR, "name": "Santa Cruz", "population": None, "admin1": "Beni"},
                        LUGAR,
                    ]
                },
            )
        assert request.url.params["latitude"] == "-17.78"
        assert request.url.params["wind_speed_unit"] == "kmh"
        return httpx.Response(200, json={"current": ACTUAL})

    with Cliente(transporte=transporte(handler)) as cliente:
        parte = cliente.clima("santa cruz", "bo")

    assert vistos == ["geocoding-api.open-meteo.com", "api.open-meteo.com"]
    assert parte.ciudad == "Santa Cruz de la Sierra"
    assert parte.pais == "BO"
    assert parte.cielo == "nublado"
    assert parte.temperatura_c == 19.9
    assert "Santa Cruz de la Sierra, Departamento de Santa Cruz" in formatear(parte)


def test_ciudad_desconocida():
    def handler(_request):
        return httpx.Response(200, json={"results": []})

    with Cliente(transporte=transporte(handler)) as cliente:
        try:
            cliente.clima("Ninguna")
        except CiudadNoEncontrada:
            return
    raise AssertionError("debía fallar")


def test_reintenta_un_cinco_y_luego_lee():
    llamadas = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if "geocoding" in request.url.host:
            return httpx.Response(200, json={"results": [LUGAR]})
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            return httpx.Response(503, json={"reason": "ocupado"})
        return httpx.Response(200, json={"current": ACTUAL})

    with Cliente(transporte=transporte(handler)) as cliente:
        parte = cliente.clima("Santa Cruz", "BO")
    assert llamadas["n"] == 2
    assert parte.humedad == 82


def test_si_sigue_caido_avisa_sin_el_cuerpo_remoto():
    def handler(request: httpx.Request) -> httpx.Response:
        if "geocoding" in request.url.host:
            return httpx.Response(500, text="falla interna secreta")
        return httpx.Response(200, json={"current": ACTUAL})

    with Cliente(transporte=transporte(handler)) as cliente:
        try:
            cliente.clima("Santa Cruz")
        except ServicioNoDisponible as exc:
            assert "secreta" not in str(exc)
            return
    raise AssertionError("debía fallar")


def test_el_hallazgo_sale_de_las_horas():
    from boletin.cliente import armar_hallazgo
    from boletin.modelos import Hora

    horas = (
        Hora("16:00", 24.0),
        Hora("17:00", 27.4),
        Hora("18:00", 19.9),
        Hora("21:00", 17.2),
    )
    sube = armar_hallazgo(19.0, horas, 0, [])
    assert "27,4" in sube and "17:00" in sube
    baja = armar_hallazgo(19.9, horas, 2, ["21:00"])
    assert "17,2" in baja and "21:00" in baja and "lluvia" in baja


def test_el_parte_sabe_si_es_de_noche():
    from boletin.cliente import escena_de, momento_de

    assert escena_de("chubascos de nieve") == "chubascos-nieve"
    assert momento_de("2026-10-28T21:10", False, "05:41", "18:22") == "noche"
    assert momento_de("2026-10-28T05:55", True, "2026-10-28T05:41", "2026-10-28T18:22") == "amanecer"
    assert momento_de("2026-10-28T18:10", True, "05:41", "18:22") == "atardecer"
    assert momento_de("2026-10-28T12:00", True, "05:41", "18:22") == "dia"

    def handler(request: httpx.Request) -> httpx.Response:
        if "geocoding" in request.url.host:
            return httpx.Response(200, json={"results": [LUGAR]})
        assert "is_day" in request.url.params["current"]
        assert "sunrise" in request.url.params["daily"]
        assert "relative_humidity_2m" in request.url.params["hourly"]
        horas = [f"2026-10-28T{hora:02d}:00" for hora in range(24)]
        return httpx.Response(
            200,
            json={
                "current": {**ACTUAL, "time": "2026-10-28T21:10", "is_day": 0, "weather_code": 0, "temperature_2m": 16.2},
                "hourly": {
                    "time": horas,
                    "temperature_2m": [20.0] * 24,
                    "relative_humidity_2m": [40] * 24,
                    "wind_speed_10m": [5.5] * 24,
                    "precipitation_probability": [0] * 24,
                },
                "daily": {
                    "time": ["2026-10-28"],
                    "weather_code": [0],
                    "temperature_2m_max": [28.0],
                    "temperature_2m_min": [16.0],
                    "sunrise": ["2026-10-28T05:41"],
                    "sunset": ["2026-10-28T18:22"],
                },
            },
        )

    with Cliente(transporte=transporte(handler)) as cliente:
        parte = cliente.tablero("Santa Cruz", "BO")
    assert parte.clima.momento == "noche"
    assert parte.clima.escena == "despejado"
    assert parte.clima.salida == "05:41"
    assert parte.clima.puesta == "18:22"
    assert parte.ahora_indice == 21
    assert parte.horas[21].humedad == 40
    assert parte.horas[21].viento_kmh == 5.5
    assert parte.horas[21].lluvia == 0


def test_respuesta_ilegible():
    def handler(_request):
        return httpx.Response(200, content=b"no-es-json")

    with Cliente(transporte=transporte(handler)) as cliente:
        try:
            cliente.clima("Santa Cruz")
        except RespuestaInesperada:
            return
    raise AssertionError("debía fallar")
