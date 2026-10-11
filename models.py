from sqlalchemy import Column, Integer, String, Float, Text, Boolean, ForeignKey, JSON, DateTime, Index
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

    __table_args__ = (
        Index("ix_products_is_active_name", "is_active", "name"),
    )


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
    

    __table_args__ = (
        Index("ix_customers_is_active_name", "is_active", "name"),
    )

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

    __table_args__ = (
        Index("ix_technical_visits_2_fecha_status", "fecha", "status"),
        Index("ix_technical_visits_2_status_fecha", "status", "fecha"),
    )

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


    __table_args__ = (
        Index("ix_technical_surveys_2_customer_id", "customer_id"),
        Index("ix_technical_surveys_2_machine_id", "machine_id"),
        Index("ix_technical_surveys_2_status_fecha", "status", "fecha"),
    )

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


    __table_args__ = (
        Index("ix_machines_customer_id", "customer_id"),
        Index("ix_machines_is_active_serial", "is_active", "serial_number"),
    )

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


    __table_args__ = (
        Index("ix_technical_surveys_machine_id", "machine_id"),
    )

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

    __table_args__ = (
        Index("ix_trash_items_restored_entity_deleted", "restored_at", "entity_type", "deleted_at"),
    )

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

class VisitReason(Base, BaseCatalogMixin):
    """Motivo de la visita.

    El objetivo dice *qué tipo* de visita es (programada, seguimiento, reclamo).
    El motivo dice *por qué se fue esta vez*: «retiro de muestra por desvío»,
    «reunión con calidad por reclamo de cliente», «plan de ahorro en paletizado».

    Va como catálogo y no como texto libre para poder filtrar y agrupar por motivo.
    """

    __tablename__ = "visit_reasons"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

    @validates('name')
    def validate_name(self, key, value):
        # En mayúsculas, como el resto de los catálogos: los filtros comparan por
        # igualdad y "Retiro de muestra" no encontraría "RETIRO DE MUESTRA".
        return value.strip().upper() if value else value


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

    __table_args__ = (
        Index("ix_at_assignments_customer_valid_to", "customer_name", "valid_to"),
        Index("ix_at_assignments_advisor_valid_to", "technical_advisor", "valid_to"),
        Index("ix_at_assignments_inactivated_by_id", "inactivated_by_id"),
    )

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


    __table_args__ = (
        Index("ix_infrastructure_surveys_customer_id", "customer_id"),
    )

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
    # El resto de la familia de soft-delete. La migración de reconciliación ya
    # las había agregado a la base, pero faltaban acá, así que los modelos y el
    # esquema no coincidían (lo detecta tests/test_schema.py).
    inactivation_reason = Column(Text, nullable=True)
    inactivated_by_id = Column(Integer, nullable=True)
    inactivated_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    __table_args__ = (
        Index("ix_action_plan_tracking_active_created", "is_active", "created_at"),
        Index("ix_action_plan_tracking_source_visit_id", "source_visit_id"),
    )


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

    __table_args__ = (
        Index("ix_meeting_minutes_status_fecha", "status", "fecha"),
    )



class ActivityLog(Base):
    """Historial de cambios por registro.

    Con cinco usuarios trabajando, "¿quién cambió esto?" no tenía respuesta. Cada
    alta, edición, baja y reactivación queda registrada con quién, cuándo y qué
    cambió.

    Se guarda el nombre del usuario además de su id: si el usuario se elimina, el
    historial tiene que seguir siendo legible. Y se guardan los cambios como
    diferencias campo por campo, no el registro entero, para poder mostrar qué se
    modificó sin tener que comparar dos versiones completas.
    """

    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # "customer", "machine", "visit", "minute", "product"
    entity = Column(String(40), nullable=False)
    entity_id = Column(Integer, nullable=False)
    # "crear", "editar", "desactivar", "reactivar", "eliminar"
    action = Column(String(20), nullable=False)
    # Descripción legible del registro afectado, para mostrarla sin otra consulta.
    entity_label = Column(String(200), nullable=True)
    user_id = Column(Integer, nullable=True)
    username = Column(String(80), nullable=True)
    # {campo: {"antes": x, "despues": y}}
    changes = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_activity_log_entity", "entity", "entity_id", "created_at"),
        Index("ix_activity_log_created", "created_at"),
    )
