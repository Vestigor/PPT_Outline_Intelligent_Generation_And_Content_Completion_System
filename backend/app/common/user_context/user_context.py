from pydantic import BaseModel

class UserContext(BaseModel):
    id: int
    username: str
    role: str

    @classmethod
    def from_payload(cls, payload: dict):
        return cls(
            id=payload["sub"],
            username=payload["username"],
            role=payload["role"],
        )