from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("leave-types", views.LeaveTypeViewSet)
router.register("leave-records", views.LeaveRecordViewSet)

urlpatterns = router.urls
