from django.urls import path
from rest_framework.routers import DefaultRouter

from documents.views import DocumentViewSet, SearchAPIView


router = DefaultRouter()
router.register("documents", DocumentViewSet, basename="document")

urlpatterns = [
    path("search/", SearchAPIView.as_view(), name="document-search"),
    *router.urls,
]
