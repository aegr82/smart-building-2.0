# Minimal stub for EnergyAgent.
# This file is intentionally minimal so the app can import the class.

class EnergyAgent:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key

    def is_configured(self) -> bool:
        return bool(self.api_key)

