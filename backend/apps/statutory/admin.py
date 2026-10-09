from django.contrib import admin

from .models import StatutoryRule, TaxBracket


class TaxBracketInline(admin.TabularInline):
    model = TaxBracket
    extra = 0


@admin.register(StatutoryRule)
class StatutoryRuleAdmin(admin.ModelAdmin):
    list_display = ("code", "version", "effective_from", "effective_to", "verification_status", "is_active")
    list_filter = ("category", "verification_status", "is_active")
    inlines = [TaxBracketInline]
