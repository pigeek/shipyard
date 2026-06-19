from sqladmin import ModelView

from app.features.users.models import User


class UserAdmin(ModelView, model=User):
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"
    column_list = [
        User.id,
        User.email,
        User.is_active,
        User.is_superuser,
        User.is_verified,
        User.created_at,
    ]
    column_searchable_list = [User.email]
    column_sortable_list = [User.email, User.created_at]
    form_excluded_columns = [User.hashed_password, User.created_at, User.updated_at]
