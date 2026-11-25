"""The course app: lessons and progress. Start it with `make course`.

It is a separate application from the service desk (servicedesk/). The two
share no code; the course only links to the desk's address.
"""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from course.api import Course
from course.api import make_router as make_api_router
from course.assistant import Assistant
from course.pages import make_router as make_pages_router

HERE = Path(__file__).parent


def create_app(data_dir: str | None = None, lessons_dir: str = "lessons", desk_url: str | None = None,
               unlock_all: bool | None = None, assistant_llm=None) -> FastAPI:
    app = FastAPI(title="Agent Quest")
    data_dir = data_dir or os.environ.get("COURSE_DATA_DIR", "data")
    if unlock_all is None:  # for checking lessons ahead of time: COURSE_UNLOCK_ALL=1 make course
        unlock_all = os.environ.get("COURSE_UNLOCK_ALL") == "1"
    course = Course(data_dir, lessons_dir, unlock_all)
    desk_url = desk_url or os.environ.get("SERVICE_DESK_URL", "http://localhost:8080")
    assistant = Assistant(course, assistant_llm)  # assistant_llm lets tests stand in for the local model
    app.include_router(make_api_router(course, assistant))
    app.include_router(make_pages_router(course, desk_url))
    app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")
    return app


app = create_app()
