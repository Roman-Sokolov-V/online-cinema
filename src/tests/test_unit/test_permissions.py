from fastapi import HTTPException

import pytest

from routes.permissions import is_moderator_or_admin


def test_is_moderator_or_admin_direct_allow():
    payload = {"user_id": 1, "group": "admin"}
    result = is_moderator_or_admin(payload=payload)
    assert result == payload
    payload = {"user_id": 1, "group": "moderator"}
    result = is_moderator_or_admin(payload=payload)
    assert result == payload


def test_is_moderator_or_admin_direct_forbidden():
    payload = {"user_id": 1, "group": "user"}
    with pytest.raises(HTTPException) as exc_info:
        is_moderator_or_admin(payload=payload)
    assert exc_info.value.status_code == 403
