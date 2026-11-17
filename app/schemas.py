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


class OperationIn(BaseModel):
    kind: Literal["cash", "deposit"]
    amount: float | None = Field(default=None, gt=0)  # deposit closure always takes the whole deposit
    behavior: dict = Field(default_factory=dict)
    answers: Answers | None = None


class TelecomSignalIn(BaseModel):
    minutes: int = Field(default=15, ge=1, le=120)


class DecisionIn(BaseModel):
    decision: Literal["approve", "reject"]
    by: str = "relative_web"  # ignored: who decided is taken from the credentials, never from the body


class CallStartIn(BaseModel):
    client_id: int = 1


class PhoneCallIn(BaseModel):
    """What the bank app learns from the phone about a call (CallKit / TelephonyCallback). The demo can say the
    call began some minutes ago, the way a scammer's call is already running when the client opens the app."""
    state: Literal["start", "end"] = "start"
    caller: str = Field(default="", max_length=40)
    caller_kind: Literal["contact", "unknown", "hidden"] = "unknown"
    incoming: bool = True
    minutes_ago: float = Field(default=0, ge=0, le=180)


class RemoteAppIn(BaseModel):
    app: str | None = Field(default=None, max_length=24)


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


class ClientIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    age: int = Field(default=67, ge=18, le=110)
    phone: str = Field(default="", max_length=24)
    balance: float = Field(default=850_000, ge=0, le=50_000_000)


class RulesIn(BaseModel):
    threshold: float | None = Field(default=None, ge=0, le=100_000_000)
    confirm_new: bool | None = None
    confirm_loans: bool | None = None
    notify_all: bool | None = None


class ContactIn(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    relation: str = Field(default="сын", max_length=30)
    phone: str = Field(min_length=10, max_length=24)
    threshold: float = Field(default=100_000, ge=0, le=100_000_000)
    confirm_new: bool = True
    confirm_loans: bool = True
    notify_all: bool = True
