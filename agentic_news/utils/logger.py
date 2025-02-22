class Logger:
    def __init__(self):
        self.log_file = None

    def log(self, message, color=None):
        print(message)
        return message 