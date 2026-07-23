from sqlmodel import SQLModel


class DeleteResponse(SQLModel):
    deleted_id: int
