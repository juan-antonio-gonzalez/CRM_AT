from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import Optional
import models
from enums import RelevamientoStatus, SurveyStatus
import datetime
from services import pagination as pg


def list_surveys(db: Session, cliente: str = None, asistente: str = None,
                 page: int = 1, per_page: int = 10):
    query = db.query(models.Machine)
    customers_raw = db.query(models.Customer).order_by(models.Customer.name).all()
    assigned_advisors = db.query(models.Customer.technical_advisor).filter(
        models.Customer.technical_advisor != None
    ).distinct().all()
    assigned_advisor_names = sorted([a[0] for a in assigned_advisors if a[0]])

    customers_for_dropdown = customers_raw
    advisors_for_dropdown = assigned_advisor_names

    if cliente and cliente.strip() != "":
        try:
            cliente_id = int(cliente)
            query = query.filter(models.Machine.customer_id == cliente_id)
            selected_cust = next((c for c in customers_raw if c.id == cliente_id), None)
            if selected_cust and selected_cust.technical_advisor:
                advisors_for_dropdown = [selected_cust.technical_advisor]
        except ValueError:
            pass

    if asistente and asistente.strip() != "":
        query = query.join(models.Customer).filter(models.Customer.technical_advisor == asistente)
        customers_for_dropdown = [c for c in customers_raw if c.technical_advisor == asistente]

    total = query.count()

    page, per_page, offset = pg.paginate(page, per_page)
    machines = query.order_by(models.Machine.brand, models.Machine.model).offset(offset).limit(per_page).all()

    selected_customer = None
    if cliente:
        selected_customer = db.query(models.Customer).filter(models.Customer.id == cliente).first()

    # Compute stats counting all filtered machines
    all_machines = query.order_by(models.Machine.brand, models.Machine.model).all()
    stats = {
        "total": len(all_machines),
        "completados": sum(1 for m in all_machines if m.relevamiento_status == RelevamientoStatus.COMPLETADO.value),
        "en_proceso": sum(1 for m in all_machines if m.relevamiento_status == RelevamientoStatus.EN_PROCESO.value),
        "pendientes": sum(1 for m in all_machines if m.relevamiento_status == RelevamientoStatus.PENDIENTE.value),
    }

    return {
        "machines": machines,
        "customers": customers_for_dropdown,
        "advisors": advisors_for_dropdown,
        "selected_customer_id": cliente,
        "selected_asistente": asistente,
        "selected_customer": selected_customer,
        "stats": stats,
        "pagination": pg.build_pagination(page, per_page, total),
    }


def get_machine_with_survey(db: Session, machine_id: int):
    machine = db.query(models.Machine).filter(models.Machine.id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Máquina no encontrada")
    survey = db.query(models.TechnicalSurvey).filter(models.TechnicalSurvey.machine_id == machine_id).first()
    return machine, survey


def save_relevamiento(db: Session, machine_id: int, data_dict: dict, is_finalize: bool = False):
    machine = db.query(models.Machine).filter(models.Machine.id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Máquina no encontrada")

    survey = db.query(models.TechnicalSurvey).filter(models.TechnicalSurvey.machine_id == machine_id).first()
    if not survey:
        survey = models.TechnicalSurvey(machine_id=machine_id, data=data_dict)
        db.add(survey)
    else:
        survey.data = data_dict
        survey.updated_at = datetime.datetime.now(datetime.UTC)

    if is_finalize:
        survey.status = SurveyStatus.COMPLETADO.value
        machine.relevamiento_status = RelevamientoStatus.COMPLETADO.value
    else:
        survey.status = SurveyStatus.BORRADOR.value
        machine.relevamiento_status = RelevamientoStatus.EN_PROCESO.value

    db.commit()
    return survey


def list_infrastructure_surveys(db: Session, cliente: int = None, asistente: str = None,
                                 page: int = 1, per_page: int = 10):
    query = db.query(models.InfrastructureSurvey)
    if cliente:
        query = query.filter(models.InfrastructureSurvey.customer_id == cliente)
    if asistente:
        query = query.filter(models.InfrastructureSurvey.technical_advisor == asistente)
    total = query.count()
    page, per_page, offset = pg.paginate(page, per_page)
    surveys = query.order_by(models.InfrastructureSurvey.updated_at.desc()).offset(offset).limit(per_page).all()
    customers = db.query(models.Customer).order_by(models.Customer.name).all()
    advisors = db.query(models.TechnicalAdvisor).order_by(models.TechnicalAdvisor.name).all()
    return surveys, customers, advisors, pg.build_pagination(page, per_page, total)


def save_infrastructure_survey(db: Session, form_data: dict, survey_id: int = None):
    if survey_id:
        survey = db.query(models.InfrastructureSurvey).filter(models.InfrastructureSurvey.id == survey_id).first()
    else:
        survey = models.InfrastructureSurvey()
        db.add(survey)

    customer_id = form_data.get("customer_id")
    if customer_id:
        survey.customer_id = int(customer_id)

    survey.plant = form_data.get("plant")
    survey.technical_advisor = form_data.get("technical_advisor")
    survey.status = form_data.get("status", SurveyStatus.EN_PROCESO.value)

    date_str = form_data.get("date")
    if date_str:
        try:
            survey.date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
        except:
            pass

    survey.storage_data = {
        "measures_insumos": form_data.get("measures_insumos"),
        "temp_insumos": form_data.get("temp_insumos"),
        "time_insumos": form_data.get("time_insumos"),
        "pop_insumos": form_data.get("pop_insumos"),
        "crit_insumos": form_data.get("crit_insumos"),
        "obs_insumos": form_data.get("obs_insumos"),
        "measures_finished": form_data.get("measures_finished"),
        "temp_finished": form_data.get("temp_finished"),
        "time_finished": form_data.get("time_finished"),
        "pop_finished": form_data.get("pop_finished"),
        "crit_finished": form_data.get("crit_finished"),
        "obs_finished": form_data.get("obs_finished")
    }
    survey.packaging_data = {
        "type": form_data.get("pkg_type"),
        "material": form_data.get("pkg_material"),
        "obs": form_data.get("pkg_obs")
    }
    survey.palletizing_data = {
        "type": form_data.get("pal_type"),
        "pallet_type": form_data.get("pal_pallet_type"),
        "pieces": form_data.get("pal_pieces"),
        "height": form_data.get("pal_height"),
        "overhang": form_data.get("pal_overhang"),
        "pattern": form_data.get("pal_pattern"),
        "stretch": form_data.get("pal_stretch"),
        "corners": form_data.get("pal_corners"),
        "interpallet": form_data.get("pal_interpallet"),
        "crit": form_data.get("pal_crit"),
        "obs": form_data.get("pal_obs")
    }
    survey.logistics_data = {
        "veh_type": form_data.get("log_veh_type"),
        "veh_height": form_data.get("log_veh_height"),
        "max_route": form_data.get("log_max_route"),
        "crit_trans": form_data.get("log_crit_trans"),
        "obs_trans": form_data.get("log_obs_trans"),
        "channel": form_data.get("log_channel"),
        "shelf": form_data.get("log_shelf"),
        "freq": form_data.get("log_freq"),
        "crit_dist": form_data.get("log_crit_dist"),
        "obs_dist": form_data.get("log_obs_dist")
    }

    db.commit()
    return survey


def delete_infrastructure_survey(db: Session, survey_id: int, user_id: int = None, username: str = None):
    survey = db.query(models.InfrastructureSurvey).filter(models.InfrastructureSurvey.id == survey_id).first()
    if survey:
        from services.trash_service import move_to_trash
        move_to_trash(db, "infrastructure", survey_id, {
            "customer_id": survey.customer_id, "plant": survey.plant,
            "date": str(survey.date) if survey.date else None,
            "technical_advisor": survey.technical_advisor,
            "status": survey.status,
            "storage_data": survey.storage_data,
            "packaging_data": survey.packaging_data,
            "palletizing_data": survey.palletizing_data,
            "logistics_data": survey.logistics_data,
        }, user_id, username, f"Infraestructura #{survey.id}")
        db.delete(survey)
        db.commit()
