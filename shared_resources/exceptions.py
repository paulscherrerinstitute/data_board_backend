class DashboardSizeError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class DashboardValidationError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)