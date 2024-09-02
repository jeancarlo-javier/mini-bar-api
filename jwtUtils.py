import jwt
from fastapi import HTTPException
from typing import Union
from datetime import datetime, timedelta, timezone

SECRET_KEY = "866fff7f4ecad9aa1fc976912eeafed7add0c0aea74ed610ec982353c968d64c"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 720


def create_access_token(
    data: dict, expires_delta: Union[timedelta, None] = None
) -> str:
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def decode_token(token: str):
    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return decoded
    except jwt.ExpiredSignatureError:
        return HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        return HTTPException(status_code=401, detail="Invalid token")
    except Exception:
        return HTTPException(status_code=401, detail="Invalid token")
