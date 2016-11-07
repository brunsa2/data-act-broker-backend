import traceback

class ValidationError(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, payload=None):
        super(ValidationError, self).__init__()
        self.message = message
        self.status_code = status_code or self.status_code
        self.payload = payload

    def to_dict(self):
        ret = self.payload or {}
        ret['status'] = self.status_code
        ret['message'] = self.message
        return ret

    def get_trace(self):
        return {'trace': traceback.extract_tb(self.__traceback__)}
