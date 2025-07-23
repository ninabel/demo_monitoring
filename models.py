# -*- coding: utf-8 -*-
"""
Author: Nina Belyavskaya
"""

from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime

class Site(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)  # Unique name for the site

    devices: list["Device"] = Relationship(back_populates="site")

class Metric(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)  # Unique name for the metric
    unit: str = Field(nullable=False)  # Unit of measurement for the metric
    call: str = Field(default="mock")  # Function name to call

class DeviceTypeMetricLink(SQLModel, table=True):
    """Association table for Many-to-Many relationship between DeviceType and Metric."""
    device_type_id: int | None = Field(foreign_key="devicetype.id", primary_key=True)
    metric_id: int | None = Field(foreign_key="metric.id", primary_key=True, ondelete="CASCADE")
    
class DeviceType(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)  # Unique name for the device type
    
    metrics: list[Metric] = Relationship(
        link_model=DeviceTypeMetricLink
    )

class Device(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True) 
    site_id: int | None = Field(foreign_key="site.id", nullable=False, ondelete="CASCADE")
    device_type_id: int | None = Field(foreign_key="devicetype.id", nullable=False, ondelete="CASCADE")
    is_active: bool = Field(default=True)

    site: Site = Relationship(back_populates="devices")
    device_type: DeviceType = Relationship()
    

class Measure(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    device_id: int | None = Field(foreign_key="device.id", ondelete="CASCADE")
    metric_id: int | None = Field(foreign_key="metric.id", ondelete="CASCADE")
    value: float
    timestamp: datetime

    device: Device = Relationship()
    metric: Metric = Relationship()