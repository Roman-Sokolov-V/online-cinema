import os

from database.models.base import Base
from database.models.accounts import (
    UserModel,
    UserGroupModel,
    UserGroupEnum,
    ActivationTokenModel,
    PasswordResetTokenModel,
    RefreshTokenModel,
    UserProfileModel,
    RateModel
)
from database.models.movies import (
    MovieModel,
    GenreModel,
    MoviesGenresModel,
    StarModel,
    MoviesStarsModel,
    CertificationModel,
    DirectorModel,
    MoviesDirectorsModel,
)
from database.models.opinions import CommentModel
from database.models.shopping_cart import (
    CartModel,
    CartItemModel,
    PurchaseModel
)
from database.models.orders import OrderModel, OrderItemModel, OrderStatus
from database.models.payments import PaymentModel, PaymentItemModel, StatusPayment
from database.session_sqlite import reset_sqlite_database as reset_database, reset_sync_sqlite_database
from database.validators import accounts as accounts_validators


environment = os.getenv("ENVIRONMENT", "developing")

if environment == "testing":
    from database.session_sqlite import (
        get_sqlite_db_contextmanager as get_db_contextmanager,
        get_sync_sqlite_db_contextmanager as get_sync_db_contextmanager,
        get_sqlite_db as get_db
    )
else:
    from database.session_postgresql import (
        get_postgresql_db_contextmanager as get_db_contextmanager,
        get_sync_postgresql_db_contextmanager as get_sync_db_contextmanager,
        get_postgresql_db as get_db,
    )
