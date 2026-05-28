def test_imports():
    import models
    import database
    import config
    import logger
    import security
    from enums import (
        VisitStatus, TrackingStatus, SurveyStatus,
        RelevamientoStatus, CustomerStatus, ProductStatus
    )
    assert VisitStatus.PROGRAMADA.value == "Programada"
    assert TrackingStatus.FINALIZADO.value == "Finalizado"


def test_models_import():
    from models import (
        Product, Customer, Machine, TechnicalVisit,
        User, ATAssignment, TechnicalSurvey, InfrastructureSurvey,
        ActionPlanTracking, TechnicalAdvisor, Designer,
        CommercialAdvisor, IndustrialSector, MachineType, VisitTopic,
    )
    assert User is not None


def test_schemas_import():
    from schemas.common import Message, ErrorResponse, SuccessResponse
    from schemas.user import UserOut, UserCreate, UserLogin
    from schemas.customer import CustomerDetail, KpiAssignment
    from schemas.product import ProductSearchResult, ProductCreate
    from schemas.visit import VisitEvent
    assert Message is not None


def test_utils():
    from utils import calculate_relevo_status
    result = calculate_relevo_status({
        "name": "Test", "plant": "P1", "industry_sector": "S1",
        "assigned_commercial": "C1", "technical_advisor": "A1",
        "designer": "D1", "address": "A1", "city": "C1", "observations": "O1"
    }, [{"name": "M1"}])
    assert result == "Completado"
    result = calculate_relevo_status({
        "name": "", "plant": "", "industry_sector": "", "assigned_commercial": "",
        "technical_advisor": "", "designer": "", "address": "", "city": "",
        "observations": ""
    }, [])
    assert result == "Pendiente"
