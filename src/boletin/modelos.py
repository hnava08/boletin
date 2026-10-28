from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class Hora:
    etiqueta: str
    temperatura_c: float
    humedad: Optional[int] = None
    viento_kmh: Optional[float] = None
    lluvia: Optional[int] = None


@dataclass(frozen=True)
class Dia:
    etiqueta: str
    cielo: str
    minima: float
    maxima: float
    hoy: bool


@dataclass(frozen=True)
class Tablero:
    clima: "Clima"
    hallazgo: str
    horas: Tuple[Hora, ...]
    ahora_indice: int
    ahora_etiqueta: str
    dias: Tuple[Dia, ...]


@dataclass(frozen=True)
class Clima:
    ciudad: str
    pais: str
    region: str
    temperatura_c: float
    humedad: int
    viento_kmh: float
    cielo: str
    observado: str
    es_dia: bool = True
    momento: str = "dia"
    escena: str = "nublado"
    salida: str = ""
    puesta: str = ""
