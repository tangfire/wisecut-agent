"""Unified error model matching the Go Client's AgentFilmHTTPError."""

from __future__ import annotations

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Standard error response body for non-2xx responses.

    Matches the Go Client's AgentFilmHTTPError struct:
      Method     string
      Path       string
      StatusCode int
      Body       string
    """

    method: str
    path: str
    status_code: int
    body: str


class MAAException(Exception):
    """Base exception for MAA application errors."""

    def __init__(self, method: str, path: str, status_code: int, detail: str) -> None:
        self.method = method
        self.path = path
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)

    def to_response(self) -> ErrorResponse:
        return ErrorResponse(
            method=self.method,
            path=self.path,
            status_code=self.status_code,
            body=self.detail,
        )


class ConversationNotFound(MAAException):
    def __init__(self, conversation_id: str) -> None:
        super().__init__(
            method="GET",
            path=f"/conversations/{conversation_id}",
            status_code=404,
            detail=f"conversation not found: {conversation_id}",
        )


class RunNotFound(MAAException):
    def __init__(self, run_id: str) -> None:
        super().__init__(
            method="GET",
            path=f"/runs/{run_id}/events",
            status_code=404,
            detail=f"run not found: {run_id}",
        )


class RunTerminalError(MAAException):
    def __init__(self, run_id: str, status: str) -> None:
        super().__init__(
            method="POST",
            path=f"/runs/{run_id}/cancel",
            status_code=409,
            detail=f"run is already in terminal state: {status}",
        )


class ValidationError(MAAException):
    def __init__(self, path: str, detail: str) -> None:
        super().__init__(
            method="",
            path=path,
            status_code=422,
            detail=detail,
        )


class ApprovalNotFound(MAAException):
    def __init__(self, approval_id: str) -> None:
        super().__init__(
            method="POST",
            path=f"/approvals/{approval_id}/decide",
            status_code=404,
            detail=f"approval not found: {approval_id}",
        )


class ArtifactNotFound(MAAException):
    def __init__(self, conversation_id: str, artifact_id: str) -> None:
        super().__init__(
            method="GET",
            path=f"/conversations/{conversation_id}/artifacts/{artifact_id}",
            status_code=404,
            detail=f"artifact not found: {artifact_id}",
        )
