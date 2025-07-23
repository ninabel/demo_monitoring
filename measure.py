# -*- coding: utf-8 -*-
"""
Author: Nina Belyavskaya
"""
from models import Device, Metric

def mock(metric: Metric, device: Device) -> float:
    """
    Mock function to simulate fetching a metric value for a device.
    In a real application, this would call the actual metric retrieval logic.
    """
    from random import randrange
    return randrange(1, 100)  # Simulating a metric value between 1 and 100