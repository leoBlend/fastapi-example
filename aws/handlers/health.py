import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.response import ok


def handler(event, context):
    return ok({"status": "Healthy"})
