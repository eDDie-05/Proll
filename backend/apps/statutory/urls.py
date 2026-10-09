from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("statutory-rules", views.StatutoryRuleViewSet)

urlpatterns = router.urls
