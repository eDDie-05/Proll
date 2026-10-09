from rest_framework import serializers

from .models import AuditLog, CompanySettings


class CompanySettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanySettings
        exclude = ["id"]
        read_only_fields = ["updated_at"]


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = "__all__"


class ModelCleanMixin:
    """Run the model's clean() during serializer validation so business rules live in one place."""

    def validate(self, attrs):
        attrs = super().validate(attrs)
        from django.core.exceptions import ValidationError as DjangoValidationError

        model = self.Meta.model
        concrete = {f.name for f in model._meta.concrete_fields}
        instance = self.instance or model()
        original = {k: getattr(instance, k) for k in attrs if k in concrete} if self.instance else {}
        for k, v in attrs.items():
            if k in concrete:
                setattr(instance, k, v)
        try:
            instance.clean()
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message_dict if hasattr(e, "message_dict") else e.messages)
        finally:
            for k, v in original.items():
                setattr(instance, k, v)
        return attrs
