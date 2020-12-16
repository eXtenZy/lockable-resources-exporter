FROM python:3

COPY src requirements.txt /opt/

WORKDIR /opt

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8080

ENTRYPOINT [ "python", "lockable-resources-exporter.py" ]
