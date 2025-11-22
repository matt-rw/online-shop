import random
import uuid
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from shop.models.analytics import PageView, VisitorSession


class Command(BaseCommand):
    help = "Populate visitor analytics with sample data"

    def add_arguments(self, parser):
        parser.add_argument(
            "--sessions",
            type=int,
            default=100,
            help="Number of visitor sessions to create",
        )
        parser.add_argument(
            "--days", type=int, default=30, help="Number of days of history to create"
        )

    def handle(self, *args, **options):
        num_sessions = options["sessions"]
        num_days = options["days"]

        self.stdout.write(
            self.style.SUCCESS(
                f"Generating {num_sessions} visitor sessions over {num_days} days..."
            )
        )

        # Sample data
        pages = [
            "/",
            "/shop/",
            "/shop/products/",
            "/shop/products/classic-tee/",
            "/shop/products/hoodie/",
            "/shop/products/joggers/",
            "/shop/products/cap/",
            "/shop/cart/",
            "/shop/checkout/",
            "/about/",
            "/contact/",
        ]

        countries = [
            {"code": "US", "name": "United States", "cities": ["New York", "Los Angeles", "Chicago", "Houston", "Miami"], "regions": ["NY", "CA", "IL", "TX", "FL"]},
            {"code": "GB", "name": "United Kingdom", "cities": ["London", "Manchester", "Birmingham", "Liverpool", "Leeds"], "regions": ["England", "England", "England", "England", "England"]},
            {"code": "CA", "name": "Canada", "cities": ["Toronto", "Vancouver", "Montreal", "Calgary", "Ottawa"], "regions": ["ON", "BC", "QC", "AB", "ON"]},
            {"code": "AU", "name": "Australia", "cities": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"], "regions": ["NSW", "VIC", "QLD", "WA", "SA"]},
            {"code": "DE", "name": "Germany", "cities": ["Berlin", "Munich", "Hamburg", "Frankfurt", "Cologne"], "regions": ["Berlin", "Bavaria", "Hamburg", "Hesse", "NRW"]},
            {"code": "FR", "name": "France", "cities": ["Paris", "Lyon", "Marseille", "Toulouse", "Nice"], "regions": ["Île-de-France", "Auvergne-Rhône-Alpes", "Provence-Alpes-Côte d'Azur", "Occitanie", "Provence-Alpes-Côte d'Azur"]},
            {"code": "JP", "name": "Japan", "cities": ["Tokyo", "Osaka", "Kyoto", "Yokohama", "Nagoya"], "regions": ["Tokyo", "Osaka", "Kyoto", "Kanagawa", "Aichi"]},
            {"code": "BR", "name": "Brazil", "cities": ["São Paulo", "Rio de Janeiro", "Brasília", "Salvador", "Fortaleza"], "regions": ["SP", "RJ", "DF", "BA", "CE"]},
            {"code": "IN", "name": "India", "cities": ["Mumbai", "Delhi", "Bangalore", "Hyderabad", "Chennai"], "regions": ["Maharashtra", "Delhi", "Karnataka", "Telangana", "Tamil Nadu"]},
            {"code": "MX", "name": "Mexico", "cities": ["Mexico City", "Guadalajara", "Monterrey", "Puebla", "Tijuana"], "regions": ["CDMX", "Jalisco", "Nuevo León", "Puebla", "Baja California"]},
        ]

        devices = [
            {"type": "desktop", "weight": 40},
            {"type": "mobile", "weight": 50},
            {"type": "tablet", "weight": 8},
            {"type": "bot", "weight": 2},
        ]

        browsers = ["Chrome", "Safari", "Firefox", "Edge", "Opera"]
        operating_systems = ["Windows", "macOS", "Linux", "iOS", "Android"]

        referrers = [
            {"domain": "", "url": None},  # Direct traffic
            {"domain": "google.com", "url": "https://google.com/search?q=blueprint+apparel"},
            {"domain": "facebook.com", "url": "https://facebook.com"},
            {"domain": "instagram.com", "url": "https://instagram.com"},
            {"domain": "twitter.com", "url": "https://twitter.com"},
            {"domain": "reddit.com", "url": "https://reddit.com/r/fashion"},
            {"domain": "tiktok.com", "url": "https://tiktok.com"},
            {"domain": "pinterest.com", "url": "https://pinterest.com"},
        ]

        # Clear existing data
        self.stdout.write("Clearing existing visitor data...")
        PageView.objects.all().delete()
        VisitorSession.objects.all().delete()

        # Generate visitor sessions
        sessions_created = 0
        page_views_created = 0

        for i in range(num_sessions):
            # Random timestamp within the date range
            days_ago = random.randint(0, num_days - 1)
            hours_ago = random.randint(0, 23)
            minutes_ago = random.randint(0, 59)
            first_seen = timezone.now() - timedelta(
                days=days_ago, hours=hours_ago, minutes=minutes_ago
            )

            # Random country and city
            country = random.choice(countries)
            city_index = random.randint(0, len(country["cities"]) - 1)
            city = country["cities"][city_index]
            region = country["regions"][city_index]

            # Random device type (weighted)
            device = random.choices(
                [d["type"] for d in devices], weights=[d["weight"] for d in devices]
            )[0]

            # Random browser and OS
            browser = random.choice(browsers)
            os = random.choice(operating_systems)

            # Random referrer
            referrer_data = random.choice(referrers)

            # Generate session ID
            session_id = str(uuid.uuid4())

            # Random IP address (fake)
            ip_address = f"{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}.{random.randint(1, 255)}"

            # Random landing page
            landing_page = random.choice(pages)

            # Number of page views in this session (weighted towards fewer views)
            num_page_views = random.choices(
                [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                weights=[30, 25, 15, 10, 8, 5, 3, 2, 1, 1],
            )[0]

            # Calculate last seen (some time after first seen, within the session)
            session_duration_minutes = random.randint(1, 30)
            last_seen = first_seen + timedelta(minutes=session_duration_minutes)

            # Create visitor session
            visitor_session = VisitorSession.objects.create(
                session_id=session_id,
                first_seen=first_seen,
                last_seen=last_seen,
                landing_page=landing_page,
                referrer=referrer_data["url"],
                page_views=num_page_views,
                ip_address=ip_address,
                user_agent=f"Mozilla/5.0 ({os}) {browser}",
                device_type=device,
                country=country["code"],
                country_name=country["name"],
                region=region,
                city=city,
                latitude=random.uniform(-90, 90),
                longitude=random.uniform(-180, 180),
            )
            sessions_created += 1

            # Create page views for this session
            current_time = first_seen
            visited_pages = [landing_page]

            for j in range(num_page_views):
                # Choose next page (weighted towards continuing from current page)
                if j == 0:
                    page = landing_page
                else:
                    # 70% chance to visit a new page, 30% chance to revisit
                    if random.random() < 0.7:
                        available_pages = [p for p in pages if p not in visited_pages]
                        if available_pages:
                            page = random.choice(available_pages)
                            visited_pages.append(page)
                        else:
                            page = random.choice(pages)
                    else:
                        page = random.choice(visited_pages)

                # Add some time between page views
                if j > 0:
                    current_time += timedelta(seconds=random.randint(10, 180))

                # Random response time (weighted towards faster responses)
                response_time = random.choices(
                    [50, 100, 150, 200, 300, 500, 1000, 2000],
                    weights=[20, 25, 20, 15, 10, 5, 3, 2],
                )[0]

                PageView.objects.create(
                    path=page,
                    method="GET",
                    ip_address=ip_address,
                    user_agent=f"Mozilla/5.0 ({os}) {browser}",
                    referrer=referrer_data["url"] if j == 0 else None,
                    referrer_domain=referrer_data["domain"] if j == 0 else "",
                    device_type=device,
                    browser=browser,
                    os=os,
                    response_time_ms=response_time,
                    session_id=session_id,
                    viewed_at=current_time,
                    country=country["code"],
                    country_name=country["name"],
                    region=region,
                    city=city,
                    latitude=visitor_session.latitude,
                    longitude=visitor_session.longitude,
                )
                page_views_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ Successfully created {sessions_created} visitor sessions"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(f"✓ Successfully created {page_views_created} page views")
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"\nYou can now view the visitor analytics at /admin/visitors/"
            )
        )
