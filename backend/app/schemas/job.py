from pydantic import BaseModel, HttpUrl


class JobCreate(BaseModel):
    url: HttpUrl


class JobResponse(BaseModel):
    id: str
    url: str
    status: str

    model_config = {"from_attributes": True}
