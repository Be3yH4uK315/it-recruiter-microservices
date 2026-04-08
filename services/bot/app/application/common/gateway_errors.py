"""HTTP gateway errors raised by backend integrations (application-facing, no infra imports)."""


class CandidateGatewayError(RuntimeError):
    pass


class CandidateGatewayUnauthorizedError(CandidateGatewayError):
    pass


class CandidateGatewayForbiddenError(CandidateGatewayError):
    pass


class CandidateGatewayUnavailableError(CandidateGatewayError):
    pass


class CandidateGatewayConflictError(CandidateGatewayError):
    pass


class CandidateGatewayValidationError(CandidateGatewayError):
    pass


class CandidateGatewayRateLimitedError(CandidateGatewayError):
    pass


class CandidateGatewayProtocolError(CandidateGatewayError):
    pass


class EmployerGatewayError(RuntimeError):
    pass


class EmployerGatewayUnauthorizedError(EmployerGatewayError):
    pass


class EmployerGatewayForbiddenError(EmployerGatewayError):
    pass


class EmployerGatewayUnavailableError(EmployerGatewayError):
    pass


class EmployerGatewayNotFoundError(EmployerGatewayError):
    pass


class EmployerGatewayConflictError(EmployerGatewayError):
    pass


class EmployerGatewayValidationError(EmployerGatewayError):
    pass


class EmployerGatewayRateLimitedError(EmployerGatewayError):
    pass


class EmployerGatewayProtocolError(EmployerGatewayError):
    pass
