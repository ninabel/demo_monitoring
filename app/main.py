# -*- coding: utf-8 -*-
"""
Author: Nina Belyavskaya
"""

from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI, HTTPException, status, Depends
from .models import Device, Metric, Site, DeviceType, Measure
from .measure import mock
from .db import AsyncSession, create_db_and_tables, get_async_session, async_session_maker
from sqlmodel import select
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone
from fastapi.logger import logger
from sqlalchemy.orm import selectinload

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield

app = FastAPI(title="Device Monitoring API", lifespan=lifespan)


async def measure_devices():
    """
    Function to measure devices and store results in the database.
    This function should be called periodically by the scheduler.
    """
    logger.info("Starting measurement of devices")
    async with async_session_maker() as session:
        res = await session.execute(select(Device).options(
            selectinload(Device.device_type).selectinload(DeviceType.metrics)
        ).where(Device.is_active))
        devices = res.scalars().all()
        for device in devices:
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
        await session.commit()
    logger.info("Measurement of devices completed")

def measure_devices_job():
    asyncio.run(measure_devices())

# Initialize the scheduler to run measure_devices every 30 seconds
scheduler = BackgroundScheduler()
scheduler.add_job(measure_devices_job, 'interval', seconds=180)
scheduler.start()

@app.get("/")
# main page with all sites
async def sites(session: AsyncSession = Depends(get_async_session)):
    res = await session.execute(select(Site))
    sites = res.scalars().all()
    if not sites:
        print("The system is empty, please create a site first.")
        return {"message": "The system is empty, please create a site first."}
    return [{"id": site.id, "name": site.name, "link": f"/site/{site.id}"} for site in sites]

@app.get("/site/{id}")
# site details with its devices
async def site_page(id: int, session: AsyncSession = Depends(get_async_session)):
    res = await session.execute(select(Site).options(
            selectinload(Site.devices).selectinload(Device.device_type)
        ).where(Site.id==id))
    site = res.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    return {"id": site.id, "name": site.name,
            "link": f"/site/{site.id}",
            "devices": [
                 {"id": device.id, "name": device.name, "device_type": device.device_type.name,
                  "link": f"/device/{device.id}"} for device in site.devices
                 ] if site.devices else []
            }

@app.post("/site/")
# create new site
async def site_new(site_data: Site, session: AsyncSession = Depends(get_async_session)):
    session.add(site_data)
    await session.commit()
    session.refresh(site_data)
    return site_data

@app.post("/site/{id}")
# edit site
async def site_edit(id: int, 
                    site_data: Site, session: AsyncSession = Depends(get_async_session)):
    res = await session.execute(select(Site).where(Site.id==id))
    site = res.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    site.name = site_data.name
    await session.commit()
    session.refresh(site)
    return site

@app.delete("/site/{id}")
# delete site with its devices
async def site_delete(id: int, session: AsyncSession = Depends(get_async_session)):
    res = await session.execute(select(Site).where(Site.id==id))
    site = res.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    session.delete(site)
    await session.commit()
    return {"ok": True, "message": f"Site {site.name} deleted"}

@app.get("/device_types/")
# all device types
async def device_types(session: AsyncSession = Depends(get_async_session)):
    res = await session.execute(select(DeviceType))
    device_types = res.scalars().all()
    return [{"id": dt.id, "name": dt.name, "link": f"/device_type/{dt.id}"} for dt in device_types]

@app.get("/device_type/{id}")
# device_type with its metrics
async def device_type_page(id: int, session: AsyncSession = Depends(get_async_session)):
    res = await session.execute(select(DeviceType).options(
        selectinload(DeviceType.metrics)
    ).where(DeviceType.id==id))
    device_type = res.scalar_one_or_none()
    if not device_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device Type not found")
    return {"id": device_type.id, "name": device_type.name,
            "link": f"/device_type/{device_type.id}",
            "metrics": [
                {"id": metric.id, "name": metric.name, "unit": metric.unit, "call": metric.call}
                for metric in device_type.metrics
            ] if device_type.metrics else []}

@app.post("/device_type/")
async def device_type_new(device_type: DeviceType, session: AsyncSession = Depends(get_async_session)):
    session.add(device_type)
    await session.commit()
    session.refresh(device_type)
    return device_type

@app.post("/device_type/{id}")
# create new or edit site
async def device_type_edit(id: int,
                     device_type_data: DeviceType, session: AsyncSession = Depends(get_async_session)):
    res = await session.execute(select(DeviceType).where(DeviceType.id==id))
    device_type = res.scalar_one_or_none()
    if not device_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device Type not found")
    device_type.name = device_type_data.name
    await session.commit()
    session.refresh(device_type)
    return device_type

@app.post("/device_type/{id}/add_metric/{metric_id}")
# add metric to device type
async def device_type_add_metric(id: int, metric_id: int, session: AsyncSession = Depends(get_async_session)):
    res = await session.execute(select(DeviceType).options(
        selectinload(DeviceType.metrics)
    ).where(DeviceType.id==id))
    device_type = res.scalar_one_or_none()
    if not device_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device Type not found")
    res = await session.execute(select(Metric).where(Metric.id==id))
    metric = res.scalar_one_or_none()
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric not found")
    if metric in device_type.metrics:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Metric already exists in Device Type")
    device_type.metrics.append(metric)
    await session.commit()
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
async def device_type_remove_metric(id: int, metric_id: int, session: AsyncSession = Depends(get_async_session)):
    res = await session.execute(select(DeviceType).options(
        selectinload(DeviceType.metrics)
    ).where(DeviceType.id==id))
    device_type = res.scalar_one_or_none()
    if not device_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device Type not found")
    res = await session.execute(select(Metric).where(Metric.id==id))
    metric = res.scalar_one_or_none()
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric not found")
    if metric not in device_type.metrics:   
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Metric not found in Device Type")
    device_type.metrics.remove(metric)
    await session.commit()
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
# delete device_type
async def device_type_delete(id: int, session: AsyncSession = Depends(get_async_session)):
    res = await session.execute(select(DeviceType).where(DeviceType.id==id))
    device_type = res.scalar_one_or_none()
    if not device_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device Type not found")
    session.delete(device_type)
    await session.commit()
    return {"ok": True, "message": f"Device Type {device_type.name} deleted"}

@app.get("/device/{id}")
# device, its site and device_type with last metrics
async def device(id: int, session: AsyncSession = Depends(get_async_session)):
    res = await session.execute(select(Device).options(
        selectinload(Device.site),selectinload(Device.device_type)
    ).where(Device.id==id))
    device = res.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    
    # Query last measure for each metric
    res = await session.execute(
        select(Measure).options(
            selectinload(Measure.metric)
        ).where(Measure.device_id == id)
        .order_by(Measure.metric_id, Measure.timestamp.desc())
    )
    measures = res.scalars().all()

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
async def device_new(device: Device, device_type_id: int, site_id:int, session: AsyncSession = Depends(get_async_session)):
    res = await session.execute(select(DeviceType).where(DeviceType.id==id))
    device_type = res.scalar_one_or_none()
    if not device_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device Type not found")
    res = await session.execute(select(Site).where(Site.id==id))
    site = res.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    device.device_type = device_type
    device.site = site
    if not device.name:
        device.name = device.device_type.name
    session.add(device)
    await session.commit()
    session.refresh(device)
    return device
 
@app.post("/device/{id}")
# edit device
async def device_edit(id: int,
                     device_data: Device, session: AsyncSession = Depends(get_async_session)):
    res = await session.execute(select(Device).where(Device.id==id))
    device = res.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    device.name = device_data.name
    device.is_active = device_data.is_active
    res = await session.execute(select(Site).where(Site.id==id))
    site = res.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    device.site = site
    res = await session.execute(select(DeviceType).where(DeviceType.id==id))
    device_type = res.scalar_one_or_none()
    if not device_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device Type not found")
    device.device_type = device_type
    await session.commit()
    session.refresh(device)
    return device

@app.delete("/device/{id}")
# delete device
async def device_delete(id: int, session: AsyncSession = Depends(get_async_session)):
    res = await session.execute(select(Device).where(Device.id==id))
    device = res.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    session.delete(device)
    await session.commit()
    return {"ok": True, "message": f"Device {device.name} deleted"}
    

@app.get("/metrics/")
# all metrics
async def metrics(session: AsyncSession = Depends(get_async_session)):
    res = await session.execute(select(Metric))
    metrics = res.scalars().all()
    return [
        {"id": metric.id, "name": metric.name, "unit": metric.unit, "call": metric.call,
         "link": f"/metric/{metric.id}"}
        for metric in metrics
    ]

@app.get("/metric/{id}")
# metric details
async def metric(id: int, session: AsyncSession = Depends(get_async_session)):
    res = await session.execute(select(Metric).where(Metric.id==id))
    metric = res.scalar_one_or_none()
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric not found")
    return {
        "id": metric.id,
        "name": metric.name,
        "unit": metric.unit,
        "call": metric.call,
        "link": f"/metric/{metric.id}",
    }

@app.post("/metric/")
# create new metric
async def metric_new(metric: Metric, session: AsyncSession = Depends(get_async_session)):
    session.add(metric)
    await session.commit()
    session.refresh(metric)
    return metric

@app.post("/metric/{id}")
async def metric_edit(id: int,
                     metric_data: Metric, session: AsyncSession = Depends(get_async_session)):
    res = await session.execute(select(Metric).where(Metric.id==id))
    metric = res.scalar_one_or_none()
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric not found")
    metric.name = metric_data.name
    metric.unit = metric_data.unit
    metric.call = metric_data.call
    await session.commit()
    session.refresh(metric)
    return metric

@app.delete("/metric/{id}")
# delete metric
async def metric_delete(id: int, session: AsyncSession = Depends(get_async_session)):
    res = await session.execute(select(Metric).where(Metric.id==id))
    metric = res.scalar_one_or_none()
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric not found")
    session.delete(metric) 
    await session.commit()
    return {"ok": True, "message": f"Metric {metric.name} deleted"}

@app.get("/history/{device_id}/{metric_id}")
# get measure history for device and metric
async def measure_history(device_id: int, metric_id: int, session: AsyncSession = Depends(get_async_session)):
    res = await session.execute(select(Device).options(
        selectinload(Device.site), selectinload(Device.device_type)
    ).where(Device.id==device_id))
    device = res.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    res = await session.execute(select(Metric).where(Metric.id==metric_id))
    metric = res.scalar_one_or_none()
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric not found")
    res = await session.execute(
        select(Measure)
        .where(Measure.device_id == device.id, Measure.metric_id == metric.id)
        .order_by(Measure.timestamp.desc())
    )
    measures = res.scalars().all()
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