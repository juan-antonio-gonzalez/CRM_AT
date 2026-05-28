def calculate_relevo_status(data: dict, team: list) -> str:
    required_fields = [
        'name', 'plant', 'industry_sector', 'assigned_commercial',
        'technical_advisor', 'designer', 'address', 'city', 'observations'
    ]
    for field in required_fields:
        val = data.get(field, "")
        if not val or (isinstance(val, str) and not val.strip()):
            return "Pendiente"
    if not team or len(team) == 0:
        return "En Proceso"
    return "Completado"
