from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """Convert Django model ValidationErrors into 400 responses with DRF-style bodies."""
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            data = exc.message_dict
        else:
            data = {"detail": exc.messages[0] if len(exc.messages) == 1 else exc.messages}
        return Response(data, status=status.HTTP_400_BAD_REQUEST)
    return exception_handler(exc, context)
