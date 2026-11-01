class DependencyUnavailable(FileNotFoundError):
    def __init__(self, dependency: str):
        messages = {
            "atlas": (
                "atlas-unavailable",
                "Atlas Jira access is unavailable.",
            ),
            "noc-tools": (
                "noc-tools-unavailable",
                "The required noc-tools command is unavailable.",
            ),
            "microsoft365": (
                "microsoft365-unavailable",
                "Microsoft 365 CLI is unavailable.",
            ),
        }
        self.dependency = dependency
        self.code, message = messages[dependency]
        self.message = message
        super().__init__(message)


class ExternalOperationFailed(RuntimeError):
    def __init__(self, dependency: str):
        messages = {
            "atlas": (
                "atlas-operation-failed",
                "The Atlas Jira operation failed.",
            ),
            "noc-tools": (
                "noc-tools-operation-failed",
                "The noc-tools operation failed.",
            ),
            "microsoft365": (
                "microsoft365-operation-failed",
                "The Microsoft 365 operation failed.",
            ),
        }
        self.dependency = dependency
        self.code, message = messages[dependency]
        self.message = message
        super().__init__(message)
