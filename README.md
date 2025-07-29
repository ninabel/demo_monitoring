# Device Monitoring Demo

This is a simple FastAPI-based monitoring dashboard that demonstrates:

- Device and site relationships
- JSON endpoints
- Async SQLModel usage
- Dockerized deployment

The core domain object is a **Site**. 

Each Site has several **Devices** (batteries, inverters, PV panels, wind turbines …). 

Device reports at least one **metric** (e.g. battery state‑of‑charge, PV power, wind speed). 

Devices belong to **Device Types**, which determine which metrics can be measured on given device.

## Run Locally (with virtualenv)

### 1. Clone the repo

```#bash
git clone https://github.com/ninabel/demo_monitoring.git
cd demo_monitoring
```

### 2. Create a virtualenv and install dependencies
```#bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Run the app
```#bash
uvicorn app.main:app --reload
```
Then open: http://localhost:8000

## Run in Docker (Podman or Docker)
### 1. Build the image
```#bash
podman build -t demo-monitoring .
# or
docker build -t demo-monitoring .
```

### 2. Run the container
```#bash
podman run -p 8000:8000 demo-monitoring
# or
docker run -p 8000:8000 demo-monitoring
```

Then open: http://localhost:8000

_**Note:** The SQLite database will be re-created fresh on each container run unless you mount a volume._

## Customize

You can modify models.py to add more fields to Site and Device.

To switch DB backend, adjust the DATABASE_URL in db.py.

## ToDo

**Tests** — Add unit and integration tests (e.g. with pytest-asyncio)

**Validation** — Use Pydantic models

**Configuration** — Enable settings 
 
