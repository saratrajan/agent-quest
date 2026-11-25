# The course app: lessons and progress tracking, on port 8000.
FROM python:3.13-slim
WORKDIR /app
RUN pip install --no-cache-dir "fastapi>=0.115" "uvicorn>=0.30" "jinja2>=3.1" "pyyaml>=6.0" "pytest>=8"
COPY course ./course
EXPOSE 8000
CMD ["uvicorn", "course.app:app", "--host", "0.0.0.0", "--port", "8000"]
