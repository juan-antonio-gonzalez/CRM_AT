from sqlalchemy import Column, Integer, String, Float, Text, Boolean, ForeignKey, JSON, DateTime
from sqlalchemy.orm import relationship
from database import Base
from enums import VisitStatus, TrackingStatus, SurveyStatus, RelevamientoStatus, CustomerStatus, ProductStatus
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
    last_modified = Column(String)

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
    
    # Relationships
    machines = relationship("Machine", back_populates="customer")
    technical_visits = relationship("TechnicalVisit", back_populates="customer")

class TechnicalVisit(Base):
    """
    Registro maestro de reuniones y visitas realizadas al cliente.
    Contiene la metadata de la visita, participantes, objetivos,
    conclusiones, fotografías subidas y planes de acción JSON crudos.
    """
    __tablename__ = "technical_visits"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    plant = Column(String)
    date = Column(DateTime, default=datetime.datetime.utcnow)
    participants = Column(String)
    visit_type = Column(String)
    objective = Column(Text)
    follow_up_previous = Column(Text)
    findings_quality = Column(Text)
    findings_support = Column(Text)
    conclusions = Column(Text)
    action_plan = Column(JSON, default=[]) # List of dicts: {task, responsible, due_date, status}
    detailed_development = Column(Text)
    status = Column(String, default=VisitStatus.PROGRAMADA.value)
    evidence_photos = Column(JSON, default=[]) # Array of strings (filenames)
    customer_name_backup = Column(String, nullable=True) # Backup for when customer is deleted
    topics = Column(JSON, default=[]) # Multiple selection topics (strings)
    cancellation_reason = Column(Text, nullable=True)
    technical_advisor = Column(String, nullable=True)
    distributor_plant = Column(String, nullable=True)

    # Relationships
    customer = relationship("Customer", back_populates="technical_visits")

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

class TechnicalAdvisor(Base):
    __tablename__ = "technical_advisors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

class Designer(Base):
    __tablename__ = "designers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

class CommercialAdvisor(Base):
    """
    Tabla Auxiliar interactuable.
    Almacena los asesores comerciales disponibles para asignar a clientes.
    """
    __tablename__ = "commercial_advisors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

class IndustrialSector(Base):
    __tablename__ = "industrial_sectors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

class VisitTopic(Base):
    """
    Tabla Auxiliar interactuable.
    Define los tópicos preestablecidos (capacitación, auditoría, prueba) a seleccionar en las visitas.
    """
    __tablename__ = "visit_topics"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

class FormadoType(Base):
    __tablename__ = "formado_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

class InferiorClosure(Base):
    __tablename__ = "inferior_closure_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

class ClientName(Base):
    __tablename__ = "client_names"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

class PlantName(Base):
    __tablename__ = "plant_names"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

class VisitType(Base):
    __tablename__ = "visit_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

class DistributorPlant(Base):
    __tablename__ = "distributor_plants"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

class ATAssignment(Base):
    __tablename__ = "at_assignments"
    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String, unique=True, index=True)
    technical_advisor = Column(String)
    standard_visits = Column(Integer, default=0)
    premium_visits = Column(Integer, default=0)
    attention_required = Column(Boolean, default=False)
    attention_observations = Column(Text)

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

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    customer = relationship("Customer")

class ActionPlanTracking(Base):
    __tablename__ = "action_plan_tracking"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String, index=True)
    plant = Column(String, nullable=True)
    visit_date = Column(DateTime, nullable=True)
    task = Column(Text)
    responsible = Column(String, nullable=True)
    due_date = Column(String, nullable=True)
    status = Column(String, default=TrackingStatus.PENDIENTE.value)
    observations = Column(Text, nullable=True)
    source_visit_id = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
