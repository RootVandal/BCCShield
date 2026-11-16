from typing import Literal

from pydantic import BaseModel, Field


class LanguageIn(BaseModel):
    language: Literal["ru", "kk"]


class ShieldIn(BaseModel):
    enabled: bool


class LoanIn(BaseModel):
    amount: float = Field(gt=0, le=10_000_000)


class Answers(BaseModel):
    on_call: bool = False
    safe_account: bool = False
    impersonation: bool = False


class TransferIn(BaseModel):
    bank: str = "BCC"
    card: str | None = None
    phone: str | None = None
    amount: float = Field(gt=0)
    behavior: dict = Field(default_factory=dict)  # {"pasted": bool, "fill_seconds": float}
    answers: Answers | None = None


class DecisionIn(BaseModel):
    decision: Literal["approve", "reject"]
    by: str = "relative_web"


class CallStartIn(BaseModel):
    client_id: int = 1


class CallTextIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class ScenarioIn(BaseModel):
    name: str


class AnswerIn(BaseModel):
    outcome: str = "ended"


class SignalIn(BaseModel):
    account_id: int
    reason: str = "Подозрение на дроп-счёт (решение аналитика)"


class SimulateSignalIn(BaseModel):
    account_id: int | None = None
