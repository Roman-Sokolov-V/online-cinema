from sqlalchemy import or_, and_, func
from sqlalchemy.orm import InstrumentedAttribute
from typing import Optional
from sqlalchemy.sql import Select


def apply_m2m_filter(
    stmt: Select,
    field: InstrumentedAttribute,
    value: Optional[str],
    related_field_name: str = "name",
) -> Select:
    """
    Додає фільтр по зв'язку many-to-many з підтримкою | (OR), & (AND), або одиночного значення.

    :param stmt: SQLAlchemy select-вираз
    :param field: Наприклад, MovieModel.genres
    :param value: Строка типу "action|horror", "action&horror", "action"
    :param related_field_name: Назва поля в зв’язаній моделі (зазвичай name)
    :return: Оновлений select
    """
    if not value:
        return stmt

    def any_clause(v: str):
        return field.any(
            func.lower(
                getattr(field.property.mapper.class_, related_field_name)
            ) == v.strip().lower()
        )

    if "|" in value:
        values = value.split("|")
        stmt = stmt.filter(or_(*(any_clause(v) for v in values)))
    elif "," in value:
        values = value.split(",")
        stmt = stmt.filter(and_(*(any_clause(v) for v in values)))
    else:
        stmt = stmt.filter(any_clause(value))
    return stmt
