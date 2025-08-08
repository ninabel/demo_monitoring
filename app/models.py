# -*- coding: utf-8 -*-
"""
Author: Nina Belyavskaya
"""
from typing import List, Optional

from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime


# Models for the application

# Site model represents a physical location where devices are installed.
class Site(SQLModel, table=True):
    """Model representing a site, which can have multiple devices."""
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)  # Unique name for the site
    devices: list["Device"] = Relationship(back_populates="site")

    @property
    def link(self) -> str: 
        return f"/site/{self.id}/"  # Link to the site view
      
class SiteShort(SQLModel):
    """Model for a short representation of a site."""
    id: int
    name: str
    link: str

class SiteView(SQLModel):
    """Model for viewing a site with its devices."""
    id: int
    name: str
    devices: List["DeviceShort"] = []  # List of devices associated with the site
    

# Metric model represents a metric that can be associated with device types.
class Metric(SQLModel, table=True):
    """Model representing a metric that can be associated with device types."""
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)  # Unique name for the metric
    unit: str = Field(nullable=False)  # Unit of measurement for the metric
    call: str = Field(default="mock")  # Function name to call

    @property
    def link(self) -> str: 
        return f"/metric/{self.id}/"  # Link to the metric view

class MetricShort(SQLModel):
    """Model for a short representation of a metric."""
    id: int
    name: str
    unit: str
    link: str


# Association table for Many-to-Many relationship between DeviceType and Metric.
class DeviceTypeMetricLink(SQLModel, table=True):
    """Association table for Many-to-Many relationship between DeviceType and Metric."""
    device_type_id: int | None = Field(foreign_key="devicetype.id", primary_key=True)
    metric_id: int | None = Field(foreign_key="metric.id", primary_key=True, ondelete="CASCADE")
    

# DeviceType model represents a type of device, which can have multiple metrics associated with it.
class DeviceType(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)  # Unique name for the device type
    
    metrics: list[Metric] = Relationship(
        link_model=DeviceTypeMetricLink
    )

    @property
    def link(self) -> str: 
        return f"/device_type/{self.id}/"  # Link to the device type view

class DeviceTypeShort(SQLModel):
    """Model for a short representation of a device type."""
    id: int
    name: str
    link: str

class DeviceTypeView(SQLModel):
    """Model for viewing a device type with its metrics."""
    id: int
    name: str
    metrics: List[MetricShort] = []  # List of metrics associated with the device type  

# Device model represents a physical device that is associated with a site and a device type.
class Device(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True) 
    site_id: int | None = Field(foreign_key="site.id", nullable=False, ondelete="CASCADE")
    device_type_id: int | None = Field(foreign_key="devicetype.id", nullable=False, ondelete="CASCADE")
    is_active: bool = Field(default=True)

    site: Site = Relationship(back_populates="devices")
    device_type: DeviceType = Relationship()

    @property
    def link(self) -> str: 
        return f"/device/{self.id}/"  # Link to the device view

class DeviceShort(SQLModel):
    """Model for a short representation of a device."""
    id: int
    name: str
    is_active: bool = True
    link: str  # Link to the device view

class DeviceView(SQLModel):
    """Model for viewing a device with its last measures."""
    id: int
    name: str
    is_active: bool = True
    site: SiteShort  # Site associated with the device
    device_type: DeviceTypeShort # Device type associated with the device
    last_measures: List["LastMeasure"] = []  # List of last measures for the device

# Measure model represents a measurement taken by a device for a specific metric at a given time.
class Measure(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    device_id: int | None = Field(foreign_key="device.id", ondelete="CASCADE")
    metric_id: int | None = Field(foreign_key="metric.id", ondelete="CASCADE")
    value: float
    timestamp: datetime

    device: Device = Relationship()
    metric: Metric = Relationship()

# LastMeasure model represents the last measurement for a device and metric.
# It is used in the device view to show the most recent measure.
class LastMeasure(SQLModel):
    timestamp: datetime
    metric: str
    value: float
    unit: str
    link: str  # Link to the history of this measure

# MeasureShort model is a simplified version of Measure for use in lists.
class MeasureShort(SQLModel):
    """Model for a short representation of a measure."""
    timestamp: datetime
    value: float
    
# MeasuresHistory model represents the history of measures for a device and metric.
class MeasuresHistory(SQLModel):
    """Model for the history of measures for a device and metric."""
    device: DeviceShort  # Device associated with the measures
    site: SiteShort  # site associated with the device
    device_type: DeviceTypeShort  # Device type associated with the measures
    metric: MetricShort  # Metric associated with the measures
    history: List[MeasureShort] = []  # List of measures for the device and metric
