from datetime import timedelta

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core import audit
from apps.core.models import AuditLog
from apps.core.permissions import crud_permissions
from apps.core.utils import to_decimal
from apps.core.views_mixins import AuditedModelViewSet

from . import calculator
from .models import StatutoryRule, TaxBracket
from .serializers import NewVersionSerializer, StatutoryRuleSerializer, VerifySerializer


class StatutoryRuleViewSet(AuditedModelViewSet):
    queryset = StatutoryRule.objects.prefetch_related("brackets").select_related("verified_by")
    serializer_class = StatutoryRuleSerializer
    required_permissions = crud_permissions(
        "statutory.view", "statutory.manage", verify="statutory.verify", new_version="statutory.manage",
        preview=["statutory.view", "statutory.manage"], in_force=["statutory.view", "statutory.manage"],
    )
    filterset_fields = ["code", "category", "party", "is_active", "verification_status"]
    search_fields = ["code", "name", "source_reference"]
    ordering_fields = ["code", "effective_from", "version", "calculation_order"]
    allow_destroy = False
    pagination_class = None

    def perform_update(self, serializer):
        old_brackets = [str(b) for b in serializer.instance.brackets.all()]
        super().perform_update(serializer)
        new_brackets = [str(b) for b in serializer.instance.brackets.all()]
        if old_brackets != new_brackets:
            audit.record(AuditLog.Action.UPDATE, serializer.instance, old={"brackets": old_brackets},
                         new={"brackets": new_brackets}, message="Tax brackets changed")

    @extend_schema(request=VerifySerializer)
    @action(detail=True, methods=["post"])
    def verify(self, request, pk=None):
        rule = self.get_object()
        ser = VerifySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            rule.validate_brackets()
        except DjangoValidationError as e:
            raise ValidationError({"brackets": e.messages})
        old = audit.snapshot(rule)
        for k, v in ser.validated_data.items():
            setattr(rule, k, v)
        rule.verification_status = StatutoryRule.Verification.VERIFIED
        rule.verified_by = request.user
        rule.verified_at = timezone.now()
        rule.save()
        before, after = audit.diff(old, audit.snapshot(rule))
        audit.record(AuditLog.Action.UPDATE, rule, old=before, new=after, message="Statutory rule verified")
        return Response(StatutoryRuleSerializer(rule).data)

    @extend_schema(request=NewVersionSerializer)
    @action(detail=True, methods=["post"], url_path="new-version")
    def new_version(self, request, pk=None):
        """Copy this rule into a new UNVERIFIED version starting at `effective_from`; end-date the current one."""
        rule = self.get_object()
        ser = NewVersionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        start = ser.validated_data["effective_from"]
        if start <= rule.effective_from:
            raise ValidationError({"effective_from": "New version must start after the current version."})
        with transaction.atomic():
            old_to = rule.effective_to
            rule.effective_to = start - timedelta(days=1)
            rule.save(update_fields=["effective_to", "updated_at"])
            audit.record(AuditLog.Action.UPDATE, rule, old={"effective_to": str(old_to) if old_to else None},
                         new={"effective_to": str(rule.effective_to)}, message="End-dated by new version")
            brackets = list(rule.brackets.all())
            last_version = StatutoryRule.objects.filter(code=rule.code).order_by("-version").first().version
            rule.pk = None
            rule.id = None
            rule._state.adding = True
            rule.version = last_version + 1
            rule.effective_from = start
            rule.effective_to = old_to if old_to and old_to >= start else None
            rule.verification_status = StatutoryRule.Verification.UNVERIFIED
            rule.verified_by = rule.verified_at = None
            rule.verification_notes = ""
            rule.created_by = request.user
            for k in ("source_reference", "source_url"):
                if k in ser.validated_data:
                    setattr(rule, k, ser.validated_data[k])
            rule.save()
            TaxBracket.objects.bulk_create(
                [TaxBracket(rule=rule, lower_bound=b.lower_bound, upper_bound=b.upper_bound, rate=b.rate) for b in brackets]
            )
            audit.record(AuditLog.Action.CREATE, rule, new=audit.snapshot(rule), message="New statutory rule version")
        return Response(StatutoryRuleSerializer(rule).data, status=201)

    @action(detail=True, methods=["post"])
    def preview(self, request, pk=None):
        """Calculate this rule against a sample base amount (no side effects)."""
        rule = self.get_object()
        try:
            base = to_decimal(request.data.get("base_amount"))
        except Exception:
            raise ValidationError({"base_amount": "A numeric base amount is required."})
        amount, detail = calculator.calculate(rule, base)
        return Response({"amount": str(amount), "detail": detail})

    @action(detail=False, methods=["get"], url_path="in-force")
    def in_force(self, request):
        on = serializers.DateField().to_internal_value(request.query_params.get("date") or timezone.localdate().isoformat())
        return Response(StatutoryRuleSerializer(StatutoryRule.in_force(on), many=True).data)
