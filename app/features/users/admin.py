from sqladmin import ModelView

from app.features.users.models import User


class UserAdmin(ModelView, model=User):
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"
    # String column names sidestep typing friction from the fastapi-users base.
    column_list = [
        "id",
        "email",
        "is_active",
        "is_superuser",
        "is_verified",
        "created_at",
    ]
    column_searchable_list = ["email"]
    column_sortable_list = ["email", "created_at"]
    form_excluded_columns = ["hashed_password", "created_at", "updated_at"]
