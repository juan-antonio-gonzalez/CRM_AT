from math import ceil


def paginate(page: int = 1, per_page: int = 10):
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 10
    if per_page > 100:
        per_page = 100
    offset = (page - 1) * per_page
    return page, per_page, offset


def build_pagination(page: int, per_page: int, total: int):
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": ceil(total / per_page) if total > 0 else 1,
        "has_prev": page > 1,
        "has_next": page * per_page < total,
    }
