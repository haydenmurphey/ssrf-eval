FROM python:3.10-alpine
WORKDIR /app
RUN pip install flask
COPY dashboard.py .
EXPOSE 5000
CMD ["python", "dashboard.py"]