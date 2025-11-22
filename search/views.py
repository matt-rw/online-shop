from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.template.response import TemplateResponse
from django.db.models import Q

from shop.models import Product


def search(request):
    search_query = request.GET.get("query", None)
    page = request.GET.get("page", 1)

    # Search across Product models
    if search_query:
        search_results = Product.objects.filter(
            Q(name__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(category_obj__name__icontains=search_query)
        )
    else:
        search_results = Product.objects.none()

    # Pagination
    paginator = Paginator(search_results, 10)
    try:
        search_results = paginator.page(page)
    except PageNotAnInteger:
        search_results = paginator.page(1)
    except EmptyPage:
        search_results = paginator.page(paginator.num_pages)

    return TemplateResponse(
        request,
        "search/search.html",
        {
            "search_query": search_query,
            "search_results": search_results,
        },
    )
