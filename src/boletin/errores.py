class BoletinError(Exception):
    pass


class CiudadNoEncontrada(BoletinError):
    pass


class ServicioNoDisponible(BoletinError):
    pass


class RespuestaInesperada(BoletinError):
    pass
