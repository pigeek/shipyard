from sqladmin import ModelView

from app.features.files.models import StoredFile


class StoredFileAdmin(ModelView, model=StoredFile):
    name = "File"
    name_plural = "Files"
    icon = "fa-solid fa-file-arrow-up"
    can_create = False
    can_edit = False
    column_list = [
        StoredFile.id,
        StoredFile.filename,
        StoredFile.content_type,
        StoredFile.size,
        StoredFile.status,
        StoredFile.owner_id,
        StoredFile.team_id,
        StoredFile.created_at,
    ]
    column_searchable_list = [StoredFile.filename, StoredFile.key]
    column_sortable_list = [StoredFile.created_at, StoredFile.size, StoredFile.status]
