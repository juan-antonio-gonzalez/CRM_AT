from enum import Enum


class VisitStatus(str, Enum):
    PROGRAMADA = "Programada"
    FINALIZADA = "Finalizada"
    CANCELADA = "Cancelada"


class TrackingStatus(str, Enum):
    PENDIENTE = "Pendiente"
    EN_CURSO = "En curso"
    FINALIZADO = "Finalizado"
    CANCELADO = "Cancelado"


class SurveyStatus(str, Enum):
    PENDIENTE = "Pendiente"
    EN_PROCESO = "En Proceso"
    COMPLETADO = "Completado"
    BORRADOR = "Borrador"


class RelevamientoStatus(str, Enum):
    PENDIENTE = "Pendiente"
    EN_PROCESO = "En Proceso"
    COMPLETADO = "Completado"


class CustomerStatus(str, Enum):
    CLIENTE = "Cliente"
    PROSPECTO = "Prospecto"


class ProductStatus(str, Enum):
    ACTIVO = "Activo"
    INACTIVO = "Inactivo"
