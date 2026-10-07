from django.conf import settings
from django.contrib.auth import authenticate, password_validation
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core import audit
from apps.core.models import AuditLog
from apps.core.permissions import HasPermissionCode
from apps.core.views_mixins import AuditedModelViewSet

from .models import Permission, Role, User
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    MeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    PermissionSerializer,
    RoleSerializer,
    UserSerializer,
)


def _set_refresh_cookie(response, refresh):
    response.set_cookie(
        settings.JWT_REFRESH_COOKIE,
        str(refresh),
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        httponly=True,
        secure=settings.JWT_REFRESH_COOKIE_SECURE,
        samesite=settings.JWT_REFRESH_COOKIE_SAMESITE,
        path=settings.JWT_REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response):
    response.delete_cookie(settings.JWT_REFRESH_COOKIE, path=settings.JWT_REFRESH_COOKIE_PATH)


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(request=LoginSerializer, responses={200: MeSerializer})
    def post(self, request):
        ser = LoginSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = authenticate(request, username=ser.validated_data["username"], password=ser.validated_data["password"])
        if user is None:
            audit.record(
                AuditLog.Action.LOGIN_FAILED, model="accounts.User",
                message=f"Failed login for username '{ser.validated_data['username'][:150]}'",
            )
            # Same message whether the user exists, is inactive or the password is wrong.
            return Response({"detail": "Invalid credentials or inactive account."}, status=status.HTTP_401_UNAUTHORIZED)
        refresh = RefreshToken.for_user(user)
        from django.contrib.auth.models import update_last_login

        update_last_login(None, user)
        audit.record(AuditLog.Action.LOGIN, user, user=user)
        response = Response({"access": str(refresh.access_token), "user": MeSerializer(user).data})
        _set_refresh_cookie(response, refresh)
        return response


class RefreshView(APIView):
    """Issue a new access token using the httpOnly refresh cookie (rotated on every call)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=None, responses={200: MeSerializer}, description="Uses the httpOnly refresh cookie.")
    def post(self, request):
        raw = request.COOKIES.get(settings.JWT_REFRESH_COOKIE)
        if not raw:
            return Response({"detail": "No refresh token."}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            old = RefreshToken(raw)
            user = User.objects.get(pk=old["user_id"])
            if not user.is_active:
                raise TokenError("inactive")
            old.blacklist()
            new = RefreshToken.for_user(user)
        except (TokenError, User.DoesNotExist, KeyError):
            response = Response({"detail": "Session expired."}, status=status.HTTP_401_UNAUTHORIZED)
            _clear_refresh_cookie(response)
            return response
        response = Response({"access": str(new.access_token), "user": MeSerializer(user).data})
        _set_refresh_cookie(response, new)
        return response


class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        raw = request.COOKIES.get(settings.JWT_REFRESH_COOKIE)
        user = None
        if raw:
            try:
                token = RefreshToken(raw)
                user = User.objects.filter(pk=token["user_id"]).first()
                token.blacklist()
            except TokenError:
                pass
        if user:
            audit.record(AuditLog.Action.LOGOUT, user, user=user)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        _clear_refresh_cookie(response)
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=MeSerializer)
    def get(self, request):
        return Response(MeSerializer(request.user).data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=ChangePasswordSerializer, responses={204: None})
    def post(self, request):
        ser = ChangePasswordSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        request.user.set_password(ser.validated_data["new_password"])
        request.user.must_change_password = False
        request.user.save(update_fields=["password", "must_change_password"])
        audit.record(AuditLog.Action.PASSWORD_CHANGE, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    @extend_schema(request=PasswordResetRequestSerializer, responses={200: None})
    def post(self, request):
        ser = PasswordResetRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=ser.validated_data["email"], is_active=True).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            link = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
            send_mail(
                "Bravado Payroll password reset",
                f"Hello {user.get_full_name() or user.username},\n\nUse the link below to reset your password. "
                f"It expires in {settings.PASSWORD_RESET_TIMEOUT // 60} minutes.\n\n{link}\n\n"
                "If you did not request this, ignore this email.",
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            audit.record(AuditLog.Action.PASSWORD_RESET, user, user=user, message="Reset requested")
        # Never reveal whether the address exists.
        return Response({"detail": "If the address is registered, a reset link has been sent."})


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    @extend_schema(request=PasswordResetConfirmSerializer, responses={204: None})
    def post(self, request):
        ser = PasswordResetConfirmSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            uid = force_str(urlsafe_base64_decode(ser.validated_data["uid"]))
            user = User.objects.get(pk=uid, is_active=True)
        except (ValueError, TypeError, OverflowError, User.DoesNotExist):
            user = None
        if user is None or not default_token_generator.check_token(user, ser.validated_data["token"]):
            raise ValidationError({"token": "Invalid or expired reset link."})
        try:
            password_validation.validate_password(ser.validated_data["new_password"], user)
        except DjangoValidationError as e:
            raise ValidationError({"new_password": list(e.messages)})
        user.set_password(ser.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        audit.record(AuditLog.Action.PASSWORD_RESET, user, user=user, message="Password reset completed")
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserViewSet(AuditedModelViewSet):
    queryset = User.objects.select_related("role").all()
    serializer_class = UserSerializer
    required_permissions = {"*": "users.manage"}
    search_fields = ["username", "email", "first_name", "last_name"]
    filterset_fields = ["is_active", "role__code"]
    ordering_fields = ["username", "email", "last_login", "date_joined"]
    allow_destroy = False

    def perform_update(self, serializer):
        old_role = serializer.instance.role_id
        super().perform_update(serializer)
        if serializer.instance.role_id != old_role:
            audit.record(
                AuditLog.Action.PERMISSION_CHANGE, serializer.instance,
                old={"role_id": old_role}, new={"role_id": serializer.instance.role_id},
            )

    def _set_active(self, request, active):
        user = self.get_object()
        if user == request.user and not active:
            raise ValidationError("You cannot deactivate your own account.")
        old = user.is_active
        user.is_active = active
        user.save(update_fields=["is_active"])
        audit.record(AuditLog.Action.UPDATE, user, old={"is_active": old}, new={"is_active": active},
                     message="Account activated" if active else "Account deactivated")
        return Response(UserSerializer(user).data)

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        return self._set_active(request, True)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        return self._set_active(request, False)


class RoleViewSet(AuditedModelViewSet):
    queryset = Role.objects.prefetch_related("permissions").all()
    serializer_class = RoleSerializer
    required_permissions = {"list": ["roles.manage", "users.manage"], "retrieve": ["roles.manage", "users.manage"],
                            "*": "roles.manage"}
    search_fields = ["code", "name"]
    pagination_class = None

    def perform_update(self, serializer):
        old_perms = sorted(serializer.instance.permissions.values_list("code", flat=True))
        with transaction.atomic():
            super().perform_update(serializer)
            new_perms = sorted(serializer.instance.permissions.values_list("code", flat=True))
            if old_perms != new_perms:
                audit.record(AuditLog.Action.PERMISSION_CHANGE, serializer.instance,
                             old={"permissions": old_perms}, new={"permissions": new_perms})

    def perform_destroy(self, instance):
        if instance.is_system:
            raise ValidationError("System roles cannot be deleted.")
        if instance.users.exists():
            raise ValidationError("Role is assigned to users.")
        super().perform_destroy(instance)


class PermissionViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [HasPermissionCode]
    required_permissions = {"*": ["roles.manage", "users.manage"]}
    pagination_class = None
