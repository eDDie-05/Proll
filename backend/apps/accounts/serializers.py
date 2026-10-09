from django.contrib.auth import password_validation
from rest_framework import serializers

from .models import Permission, Role, User


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["id", "code", "description"]


class RoleSerializer(serializers.ModelSerializer):
    permissions = serializers.SlugRelatedField(
        many=True, slug_field="code", queryset=Permission.objects.all(), required=False
    )
    user_count = serializers.IntegerField(source="users.count", read_only=True)

    class Meta:
        model = Role
        fields = ["id", "code", "name", "description", "permissions", "is_system", "user_count"]
        read_only_fields = ["is_system"]

    def validate_code(self, value):
        value = value.upper().strip()
        if self.instance and self.instance.is_system and value != self.instance.code:
            raise serializers.ValidationError("System role codes cannot be changed.")
        return value


class UserSerializer(serializers.ModelSerializer):
    role = serializers.SlugRelatedField(slug_field="code", queryset=Role.objects.all(), allow_null=True)
    role_name = serializers.CharField(source="role.name", read_only=True, default=None)
    password = serializers.CharField(write_only=True, required=False, style={"input_type": "password"})
    employee_id = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "first_name", "last_name", "phone", "role", "role_name",
            "is_active", "last_login", "date_joined", "password", "must_change_password", "employee_id",
        ]
        read_only_fields = ["last_login", "date_joined"]

    def get_employee_id(self, obj) -> int | None:
        emp = getattr(obj, "employee", None)
        return emp.pk if emp else None

    def validate(self, attrs):
        password = attrs.get("password")
        if self.instance is None and not password:
            raise serializers.ValidationError({"password": "Password is required for new users."})
        if password:
            candidate = User(**{k: v for k, v in attrs.items() if k not in ("password", "role")})
            password_validation.validate_password(password, candidate)
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for k, v in validated_data.items():
            setattr(instance, k, v)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class MeSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source="role.code", default=None)
    role_name = serializers.CharField(source="role.name", default=None)
    permissions = serializers.SerializerMethodField()
    employee_id = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "email", "first_name", "last_name", "role", "role_name",
            "permissions", "employee_id", "must_change_password",
        ]

    def get_permissions(self, obj) -> list[str]:
        return sorted(obj.permission_codes())

    def get_employee_id(self, obj) -> int | None:
        emp = getattr(obj, "employee", None)
        return emp.pk if emp else None


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(style={"input_type": "password"})


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField()
    new_password = serializers.CharField()

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError({"current_password": "Current password is incorrect."})
        password_validation.validate_password(attrs["new_password"], user)
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField()
