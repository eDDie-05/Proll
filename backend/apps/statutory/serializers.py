from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from apps.core.serializers import ModelCleanMixin

from .models import StatutoryRule, TaxBracket


class TaxBracketSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxBracket
        fields = ["id", "lower_bound", "upper_bound", "rate"]


class StatutoryRuleSerializer(ModelCleanMixin, serializers.ModelSerializer):
    brackets = TaxBracketSerializer(many=True, required=False)
    is_used = serializers.BooleanField(read_only=True)
    verified_by_name = serializers.CharField(source="verified_by.username", read_only=True, default=None)

    class Meta:
        model = StatutoryRule
        exclude = ["created_by"]
        read_only_fields = [
            "version", "verification_status", "verified_by", "verified_at", "created_at", "updated_at",
        ]

    def validate(self, attrs):
        if self.instance is not None and self.instance.is_used:
            locked = [k for k, v in attrs.items()
                      if k not in StatutoryRule.MUTABLE_AFTER_USE and k != "brackets" and getattr(self.instance, k) != v]
            if locked or "brackets" in attrs:
                raise serializers.ValidationError(
                    "This rule version has been used in payroll and its calculation fields are locked "
                    f"({', '.join(locked) or 'brackets'}). Create a new version instead."
                )
        attrs = super().validate(attrs)
        method = attrs.get("method", getattr(self.instance, "method", None))
        if method == StatutoryRule.Method.PROGRESSIVE and self.instance is None and not attrs.get("brackets"):
            raise serializers.ValidationError({"brackets": "Progressive rules need brackets."})
        return attrs

    def _save_brackets(self, rule, brackets):
        if brackets is None:
            return
        rule.brackets.all().delete()
        TaxBracket.objects.bulk_create([TaxBracket(rule=rule, **b) for b in brackets])
        try:
            rule.validate_brackets()
        except DjangoValidationError as e:
            raise serializers.ValidationError({"brackets": e.messages})

    @transaction.atomic
    def create(self, validated_data):
        brackets = validated_data.pop("brackets", None)
        last = StatutoryRule.objects.filter(code=validated_data["code"]).order_by("-version").first()
        validated_data["version"] = (last.version + 1) if last else 1
        rule = StatutoryRule.objects.create(**validated_data)
        self._save_brackets(rule, brackets)
        return rule

    @transaction.atomic
    def update(self, instance, validated_data):
        brackets = validated_data.pop("brackets", None)
        material = {k for k in validated_data if k not in StatutoryRule.MUTABLE_AFTER_USE}
        for k, v in validated_data.items():
            setattr(instance, k, v)
        if material or brackets is not None:
            # Any change to the calculation invalidates a prior verification.
            instance.verification_status = StatutoryRule.Verification.UNVERIFIED
            instance.verified_by = None
            instance.verified_at = None
        instance.save()
        self._save_brackets(instance, brackets)
        return instance


class NewVersionSerializer(serializers.Serializer):
    effective_from = serializers.DateField()
    source_reference = serializers.CharField(required=False, allow_blank=True)
    source_url = serializers.URLField(required=False, allow_blank=True)


class VerifySerializer(serializers.Serializer):
    verification_notes = serializers.CharField()
    source_url = serializers.URLField(required=False, allow_blank=True)
    source_reference = serializers.CharField(required=False, allow_blank=True)
    source_retrieved_on = serializers.DateField(required=False)
