"""Status vocabularies.

The application previously scattered ~40 status literals across routers and
services, and the enums disagreed with the values actually written to the
database. Two concrete examples of that drift:

* ``SurveyStatus`` declared ``"Completado"`` / ``"En Proceso"`` while
  ``TechnicalSurveyV2.status`` was written as ``"Finalizado"`` / ``"En proceso"``.
* ``TrackingStatus`` declared only ``"En curso"`` while ``tracking_service`` had
  to accept ``"en curso"``, ``"en_curso"``, ``"in_progress"``, ``"progress"`` and
  ``"en proceso"`` to survive free-text input.

These enums are the single source of truth. ``normalize_status`` maps legacy
free-text values onto them so existing rows keep working.
"""

from enum import Enum


class TrackingStatus(str, Enum):
    PENDIENTE = "Pendiente"
    EN_CURSO = "En curso"
    FINALIZADO = "Finalizado"
    CANCELADO = "Cancelado"


class SurveyStatus(str, Enum):
    """Surveys (V1 and V2). Values match what the forms actually submit."""

    PENDIENTE = "Pendiente"
    BORRADOR = "Borrador"
    EN_PROCESO = "En proceso"
    COMPLETADO = "Finalizado"  # V2 forms write "Finalizado"

    # Aliases kept so older code paths keep working.
    EN_PROCESO_LEGACY = "En Proceso"
    COMPLETADO_LEGACY = "Completado"


class RelevamientoStatus(str, Enum):
    PENDIENTE = "Pendiente"
    EN_PROCESO = "En Proceso"
    COMPLETADO = "Completado"


class VisitStatus(str, Enum):
    """TechnicalVisit2.status."""

    BORRADOR = "Borrador"
    PROGRAMADO = "Programado"
    FINALIZADO = "Finalizado"
    CANCELADO = "Cancelado"


class CustomerStatus(str, Enum):
    CLIENTE = "Activo"
    PROSPECTO = "Inactivo"


class ProductStatus(str, Enum):
    ACTIVO = "Activo"
    INACTIVO = "Inactivo"


# ── Normalisation ───────────────────────────────────────────────────────────
_TRACKING_SYNONYMS = {
    "pendiente": TrackingStatus.PENDIENTE.value,
    "pending": TrackingStatus.PENDIENTE.value,
    "en curso": TrackingStatus.EN_CURSO.value,
    "en_curso": TrackingStatus.EN_CURSO.value,
    "en proceso": TrackingStatus.EN_CURSO.value,
    "in_progress": TrackingStatus.EN_CURSO.value,
    "in progress": TrackingStatus.EN_CURSO.value,
    "progress": TrackingStatus.EN_CURSO.value,
    "finalizado": TrackingStatus.FINALIZADO.value,
    "completado": TrackingStatus.FINALIZADO.value,
    "done": TrackingStatus.FINALIZADO.value,
    "cancelado": TrackingStatus.CANCELADO.value,
    "cancelled": TrackingStatus.CANCELADO.value,
    "canceled": TrackingStatus.CANCELADO.value,
}

_SURVEY_SYNONYMS = {
    "pendiente": SurveyStatus.PENDIENTE.value,
    "borrador": SurveyStatus.BORRADOR.value,
    "draft": SurveyStatus.BORRADOR.value,
    "en proceso": SurveyStatus.EN_PROCESO.value,
    "en_proceso": SurveyStatus.EN_PROCESO.value,
    "en curso": SurveyStatus.EN_PROCESO.value,
    "in progress": SurveyStatus.EN_PROCESO.value,
    "finalizado": SurveyStatus.COMPLETADO.value,
    "completado": SurveyStatus.COMPLETADO.value,
    "terminado": SurveyStatus.COMPLETADO.value,
    "done": SurveyStatus.COMPLETADO.value,
}


def _normalize(value, synonyms: dict, default: str) -> str:
    if value is None:
        return default
    key = str(value).strip().lower()
    if not key:
        return default
    return synonyms.get(key, default)


def normalize_tracking_status(value) -> str:
    return _normalize(value, _TRACKING_SYNONYMS, TrackingStatus.PENDIENTE.value)


def normalize_survey_status(value) -> str:
    return _normalize(value, _SURVEY_SYNONYMS, SurveyStatus.PENDIENTE.value)


def tracking_status_options() -> list:
    """Distinct values for selectors."""
    return [s.value for s in TrackingStatus]


def survey_status_options() -> list:
    return [SurveyStatus.PENDIENTE.value, SurveyStatus.BORRADOR.value,
            SurveyStatus.EN_PROCESO.value, SurveyStatus.COMPLETADO.value]
