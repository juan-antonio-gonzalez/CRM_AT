from sqlalchemy import Column, Integer, String, Float, Text, Boolean, ForeignKey, JSON, DateTime
from sqlalchemy.orm import relationship, validates
from database import Base
from enums import TrackingStatus, SurveyStatus, RelevamientoStatus, CustomerStatus, ProductStatus
import datetime


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, default="")
    phone = Column(String, default="")
    role = Column(String, default="user")  # user, admin
    is_active = Column(Boolean, default=True)
    avatar_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class Product(Base):
    """
    Representa el catálogo base de los productos fabricados u ofrecidos.
    Almacena especificaciones como material, dimensiones y tipo de empaque.
    """
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    et_number = Column(String, unique=True, index=True)
    material = Column(String)
    manufacturing_route = Column(String)
    dimensions_l = Column(Float)
    dimensions_a = Column(Float)
    dimensions_h = Column(Float)
    status = Column(String, default=ProductStatus.ACTIVO.value)
    # Legacy free-text marker ("Hace 2 días", "Hoy", "%Y-%m-%d %H:%M"). Superseded
    # by updated_at; kept only so existing rows are not lost.
    last_modified = Column(String)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    is_active = Column(Boolean, default=True)
    inactivation_reason = Column(Text, nullable=True)
    inactivated_by_id = Column(Integer, nullable=True)
    inactivated_at = Column(DateTime, nullable=True)

class Customer(Base):
    """
    Entidad fundamental que representa a los clientes comerciales.
    Guarda los datos de ubicación, equipos asignados y estado operativo.
    """
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    plant = Column(String)
    industry_sector = Column(String)
    assigned_commercial = Column(String)
    technical_advisor = Column(String)
    designer = Column(String)
    address = Column(String)
    city = Column(String)
    status = Column(String, default=CustomerStatus.PROSPECTO.value)
    relevamiento_status = Column(String, default=RelevamientoStatus.PENDIENTE.value)
    client_team = Column(JSON, default=[]) # List of dicts: {name, role, email}
    observations = Column(Text)
    standard_visits = Column(Integer, default=0)
    premium_visits = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    inactivation_reason = Column(Text, nullable=True)
    inactivated_by_id = Column(Integer, nullable=True)
    inactivated_at = Column(DateTime, nullable=True)
    
    # Relationships
    machines = relationship("Machine", back_populates="customer")

class TechnicalVisit2(Base):
    """
    Nueva versión (V2) del formulario de visita técnica (SKA-DES-FO-001 Rev.2).
    Almacena todo el estado del formulario dinámico en form_data (JSON).
    """
    __tablename__ = "technical_visits_2"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    fecha = Column(String, nullable=True)
    status = Column(String, default="Borrador")
    form_data = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    inactivation_reason = Column(Text, nullable=True)
    inactivated_by_id = Column(Integer, nullable=True)
    inactivated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class TechnicalSurveyV2(Base):
    """
    Nueva versión (V2) del formulario de relevamiento técnico.
    Almacena todo el estado del formulario dinámico en form_data (JSON).
    """
    __tablename__ = "technical_surveys_2"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    machine_id = Column(Integer, ForeignKey("machines.id"), nullable=True)
    fecha = Column(String, nullable=True)
    status = Column(String, default="En proceso")
    form_data = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    inactivation_reason = Column(Text, nullable=True)
    inactivated_by_id = Column(Integer, nullable=True)
    inactivated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    customer = relationship("Customer")
    machine = relationship("Machine")


class Machine(Base):
    """
    Registro del inventario físico instalado en las diferentes plantas.
    Permite el mapeo y tracking de los números de serie individuales.
    """
    __tablename__ = "machines"

    id = Column(Integer, primary_key=True, index=True)
    serial_number = Column(String, unique=True, index=True)
    model = Column(String)
    brand = Column(String)
    plant_assigned = Column(String)
    machine_type = Column(String)
    line = Column(String)
    status = Column(String, default="Operativo")
    relevamiento_status = Column(String, default=RelevamientoStatus.PENDIENTE.value)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    inactivation_reason = Column(Text, nullable=True)
    inactivated_by_id = Column(Integer, nullable=True)
    inactivated_at = Column(DateTime, nullable=True)

    # Relationships
    customer = relationship("Customer", back_populates="machines")
    surveys = relationship("TechnicalSurvey", back_populates="machine")

class MachineType(Base):
    """
    Tabla de configuración (Auxiliar) que nutre los selectores
    para estandarizar las líneas y el tipo de máquinas soportadas.
    """
    __tablename__ = "machine_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    is_active = Column(Boolean, default=True)
    inactivation_reason = Column(Text, nullable=True)
    inactivated_by_id = Column(Integer, nullable=True)
    inactivated_at = Column(DateTime, nullable=True)

    @validates('name')
    def validate_name(self, key, value):
        return value.strip().upper()

class TechnicalSurvey(Base):
    """
    Modelo responsable de persistir las auditorías técnicas
    (relevamientos de infraestructura, procesos y calidad).
    Guarda los datos en una columna JSON estructurada de alta densidad.
    """
    __tablename__ = "technical_surveys"

    id = Column(Integer, primary_key=True, index=True)
    machine_id = Column(Integer, ForeignKey("machines.id"))
    status = Column(String, default=SurveyStatus.BORRADOR.value)
    data = Column(JSON) # Store all form fields here
    is_active = Column(Boolean, default=True)
    inactivation_reason = Column(Text, nullable=True)
    inactivated_by_id = Column(Integer, nullable=True)
    inactivated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    machine_name_backup = Column(String, nullable=True)
    machine_serial_backup = Column(String, nullable=True)

    machine = relationship("Machine", back_populates="surveys")

class TrashItem(Base):
    __tablename__ = "trash_items"
    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String, index=True)
    entity_id = Column(Integer, nullable=True)
    entity_name = Column(String, nullable=True)
    data = Column(JSON)
    deleted_by = Column(Integer, nullable=True)
    deleted_by_name = Column(String, nullable=True)
    deleted_at = Column(DateTime, default=datetime.datetime.utcnow)
    restored_at = Column(DateTime, nullable=True)
    restored_by = Column(Integer, nullable=True)

class BaseCatalogMixin:
    is_active = Column(Boolean, default=True)
    inactivation_reason = Column(Text, nullable=True)
    inactivated_by_id = Column(Integer, nullable=True)
    inactivated_at = Column(DateTime, nullable=True)


class TechnicalAdvisor(Base, BaseCatalogMixin):
    __tablename__ = "technical_advisors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    @validates('name')
    def validate_name(self, key, value):
        return value.strip().upper()

class Designer(Base, BaseCatalogMixin):
    __tablename__ = "designers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    @validates('name')
    def validate_name(self, key, value):
        return value.strip().upper()

class CommercialAdvisor(Base, BaseCatalogMixin):
    __tablename__ = "commercial_advisors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    @validates('name')
    def validate_name(self, key, value):
        return value.strip().upper()

class IndustrialSector(Base, BaseCatalogMixin):
    __tablename__ = "industrial_sectors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    @validates('name')
    def validate_name(self, key, value):
        return value.strip().upper()

class VisitTopic(Base, BaseCatalogMixin):
    __tablename__ = "visit_topics"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    @validates('name')
    def validate_name(self, key, value):
        return value.strip().upper()

class FormadoType(Base, BaseCatalogMixin):
    __tablename__ = "formado_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    @validates('name')
    def validate_name(self, key, value):
        return value.strip().upper()

class InferiorClosure(Base, BaseCatalogMixin):
    __tablename__ = "inferior_closure_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    @validates('name')
    def validate_name(self, key, value):
        return value.strip().upper()

class ClientName(Base, BaseCatalogMixin):
    __tablename__ = "client_names"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    @validates('name')
    def validate_name(self, key, value):
        return value.strip().upper()

class PlantName(Base, BaseCatalogMixin):
    __tablename__ = "plant_names"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    @validates('name')
    def validate_name(self, key, value):
        return value.strip().upper()

class VisitType(Base, BaseCatalogMixin):
    __tablename__ = "visit_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    @validates('name')
    def validate_name(self, key, value):
        return value.strip().upper()

class QualityTopic(Base, BaseCatalogMixin):
    __tablename__ = "quality_topics"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    @validates('name')
    def validate_name(self, key, value):
        return value.strip().upper()

class QualityAT(Base, BaseCatalogMixin):
    __tablename__ = "quality_at_topics"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    @validates('name')
    def validate_name(self, key, value):
        return value.strip().upper()

class ContactName(Base, BaseCatalogMixin):
    __tablename__ = "contact_names"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    @validates('name')
    def validate_name(self, key, value):
        return value.strip().upper()

class MemberSector(Base, BaseCatalogMixin):
    __tablename__ = "member_sectors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    @validates('name')
    def validate_name(self, key, value):
        return value.strip().upper()

class DistributorPlant(Base, BaseCatalogMixin):
    __tablename__ = "distributor_plants"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    @validates('name')
    def validate_name(self, key, value):
        return value.strip().upper()

class ATAssignment(Base):
    __tablename__ = "at_assignments"
    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String, index=True)
    technical_advisor = Column(String)
    standard_visits = Column(Integer, default=0)
    premium_visits = Column(Integer, default=0)
    attention_required = Column(Boolean, default=False)
    attention_observations = Column(Text)
    status = Column(String, default="Activo")
    valid_from = Column(DateTime, default=datetime.datetime.utcnow)
    valid_to = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    inactivation_reason = Column(Text, nullable=True)
    inactivated_by_id = Column(Integer, nullable=True)
    inactivated_at = Column(DateTime, nullable=True)

class InfrastructureSurvey(Base):
    """
    Relevamiento especializado para el área de Infraestructura y Logística.
    Almacena cuatro grandes dimensiones (almacenamiento, empaque, paletizado y logística) en arreglos estructurados de JSON.
    """
    __tablename__ = "infrastructure_surveys"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    plant = Column(String)
    date = Column(DateTime, default=datetime.datetime.utcnow)
    technical_advisor = Column(String)
    status = Column(String, default=SurveyStatus.PENDIENTE.value)
    
    # Store all sections in structured JSON for flexibility
    storage_data = Column(JSON, default={})
    packaging_data = Column(JSON, default={})
    palletizing_data = Column(JSON, default={})
    logistics_data = Column(JSON, default={})

    is_active = Column(Boolean, default=True)
    inactivation_reason = Column(Text, nullable=True)
    inactivated_by_id = Column(Integer, nullable=True)
    inactivated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    customer = relationship("Customer")

class ActionPlanTracking(Base):
    __tablename__ = "action_plan_tracking"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String, index=True)
    plant = Column(String, nullable=True)
    visit_date = Column(DateTime, nullable=True)
    et_number = Column(String, nullable=True)
    task = Column(Text)
    responsible = Column(String, nullable=True)
    due_date = Column(String, nullable=True)
    status = Column(String, default=TrackingStatus.PENDIENTE.value)
    observations = Column(Text, nullable=True)
    source_visit_id = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class MeetingMinutes(Base):
    __tablename__ = "meeting_minutes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    fecha = Column(String, nullable=True)
    status = Column(String, default="Borrador")
    form_data = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
    inactivation_reason = Column(Text, nullable=True)
    inactivated_by_id = Column(Integer, nullable=True)
    inactivated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
