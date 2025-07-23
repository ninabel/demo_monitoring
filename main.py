# -*- coding: utf-8 -*-
"""
Author: Nina Belyavskaya
"""

from fastapi import FastAPI, HTTPException
from models import Device, Metric, Site, DeviceType, Measure
from measure import mock
from db import SessionDep, create_db_and_tables, get_session
from sqlmodel import select
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone
from fastapi.logger import logger

app = FastAPI()

create_db_and_tables()

def measure_devices():
    """
    Function to measure devices and store results in the database.
    This function should be called periodically by the scheduler.
    """
    session = next(get_session())
    logger.info("Starting measurement of devices")
    devices = session.exec(select(Device).where(Device.is_active)).all()
    for device in devices:
        if device.is_active and device.device_type.metrics:
            for metric in device.device_type.metrics:
                func = globals().get(metric.call)
                if not callable(func):
                    raise ValueError(f"Function '{metric.call}' not found or not callable")
                
                value = func(metric, device)  # Call the function dynamically
                measure = Measure(
                    device_id=device.id,
                    metric_id=metric.id,
                    value=value,
                    timestamp=datetime.now(timezone.utc)  # Use UTC timezone                                                                                     
                )
                session.add(measure)
    session.commit()
    logger.info("Measurement of devices completed")

# Initialize the scheduler to run measure_devices every 30 seconds
scheduler = BackgroundScheduler()
scheduler.add_job(measure_devices, 'interval', seconds=180)
scheduler.start()

@app.get("/")
# main page with all sites
async def sites(session: SessionDep):
    sites = session.exec(select(Site)).all()
    if not sites:
        print("The system is empty, please create a site first.")
        return {"message": "The system is empty, please create a site first."}
    return [{"id": site.id, "name": site.name, "link": f"/site/{site.id}"} for site in sites]

@app.get("/site/{id}")
# site details with its devices
async def site_page(id: int, session: SessionDep):
    site = session.get(Site, id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return {"id": site.id, "name": site.name,
            "link": f"/site/{site.id}",
            "devices": [
                 {"id": device.id, "name": device.name, "device_type": device.device_type.name,
                  "link": f"/device/{device.id}"} for device in site.devices
                 ] if site.devices else []
            }

@app.post("/site/")
async def site_new(site_data: Site, session: SessionDep):
    session.add(site_data)
    session.commit()
    session.refresh(site_data)
    return site_data

@app.post("/site/{id}")
# create new or edit site
async def site_edit(id: int, 
                    site_data: Site, session: SessionDep):
    site = session.get(Site, id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    site.name = site_data.name
    session.commit()
    session.refresh(site)
    return site

@app.delete("/site/{id}")
# delete site with its devices
async def site_delete(id: int, session: SessionDep):
    site = session.get(Site, id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    session.delete(site)
    session.commit()
    return {"ok": True, "message": f"Site {site.name} deleted"}

@app.get("/device_types/")
# all device types
async def device_types(session: SessionDep):
    device_types = session.exec(select(DeviceType)).all()
    return [{"id": dt.id, "name": dt.name, "link": f"/device_type/{dt.id}"} for dt in device_types]

app.get("/device_type/{id}")
# device_type with its metrics
async def device_type_page(id: int, session: SessionDep):
    device_type = session.get(DeviceType, id)
    if not device_type:
        raise HTTPException(status_code=404, detail="Device Type not found")
    return {"id": device_type.id, "name": device_type.name,
            "link": f"/device_type/{device_type.id}",
            "metrics": [
                {"id": metric.id, "name": metric.name, "unit": metric.unit, "call": metric.call}
                for metric in device_type.metrics
            ] if device_type.metrics else []}

@app.post("/device_type/")
async def device_type_new(device_type: DeviceType, session: SessionDep):
    session.add(device_type)
    session.commit()
    session.refresh(device_type)
    return device_type

@app.post("/device_type/{id}")
# create new or edit site
async def device_type_edit(id: int,
                     device_type_data: DeviceType, session: SessionDep):
    device_type = session.get(DeviceType, id)
    if not device_type:
        raise HTTPException(status_code=404, detail="Device Type not found")
    device_type.name = device_type_data.name
    session.commit()
    session.refresh(device_type)
    return device_type

@app.post("/device_type/{id}/add_metric/{metric_id}")
# add metric to device type
async def device_type_add_metric(id: int, metric_id: int, session: SessionDep):
    device_type = session.get(DeviceType, id)
    if not device_type:
        raise HTTPException(status_code=404, detail="Device Type not found")
    metric = session.get(Metric, metric_id)
    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")
    if metric in device_type.metrics:
        raise HTTPException(status_code=400, detail="Metric already exists in Device Type")
    device_type.metrics.append(metric)
    session.commit()
    session.refresh(device_type)
    return {
        "id": device_type.id,
        "name": device_type.name,
        "link": f"/device_type/{device_type.id}",
        "metrics": [
            {"id": metric.id, "name": metric.name, "unit": metric.unit, "call": metric.call}
            for metric in device_type.metrics
        ]
    }

@app.post("/device_type/{id}/remove_metric/{metric_id}")
# remove metric from device type
async def device_type_remove_metric(id: int, metric_id: int, session: SessionDep):
    device_type = session.get(DeviceType, id)
    if not device_type:
        raise HTTPException(status_code=404, detail="Device Type not found")
    metric = session.get(Metric, metric_id)
    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")
    if metric not in device_type.metrics:   
        raise HTTPException(status_code=400, detail="Metric not found in Device Type")
    device_type.metrics.remove(metric)
    session.commit()
    session.refresh(device_type)
    return {
        "id": device_type.id,
        "name": device_type.name,
        "link": f"/device_type/{device_type.id}",
        "metrics": [
            {"id": metric.id, "name": metric.name, "unit": metric.unit, "call": metric.call}
            for metric in device_type.metrics
        ]
    }

@app.delete("/device_type/{id}")
# delete site with its devices
async def device_type_delete(id: int, session: SessionDep):
    device_type = session.get(DeviceType, id)
    if not device_type:
        raise HTTPException(status_code=404, detail="Device Type not found")
    session.delete(device_type)
    session.commit()
    return {"ok": True, "message": f"Device Type {device_type.name} deleted"}

@app.get("/device/{id}")
# device, its site and device_type with last metrics
async def device(id: int, session: SessionDep):
    device = session.get(Device, id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
        # Query last measure for each metric
    measures = session.exec(
        select(Measure)
        .where(Measure.device_id == id)
        .order_by(Measure.metric_id, Measure.timestamp.desc())
    ).all()

    # Group measures by metric_id and get the latest for each
    last_measures = {}
    for measure in measures:
        if measure.metric_id not in last_measures:
            last_measures[measure.metric_id] = measure

    return {
        "id": device.id,
        "name": device.name,
        "link": f"/device/{device.id}",
        "is_active": device.is_active,
        "site": {"id": device.site.id, "name": device.site.name,
                 "link": f"/site/{device.site.id}"},
        "device_type": {"id": device.device_type.id, "name": device.device_type.name,
                        "link": f"/device_type/{device.device_type.id}"},
        "last_measures": [
            {
                "timestamp": measure.timestamp,
                "metric_id": measure.metric_id,
                "metric_name": measure.metric.name,
                "value": measure.value,
                "unit": measure.metric.unit,
                "link": f"/history/{device.id}/{measure.metric_id}"
            }
            for measure in last_measures.values()
        ],
}

@app.post("/device/device_type/{device_type_id}/site/{site_id}")
# create new device
async def device_new(device: Device, device_type_id: int, site_id:int, session: SessionDep):
    device_type = session.get(DeviceType, device_type_id)
    if not device_type:
        raise HTTPException(status_code=404, detail="Device Type not found")
    site = session.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    device.device_type = device_type
    device.site = site
    if not device.name:
        device.name = device.device_type.name
    session.add(device)
    session.commit()
    session.refresh(device)
    return device
 
@app.post("/device/{id}")
# edit device
async def device_edit(id: int,
                     device_data: Device, session: SessionDep):
    device = session.get(Device, id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    device.name = device_data.name
    device.is_active = device_data.is_active
    site= session.get(Site, device_data.site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    device.site = site
    device_type = session.get(DeviceType, device_data.device_type_id)
    if not device_type:
        raise HTTPException(status_code=404, detail="Device Type not found")
    device.device_type = device_type
    session.commit()
    session.refresh(device)
    return device

@app.delete("/device/{id}")
# delete device
async def device_delete(id: int, session: SessionDep):
    device = session.get(Device, id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    session.delete(device)
    session.commit()
    return {"ok": True, "message": f"Device {device.name} deleted"}
    

@app.get("/metrics/")
# all metrics
async def metrics(session: SessionDep):
    metrics = session.exec(select(Metric)).all()
    return [
        {"id": metric.id, "name": metric.name, "unit": metric.unit, "call": metric.call,
         "link": f"/metric/{metric.id}"}
        for metric in metrics
    ]

@app.get("/metric/{id}")
# metric details
async def metric(id: int, session: SessionDep):
    metric = session.get(Metric, id)
    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")
    return {
        "id": metric.id,
        "name": metric.name,
        "unit": metric.unit,
        "call": metric.call,
        "link": f"/metric/{metric.id}",
    }

@app.post("/metric/")
# create new metric
async def metric_new(metric: Metric, session: SessionDep):
    session.add(metric)
    session.commit()
    session.refresh(metric)
    return metric

@app.post("/metric/{id}")
async def metric_edit(id: int,
                     metric_data: Metric, session: SessionDep):
    metric = session.get(Metric, id)
    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")
    metric.name = metric_data.name
    metric.unit = metric_data.unit
    metric.call = metric_data.call
    session.commit()
    session.refresh(metric)
    return metric

@app.delete("/metric/{id}")
# delete metric
async def metric_delete(id: int, session: SessionDep):
    metric = session.get(Metric, id)
    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")
    session.delete(metric) 
    session.commit()
    return {"ok": True, "message": f"Metric {metric.name} deleted"}

@app.get("/history/{device_id}/{metric_id}")
# get measure history for device and metric
async def measure_history(device_id: int, metric_id: int, session: SessionDep):
    device = session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    metric = session.get(Metric, metric_id)
    if not metric:
        raise HTTPException(status_code=404, detail="Metric not found")
    measures = session.exec(
        select(Measure)
        .where(Measure.device_id == device_id, Measure.metric_id == metric_id)
        .order_by(Measure.timestamp.desc())
    ).all()
    return {
        "device": { 
            "id": device.id,
            "name": device.name,
            "link": f"/device/{device.id}",
            "site": {"id": device.site.id, "name": device.site.name,
                     "link": f"/site/{device.site.id}"},
            "device_type": {"id": device.device_type.id, "name": device.device_type.name,
                            "link": f"/device_type/{device.device_type.id}"}
        },
        "metric": { 
            "id": metric.id,
            "name": metric.name,
            "unit": metric.unit,
        },
        "history": [
            {
                "value": measure.value,
                "timestamp": measure.timestamp
            }
            for measure in measures
        ]
    }


"""
To be implemented later:
@app.get("/subscriptions/")
# current users subscriptions
async def subscriptions():
    return {}

@app.get("/subscribe/{device_id}/{metric_id}")
# current users subscriptions
async def subscribe(device_id: int, metric_id: int):
    return {}

@app.get("/unsubscribe/{id}/")
# current users subscriptions
async def subscribe(id: int):
    return {}

"""