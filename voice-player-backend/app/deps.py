from fastapi import Request

from .config import Settings
from .db import Database
from .services.hub import Hub
from .services.pipeline import Pipeline
from .services.storage import Storage


def settings_of(request: Request) -> Settings:
    return request.app.state.settings


def db_of(request: Request) -> Database:
    return request.app.state.db


def storage_of(request: Request) -> Storage:
    return request.app.state.storage


def pipeline_of(request: Request) -> Pipeline:
    return request.app.state.pipeline


def hub_of(request: Request) -> Hub:
    return request.app.state.hub
