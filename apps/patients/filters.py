import django_filters
from apps.patients.models import Patient

class PatientFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="filter_search")
    
    class Meta:
        model = Patient
        fields = ["gender", "blood_group"]

    def filter_search(self, queryset, name, value):
        return queryset.filter(
            django_filters.db.models.Q(first_name__icontains=value) |
            django_filters.db.models.Q(last_name__icontains=value) |
            django_filters.db.models.Q(phone__icontains=value) |
            django_filters.db.models.Q(email__icontains=value) |
            django_filters.db.models.Q(patient_code__icontains=value)
        )
