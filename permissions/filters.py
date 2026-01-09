from rest_framework import filters
from django.db.models import Q
from permissions.models.audit import userprofile, company

# def permitedCompanies(user):
#     compids = []
#     comps = []
#     # return queryset.filter(owner=request.user)

#     ups = userprofile.objects.filter(user = user)
#     for up in ups:
#         if up.company:
#             if up.company.id not in compids:
#                 compids.append(up.company.id)
#         if up.organization:
#             comps = company.objects.filter(organization = up.organization.id)
#             ids = comps.values('id')
#             for id in ids:
#                 if id['id'] not in compids:
#                     compids.append(id['id'])
#     return compids, comps.values()

def permitedCompanies(user):
    compids = []
    companies = []
    # return queryset.filter(owner=request.user)

    ups = userprofile.objects.filter(user = user)
    for up in ups:
        if up.company:
            if up.company not in companies:
                companies.append(up.company)
        if up.organization:
            comps = company.objects.filter(organization = up.organization.id)
            # ids = comps.values('id')
            for comp in comps:
                if comp not in companies:
                    companies.append(comp)
    return [comp.id for comp in companies], [{'id':comp.id, 'name': comp.name, 'organization': comp.organization} for comp in companies]


class IsAllowedFilterBackend(filters.BaseFilterBackend):
    """
    Filter that only allows users to see their own objects.
    """
    def filter_queryset(self, request, queryset, view):
        
        # return queryset.filter(created_by=request.user)
        # compids = permitedCompanies(request.user)[0]
        # if compids == []:
        #     # qFilter = Q(created_by = request.user) | Q(company=None)
        #     qFilter = Q(company=None)
        # else:            
        #     qFilter = Q(company__in = compids) | Q(company=None)            
        qFilter = Q(user = request.user)
        for filt in list(request.query_params.items()):
            qFilter &= Q(**{filt[0] : filt[1]})	        
        # print(qFilter)
        return queryset.filter(qFilter)        