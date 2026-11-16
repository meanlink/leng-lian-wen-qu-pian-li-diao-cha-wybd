from pydantic import BaseModel, Field
class MeasureInput(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    detail: str = Field(default='', max_length=500)
    assignee: str = Field(min_length=2, max_length=80)
class OrderInput(BaseModel):
    job_id: int
    title: str = Field(min_length=2, max_length=160)
    measures: list[MeasureInput] = Field(min_length=1, max_length=20)
class MeasurePatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=160)
    detail: str | None = Field(default=None, max_length=500)
    assignee: str | None = Field(default=None, min_length=2, max_length=80)
    note: str | None = Field(default=None, max_length=1000)
    evidence: list[str] | None = None
    revoke: bool = False
class ClaimInput(BaseModel):
    assignee: str = Field(min_length=2, max_length=80)
class ReturnInput(BaseModel):
    payload: dict
class ResolveInput(BaseModel):
    resolution: str = Field(pattern='^(keep_online|take_package)$')
    expected_version: int = Field(ge=1)
class SendBackInput(BaseModel):
    note: str = Field(default='', max_length=300)
