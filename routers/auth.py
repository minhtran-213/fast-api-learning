from datetime import timedelta, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette import status

from database import SessionLocal
from models import User

router = APIRouter(
    prefix='/auth',
    tags=['auth']
)

oauth2Bearer = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]


class CreateUserRequest(BaseModel):
    email: str
    username: str
    first_name: str
    last_name: str
    password: str
    role: str


class Token(BaseModel):
    access_token: str
    token_type: str
    expires_time: str


bcrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def get_auth(db: db_dependency, create_user_request: CreateUserRequest):
    hashed_pass = bcrypt_context.hash(create_user_request.password)
    user = User(
        email=create_user_request.email,
        username=create_user_request.username,
        first_name=create_user_request.first_name,
        last_name=create_user_request.last_name,
        hashed_password=hashed_pass,
        role=create_user_request.role,
        is_active=True
    )
    db.add(user)
    db.commit()


def check_user_authentication(username: str, password: str, db: db_dependency):
    user = db.query(User).filter(username == User.username).first()
    if not user:
        return False
    if bcrypt_context.verify(password, user.hashed_password):
        return user
    return False


SECRET_KEY = "kMoJ8quoXyXg7XDf95JXLOQRgVHCKvRY"
ALGORITHM = "HS256"


def create_access_token(username: str, user_id: int, expires_time: timedelta):
    encode = {
        "sub": username,
        "id": user_id
    }
    expires = datetime.utcnow() + expires_time
    encode.update({"exp": expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: Annotated[str, Depends(oauth2Bearer)]):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        user_id = payload.get("id")
        if username is None or user_id is None:
            raise HTTPException(status_code=404, detail="Unauthorized")
        return {'username': username, "user_id": user_id}
    except JWTError:
        raise HTTPException(status_code=404, detail="Unauthorized")


@router.post("/login", response_model=Token)
async def authenticate_user(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: db_dependency):
    user_authenticate = check_user_authentication(form_data.username, form_data.password, db)
    if not user_authenticate:
        raise HTTPException(status_code=404, detail="Unauthorized")
    token = create_access_token(
        username=form_data.username,
        user_id=user_authenticate.id,
        expires_time=timedelta(minutes=20))
    return {"access_token": token, "token_type": "Bearer", "expires_time": "20 minutes"}
