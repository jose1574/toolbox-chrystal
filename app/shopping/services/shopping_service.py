from sqlalchemy import or_

from app.models import Provider


def get_shopping_overview():
    return {
        'purchase_orders': 0,
        'pending_approvals': 0,
        'received_orders': 0,
        'recent_activities': [],
    }


def get_provider_by_code(code_provider):
    if not code_provider:
        return None

    provider = Provider.query.filter_by(code=code_provider).first()
    return provider 

def search_providers(query='', page=1, per_page=10):
    query = (query or '').strip()
    page = max(page or 1, 1)
    per_page = max(min(per_page or 10, 50), 1)

    provider_query = Provider.query.with_entities(
        Provider.code,
        Provider.contact,
        Provider.description,
    )

    if query:
        search_value = f'%{query}%'
        provider_query = provider_query.filter(
            or_(
                Provider.code.ilike(search_value),
                Provider.description.ilike(search_value),
            )
        )

    provider_query = provider_query.order_by(Provider.description.asc(), Provider.code.asc())
    total = provider_query.count()
    total_pages = max((total + per_page - 1) // per_page, 1)
    page = min(page, total_pages)
    providers = provider_query.limit(per_page).offset((page - 1) * per_page).all()

    return providers, total, total_pages, page