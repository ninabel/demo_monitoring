# -*- coding: utf-8 -*-
"""
Author: Nina Belyavskaya
"""

from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI, HTTPException, status, Depends
from .models import (
    Device, DeviceShort, DeviceView,
    Metric, MetricShort, 
    Site, SiteShort, SiteView, 
    DeviceType, DeviceTypeShort, DeviceTypeView,
    Measure, LastMeasure, MeasureShort, MeasuresHistory
)
from .measure import mock
from .db import AsyncSession, create_db_and_tables, get_async_session, async_session_maker
from sqlmodel import select
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone
from fastapi.logger import logger
from sqlalchemy.orm import selectinload

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler to create the database and tables at startup.
    This function is called when the FastAPI application starts.
    """
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
    """
    Job to run the measure_devices function periodically.
    This function is called by the scheduler.
    """
    asyncio.run(measure_devices())

# Initialize the scheduler to run measure_devices every 30 seconds
scheduler = BackgroundScheduler()
scheduler.add_job(measure_devices_job, 'interval', seconds=180)
scheduler.start()

@app.get("/", response_model=dict|list[SiteShort])
# return string if sitelist is empty or SiteList with links to sites
async def sites(session: AsyncSession = Depends(get_async_session)): 
    """
    Main page that lists all sites.
    """
    res = await session.execute(select(Site))
    sites = res.scalars().all()
    if not sites:
        print("The system is empty, please create a site first.")
        return {"message": "The system is empty, please create a site first."}
    return [SiteShort(
        id=site.id, name=site.name, link=site.link
        ) for site in sites]

@app.get("/site/{id}", response_model=SiteView)
# site details with its devices
async def site_page(id: int, session: AsyncSession = Depends(get_async_session)):
    """
    Get details of a specific site by its ID.
    This endpoint returns the site information along with its devices and their types.
    """
    res = await session.execute(select(Site).options(
            selectinload(Site.devices).selectinload(Device.device_type)
        ).where(Site.id==id))
    site = res.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    return SiteView(
        id=site.id,
        name=site.name,
        devices=[DeviceShort(
            id=device.id, name=device.name, link=device.link,    
        ) for device in site.devices]
     ) if site.devices else []

@app.post("/site/", response_model=Site)
# create new site
async def site_new(site: Site, session: AsyncSession = Depends(get_async_session)):
    """
    Create a new site.
    This endpoint allows you to create a new site with a unique name.
    """
    session.add(site)
    await session.commit()
    session.refresh(site)
    return site

@app.post("/site/{id}", response_model=Site)
# edit site
async def site_edit(id: int, 
                    site_data: Site, session: AsyncSession = Depends(get_async_session)):
    """
    Edit an existing site by its ID.
    This endpoint allows you to update the name of a site.
    """
    res = await session.execute(select(Site).where(Site.id==id))
    site = res.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    site.name = site_data.name
    await session.commit()
    session.refresh(site)
    return site

@app.delete("/site/{id}", response_model=dict)
# delete site with its devices
async def site_delete(id: int, session: AsyncSession = Depends(get_async_session)):
    """
    Delete a site by its ID.
    This endpoint removes the site and all associated devices.
    """
    res = await session.execute(select(Site).where(Site.id==id))
    site = res.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site not found")
    session.delete(site)
    await session.commit()
    return {"ok": True, "message": f"Site {site.name} deleted"}

@app.get("/device_types/", response_model=list[DeviceTypeShort])
# all device types
async def device_types(session: AsyncSession = Depends(get_async_session)):
    """Get a list of all device types.
    This endpoint returns all device types available in the system.
    """
    res = await session.execute(select(DeviceType))
    device_types = res.scalars().all()
    return [
        DeviceTypeShort(
            id=dt.id, name=dt.name, link=dt.link
        ) for dt in device_types]

@app.get("/device_type/{id}", response_model=DeviceTypeView)
# device_type with its metrics
async def device_type_page(id: int, session: AsyncSession = Depends(get_async_session)):
    """
    Get details of a specific device type by its ID.
    This endpoint returns the device type information along with its metrics.
    """
    res = await session.execute(select(DeviceType).options(
        selectinload(DeviceType.metrics)
    ).where(DeviceType.id==id))
    device_type = res.scalar_one_or_none()
    if not device_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device Type not found")
    return DeviceTypeView(id=device_type.id, name=device_type.name,
            link=device_type.link,
            # Include metrics if they exist",
            metrics=[MetricShort(
                id=metric.id, name=metric.name, unit=metric.unit, 
                link=metric.link
            ) for metric in device_type.metrics]
            if device_type.metrics else [])

@app.post("/device_type/", response_model=DeviceType)
# create new device type
async def device_type_new(device_type: DeviceType, session: AsyncSession = Depends(get_async_session)):
    session.add(device_type)
    await session.commit()
    session.refresh(device_type)
    return device_type

@app.post("/device_type/{id}", response_model=DeviceType)
# create new or edit device type
async def device_type_edit(id: int,
                     device_type_data: DeviceType, session: AsyncSession = Depends(get_async_session)):
    """
    Edit an existing device type by its ID.
    This endpoint allows you to update the name of a device type.
    """    
    res = await session.execute(select(DeviceType).where(DeviceType.id==id))
    device_type = res.scalar_one_or_none()
    if not device_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device Type not found")
    device_type.name = device_type_data.name
    await session.commit()
    session.refresh(device_type)
    return device_type

@app.post("/device_type/{id}/add_metric/{metric_id}", response_model=DeviceTypeView)
# add metric to device type
async def device_type_add_metric(id: int, metric_id: int, session: AsyncSession = Depends(get_async_session)):
    """Add a metric to a device type.
    This endpoint associates a metric with a device type by their IDs.
    If the metric is already associated, it raises an error.
    """
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
    return DeviceTypeView(
        id=device_type.id,
        name=device_type.name,
        link=device_type.link,
        metrics=[MetricShort(
            id=metric.id, name=metric.name, unit=metric.unit,
            link=metric.link
            ) for metric in device_type.metrics
        ]
    )

@app.post("/device_type/{id}/remove_metric/{metric_id}", response_model=DeviceTypeView)
# remove metric from device type
async def device_type_remove_metric(id: int, metric_id: int, session: AsyncSession = Depends(get_async_session)):
    """Remove a metric from a device type.
    This endpoint disassociates a metric from a device type by their IDs.
    If the metric is not associated with the device type, it raises an error.
    """
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
    return DeviceTypeView(
        id=device_type.id,
        name=device_type.name,
        link=device_type.link,
        metrics=[MetricShort(
            id=metric.id, name=metric.name, unit=metric.unit,
            link=metric.link
            ) for metric in device_type.metrics
        ]
    )


@app.delete("/device_type/{id}", response_model=dict)
# delete device_type
async def device_type_delete(id: int, session: AsyncSession = Depends(get_async_session)):
    """Delete a device type by its ID.
    This endpoint removes the device type and all associated devices.
    """
    res = await session.execute(select(DeviceType).where(DeviceType.id==id))
    device_type = res.scalar_one_or_none()
    if not device_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device Type not found")
    session.delete(device_type)
    await session.commit()
    return {"ok": True, "message": f"Device Type {device_type.name} deleted"}

@app.get("/device/{id}", response_model=DeviceView)
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

    return DeviceView(
        id=device.id,
        name=device.name,
        link=device.link,
        is_active=device.is_active,
        site=SiteShort(
            id=device.site.id, name=device.site.name, link=device.site.link
        ),
        device_type=DeviceTypeShort(
            id=device.device_type.id, name=device.device_type.name, link=device.device_type.link
        ),
        last_measures=[LastMeasure(
                timestamp=measure.timestamp,
                metric=measure.metric.name,
                value=measure.value,
                unit=measure.metric.unit,
                link=f"/history/{device.id}/{measure.metric_id}"
            )
            for measure in last_measures.values()
        ])


@app.post("/device/device_type/{device_type_id}/site/{site_id}", response_model=Device)
# create new device
async def device_new(device: Device, device_type_id: int, site_id:int, session: AsyncSession = Depends(get_async_session)):
    """Create a new device associated with a device type and site.
    This endpoint allows you to create a new device with a unique name, device type, and site.
    If the device type or site does not exist, it raises an error.
    """
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
 
@app.post("/device/{id}", response_model=Device)
# edit device
async def device_edit(id: int,
                     device_data: Device, session: AsyncSession = Depends(get_async_session)):
    """Edit an existing device by its ID.
    This endpoint allows you to update the name, site, and device type of a device.
    If the device does not exist, it raises an error.
    """
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

@app.delete("/device/{id}", response_model=dict)
# delete device
async def device_delete(id: int, session: AsyncSession = Depends(get_async_session)):
    """Delete a device by its ID.
    This endpoint removes the device and all associated measures.
    If the device does not exist, it raises an error.
    """
    res = await session.execute(select(Device).where(Device.id==id))
    device = res.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    session.delete(device)
    await session.commit()
    return {"ok": True, "message": f"Device {device.name} deleted"}
    

@app.get("/metrics/", response_model=list[MetricShort])
# all metrics
async def metrics(session: AsyncSession = Depends(get_async_session)):
    """
    Get a list of all metrics.
    This endpoint returns all metrics available in the system.
    """
    res = await session.execute(select(Metric))
    metrics = res.scalars().all()
    return [MetricShort(
        id=metric.id, name=metric.name, unit=metric.unit, link=metric.link
    ) for metric in metrics]

@app.get("/metric/{id}", response_model=Metric)
# metric details
async def metric(id: int, session: AsyncSession = Depends(get_async_session)):
    """Get details of a specific metric by its ID.
    This endpoint returns the metric information including its name, unit, and call function.
    """
    res = await session.execute(select(Metric).where(Metric.id==id))
    metric = res.scalar_one_or_none()
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric not found")
    return metric

@app.post("/metric/", response_model=Metric)
# create new metric
async def metric_new(metric: Metric, session: AsyncSession = Depends(get_async_session)):
    """Create a new metric.
    This endpoint allows you to create a new metric with a unique name, unit, and call function.
    """
    session.add(metric)
    await session.commit()
    session.refresh(metric)
    return metric

@app.post("/metric/{id}", response_model=Metric)
# edit metric
async def metric_edit(id: int,
                     metric_data: Metric, session: AsyncSession = Depends(get_async_session)):
    """Edit an existing metric by its ID.
    This endpoint allows you to update the name, unit, and call function of a metric.
    If the metric does not exist, it raises an error.
    """
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

@app.delete("/metric/{id}", response_model=dict)
# delete metric
async def metric_delete(id: int, session: AsyncSession = Depends(get_async_session)):
    """Delete a metric by its ID.
    This endpoint removes the metric and all associated device type links.
    If the metric does not exist, it raises an error.
    """
    res = await session.execute(select(Metric).where(Metric.id==id))
    metric = res.scalar_one_or_none()
    if not metric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric not found")
    session.delete(metric) 
    await session.commit()
    return {"ok": True, "message": f"Metric {metric.name} deleted"}

@app.get("/history/{device_id}/{metric_id}", response_model=MeasuresHistory)
# get measure history for device and metric
async def measures_history(device_id: int, metric_id: int, session: AsyncSession = Depends(get_async_session)):
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
    return MeasuresHistory(
        device=DeviceShort(
            id=device.id,
            name=device.name,
            link=device.link,
        ),
        site=SiteShort(
            id=device.site.id, name=device.site.name, link=device.site.link
        ),
        device_type=DeviceTypeShort(
            id=device.device_type.id, name=device.device_type.name, link=device.device_type.link
        ),
        metric=MetricShort(
            id=metric.id,
            name=metric.name,
            unit=metric.unit,
            link=metric.link
        ),
        history=[
            MeasureShort(
                value=measure.value,
                timestamp=measure.timestamp
            )
            for measure in measures
        ]
    )


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