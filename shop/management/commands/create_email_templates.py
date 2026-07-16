"""Generate 100 email templates across tone-based categories."""
from django.core.management.base import BaseCommand
from shop.models import EmailTemplate


def wrap(body):
    """Wrap body content in the standard email container."""
    return f'<div style="font-family: Helvetica, Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 40px 20px; color: #333;">{body}</div>'


def label(text):
    return f'<p style="font-size: 11px; letter-spacing: 0.15em; text-transform: uppercase; color: #999; margin: 0 0 20px;">{text}</p>'


def heading(text, size=22):
    return f'<p style="font-size: {size}px; font-weight: 700; color: #000; margin: 0 0 14px; letter-spacing: -0.02em;">{text}</p>'


def body(text):
    return f'<p style="font-size: 15px; line-height: 1.8; color: #555; margin: 0 0 12px;">{text}</p>'


def btn(text, url="https://www.blueprnt.store/shop/"):
    return f'<a href="{url}" style="display: inline-block; padding: 13px 28px; background: #000; color: #fff; text-decoration: none; font-size: 11px; letter-spacing: 0.15em; text-transform: uppercase; margin-top: 12px;">{text}</a>'


def sig():
    return '<p style="font-size: 11px; color: #bbb; margin: 28px 0 0;">Blueprint Apparel</p>'


class Command(BaseCommand):
    help = "Create 100 email templates"

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Delete existing templates and recreate')

    def handle(self, *args, **options):
        existing = EmailTemplate.objects.count()
        if existing >= 50 and not options.get('force'):
            self.stdout.write(f"Already have {existing} templates. Use --force to recreate.")
            return

        EmailTemplate.objects.all().delete()

        templates = []

        # === MINIMAL (20) — barely anything, all impact ===
        M = "minimal"
        templates += [
            (M, "promotion", "Just the Button", "New from Blueprint.", wrap(f'<div style="text-align:center;padding:20px 0;">{btn("Shop New")}{sig()}</div>')),
            (M, "promotion", "One Word", "Foundation.", wrap(f'{heading("Foundation.", 28)}{btn("Shop")}')),
            (M, "promotion", "Price Drop", "{product_name} — now {product_price}", wrap(f'{heading("{product_name}")}<p style="font-size:20px;font-weight:700;color:#000;margin:0 0 20px;">{"{product_price}"}</p>{btn("View", "{product_url}")}')),
            (M, "newsletter", "The Line", "The line.", wrap(f'<div style="text-align:center;padding:10px 0;"><div style="width:30px;height:2px;background:#fde047;margin:0 auto 20px;"></div><p style="font-size:16px;font-weight:600;color:#000;line-height:1.6;margin:0 0 20px;">The foundation is the first thing carved in any blueprint.</p>{btn("Shop")}</div>')),
            (M, "promotion", "New Color", "New color: {product_name}", wrap(f'{body("Now available in a new colorway.")}{btn("View", "{product_url}")}')),
            (M, "promotion", "Restock", "{product_name} restocked.", wrap(f'{body("Back in your size.")}{btn("Get It", "{product_url}")}')),
            (M, "newsletter", "Dot", ".", wrap(f'<div style="text-align:center;padding:20px 0;"><div style="width:6px;height:6px;background:#000;border-radius:50%;margin:0 auto 20px;"></div>{btn("Shop Blueprint")}</div>')),
            (M, "promotion", "Two Words", "New drop.", wrap(f'{heading("New drop.", 24)}{btn("Shop")}')),
            (M, "promotion", "Product — Minimal", "{product_name}", wrap(f'{heading("{product_name}", 20)}{btn("View", "{product_url}")}')),
            (M, "newsletter", "Blueprint", "Blueprint.", wrap(f'<div style="text-align:center;">{heading("Blueprint.", 28)}{sig()}</div>')),
            (M, "promotion", "Just Landed", "Just landed.", wrap(f'{label("New")}{btn("Shop New")}')),
            (M, "promotion", "Available Now", "{product_name} available now.", wrap(f'{heading("{product_name}", 20)}<p style="font-size:14px;color:#999;margin:0 0 16px;">{"{product_price}"}</p>{btn("Shop", "{product_url}")}')),
            (M, "newsletter", "Blank + Button", "From Blueprint.", wrap(f'<div style="padding:30px 0;text-align:center;">{btn("Shop")}</div>')),
            (M, "promotion", "Code Only", "{discount_code}", wrap(f'<div style="text-align:center;"><p style="font-size:28px;font-weight:800;color:#000;letter-spacing:0.1em;margin:0 0 8px;">{"{discount_code}"}</p><p style="font-size:14px;color:#888;margin:0 0 20px;">{"{discount_value}"}% off</p>{btn("Use Code")}</div>')),
            (M, "promotion", "Arrow", "→", wrap(f'<div style="text-align:center;padding:20px 0;"><p style="font-size:36px;margin:0 0 16px;">→</p>{btn("Shop New")}</div>')),
            (M, "promotion", "Silent Drop", "...", wrap(f'{heading("...", 32)}{btn("See What Dropped")}')),
            (M, "newsletter", "Est 2025", "Est. 2025", wrap(f'<div style="text-align:center;"><p style="font-size:11px;letter-spacing:0.3em;text-transform:uppercase;color:#bbb;margin:0;">Est. 2025</p></div>')),
            (M, "promotion", "Sold Out Soon", "Almost gone.", wrap(f'{body("Limited sizes remaining.")}{btn("Shop")}')),
            (M, "promotion", "Pairs Well", "{product_name} + {product_name_2}", wrap(f'{heading("Better together.", 20)}{btn("Shop the Pair")}')),
            (M, "promotion", "Size Run", "Your size is back.", wrap(f'{body("{product_name} — restocked in all sizes.")}{btn("Shop", "{product_url}")}')),
        ]

        # === DIRECT (20) — clear, informational, no fluff ===
        D = "direct"
        templates += [
            (D, "promotion", "New Arrival — Direct", "Just dropped: {product_name}", wrap(f'{label("New Arrival")}{heading("{product_name}")}{body("{product_description}")}{btn("View", "{product_url}")}')),
            (D, "promotion", "Product Spotlight", "{product_name} — {product_price}", wrap(f'{heading("{product_name}")}{body("{product_description}")}<p style="font-size:16px;font-weight:600;color:#000;margin:0 0 20px;">{"{product_price}"}</p>{btn("Shop Now", "{product_url}")}')),
            (D, "promotion", "Back in Stock — Direct", "{product_name} is back in stock.", wrap(f'{heading("{product_name}")}{body("Limited quantities. Premium cotton, relaxed fit.")}{btn("Get It", "{product_url}")}')),
            (D, "promotion", "Sale Announcement", "{discount_value}% off everything.", wrap(f'<p style="font-size:32px;font-weight:800;color:#000;margin:0 0 6px;">{"{discount_value}"}% OFF</p>{label("All products")}{body("No code needed. Applied at checkout.")}{btn("Shop the Sale")}')),
            (D, "promotion", "Code Discount", "{discount_value}% off with code {discount_code}", wrap(f'{body("Use code <strong>{discount_code}</strong> at checkout for {discount_value}% off.")}{btn("Shop")}')),
            (D, "promotion", "Free Shipping — Direct", "Free shipping this weekend.", wrap(f'{heading("Free shipping.")}{body("Every order. No minimum. Ends Sunday.")}{btn("Shop")}')),
            (D, "promotion", "Bundle Deal", "Bundle and save.", wrap(f'{heading("Bundle & Save")}{body("Grab the set and save on Foundation pieces.")}{btn("View Bundles")}')),
            (D, "promotion", "Lookbook Live", "The lookbook is live.", wrap(f'{heading("Lookbook")}{body("See Foundation the way we designed it.")}{btn("View Lookbook", "https://www.blueprnt.store/shop/lookbook/")}')),
            (D, "newsletter", "Collection Overview", "Foundation — the full lineup.", wrap(f'{label("Collection 001")}{heading("Foundation")}{body("Every piece in our debut collection. Designed in Chicago, inspired by Korean heritage.")}{btn("Shop All")}')),
            (D, "promotion", "Gift Guide", "For the person who has taste.", wrap(f'{heading("Gift Guide")}{body("Premium pieces. Returns within 30 days. Free shipping over $75.")}{btn("Shop Gifts")}')),
            (D, "promotion", "Last Chance", "Last chance.", wrap(f'{heading("Last chance.")}{body("These sizes will not be restocked until the next drop.")}{btn("Shop Now")}')),
            (D, "promotion", "Bestseller", "Our most popular piece.", wrap(f'{heading("{product_name}")}{body("The one everyone keeps coming back for.")}{btn("Shop", "{product_url}")}')),
            (D, "promotion", "New Season", "New season. Same blueprint.", wrap(f'{label("New")}{heading("New season.")}{body("Fresh pieces just added.")}{btn("Shop New Arrivals")}')),
            (D, "promotion", "Weekend Drop", "Weekend drop.", wrap(f'{heading("Weekend drop.")}{body("New pieces live now.")}{btn("Shop")}')),
            (D, "promotion", "Flash — 24hr", "24 hours only.", wrap(f'{heading("24 hours.", 28)}{body("{discount_value}% off. No code. Ends midnight.")}{btn("Shop the Sale")}')),
            (D, "promotion", "Summer Edit", "Summer edit.", wrap(f'{label("Seasonal")}{heading("Summer Edit")}{body("Lightweight pieces for the season.")}{btn("Shop")}')),
            (D, "promotion", "Essentials Restock", "Essentials restocked.", wrap(f'{heading("Restocked.")}{body("The basics you have been waiting for are back in all sizes.")}{btn("Shop Essentials")}')),
            (D, "newsletter", "What We Do", "What we do.", wrap(f'{body("Premium fabrics. Considered construction. A palette that works with everything you own.")}{body("Designed in Chicago. Shipped everywhere.")}{btn("Shop")}')),
            (D, "promotion", "Holiday Shipping", "Order by {date} for holiday delivery.", wrap(f'{heading("Holiday Cutoff")}{body("Order by {date} to guarantee delivery before the holidays.")}{btn("Shop Now")}')),
            (D, "promotion", "Early Access", "Early access.", wrap(f'{label("Subscribers Only")}{heading("Early access.")}{body("You are seeing this before anyone else. New pieces drop publicly tomorrow.")}{btn("Shop Now")}')),
        ]

        # === STORYTELLING (20) — brand narrative, longer form ===
        S = "storytelling"
        templates += [
            (S, "newsletter", "Chicago Roots", "Built in Chicago.", wrap(f'{label("Our Story")}{heading("Built in Chicago.")}{body("Blueprint started with Kevin Lee — raised on Chicago basketball, rooted in Korean heritage. Every graphic carries that weight.")}{btn("Learn More", "https://www.blueprnt.store/shop/about/")}')),
            (S, "newsletter", "The Tiger", "The tiger.", wrap(f'{heading("The tiger.")}{body("A symbol of courage in Korean culture. When Kevin designed the first graphic, there was no question what it would be.")}{body("This is not decoration. It is identity.")}{btn("Shop", "https://www.blueprnt.store/shop/")}')),
            (S, "newsletter", "The Swordsman", "Courage, on your back.", wrap(f'{heading("The swordsman.")}{body("A woman with a sword on her back. Discipline and intention drawn from the same roots Blueprint was built on.")}{btn("Shop")}')),
            (S, "newsletter", "Two People", "Two people, one vision.", wrap(f'{body("Kevin and Matt. Longtime friends who built Blueprint from scratch. No investors. No shortcuts.")}{body("Thanks for being part of it.")}{sig()}')),
            (S, "newsletter", "Why Foundation", "Why we called it Foundation.", wrap(f'{heading("Foundation.")}{body("Every building has bones. Every painting started as a sketch. The foundation is the first thing carved in any blueprint.")}{body("That is why we named our first collection after it.")}{btn("Shop Foundation")}')),
            (S, "newsletter", "Korean Heritage", "Seoul to Chicago.", wrap(f'{label("Heritage")}{body("The graphics in Foundation are drawn from Korean art and culture — symbols of strength, protection, and quiet discipline.")}{body("Blended with Chicago grit. That is the blueprint.")}{btn("Shop")}')),
            (S, "newsletter", "Design Process", "How we design.", wrap(f'{heading("Intentional.")}{body("Every piece starts with a question: does this need to exist? If the answer is not clear, we do not make it.")}{body("Premium cotton. Relaxed fit. Nothing extra.")}{btn("Shop")}')),
            (S, "newsletter", "The Name", "Why Blueprint?", wrap(f'{heading("Why Blueprint?")}{body("A blueprint is the plan before the building. The sketch before the painting. The intention before the action.")}{body("We named the brand after the starting point — because everything begins there.")}{btn("Shop")}')),
            (S, "newsletter", "First Collection", "Our first collection.", wrap(f'{label("January 2026")}{heading("Foundation.")}{body("Our debut. Released January 2026. Named for the first line drawn. Built on principles of balance, intention, and purpose.")}{btn("Shop Foundation")}')),
            (S, "newsletter", "Next Chapter", "The next chapter.", wrap(f'{heading("Discovery.")}{body("Foundation was the starting point. Discovery is what comes next when you follow the blueprint.")}{body("Coming late summer.")}{sig()}')),
            (S, "newsletter", "Calm Over Chaos", "Calm over chaos.", wrap(f'{body("Clothing should reflect the calm and control you strive for in your own life.")}{body("Not louder. Not busier. Just right.")}{btn("Shop")}')),
            (S, "newsletter", "No Trends", "This is not about trends.", wrap(f'{heading("Forget the trends.", 24)}{body("We do not chase what is popular. We build what lasts. Every piece in Foundation was designed to be worn for years, not seasons.")}{btn("Shop")}')),
            (S, "newsletter", "The Fabric", "It starts with the fabric.", wrap(f'{heading("Premium cotton.")}{body("We source the best materials we can find. Because a good design on bad fabric is still bad.")}{btn("Shop")}')),
            (S, "newsletter", "Chicago Basketball", "Basketball courts to blueprints.", wrap(f'{body("Kevin grew up on Chicago basketball — the discipline, the focus, the drive. That energy is in every piece.")}{body("Blueprint is what happens when you channel that into something you can wear.")}{btn("Shop")}')),
            (S, "newsletter", "Year One", "Year one.", wrap(f'{label("2025-2026")}{heading("Year one.")}{body("We launched with one collection, two people, and an idea. Thank you for being here from the start.")}{sig()}')),
            (S, "newsletter", "What We Believe", "What we believe.", wrap(f'{body("Clothing should work as hard as you do.")}{body("No trend-chasing. No hype cycles. Just clean, versatile pieces built to last.")}{btn("Shop")}')),
            (S, "newsletter", "The Details", "It is in the details.", wrap(f'{heading("Details.")}{body("The weight of the cotton. The drop of the shoulder. The way it moves. These are the things we obsess over.")}{btn("Shop")}')),
            (S, "newsletter", "Every Stitch", "Every stitch.", wrap(f'{body("We do not mass produce. We do not cut corners. Every piece is built the way we would want it built if we were buying it ourselves.")}{body("Because we are.")}{btn("Shop")}')),
            (S, "newsletter", "Follow Your Path", "Follow your path.", wrap(f'<div style="text-align:center;">{heading("Forget the trends.", 22)}<p style="font-size:18px;color:#888;margin:0 0 4px;">Remember the blueprint.</p><p style="font-size:14px;color:#bbb;letter-spacing:0.05em;margin:0 0 24px;">Follow your path.</p>{btn("Shop")}</div>')),
            (S, "newsletter", "Thank You", "Thank you.", wrap(f'{heading("Thank you.")}{body("We are a two-person team. Every order matters. Thanks for supporting independent.")}{sig()}')),
        ]

        # === URGENT (20) — time-sensitive, scarcity ===
        U = "urgent"
        templates += [
            (U, "promotion", "Ends Tonight", "Ends tonight.", wrap(f'{heading("Ends tonight.", 28)}{body("{discount_value}% off. No code needed.")}{btn("Shop Before Midnight")}')),
            (U, "promotion", "Hours Left", "{hours} hours left.", wrap(f'{heading("{hours} hours left.")}{body("Sale ends soon.")}{btn("Shop Now")}')),
            (U, "promotion", "Final Restock", "Final restock.", wrap(f'{heading("Final restock.")}{body("{product_name} will not be made again after this run.")}{btn("Get It", "{product_url}")}')),
            (U, "promotion", "Selling Fast", "Selling fast.", wrap(f'{heading("{product_name}")}{body("Moving faster than expected. Grab your size.")}{btn("Shop", "{product_url}")}')),
            (U, "promotion", "Almost Sold Out", "Almost sold out.", wrap(f'{body("{product_name} — a few sizes left.")}{btn("Shop", "{product_url}")}')),
            (U, "promotion", "Last Units", "Last units.", wrap(f'{heading("Last units.")}{body("Once these are gone, they are gone.")}{btn("Shop")}')),
            (U, "promotion", "Today Only — Flat", "Today only: {discount_value}% off", wrap(f'<p style="font-size:36px;font-weight:800;color:#000;margin:0 0 6px;">{"{discount_value}"}%</p>{label("Today Only")}{btn("Shop")}')),
            (U, "promotion", "Flash Drop", "Flash drop.", wrap(f'{heading("Surprise.")}{body("New piece just dropped. No announcement. You are seeing it first.")}{btn("View")}')),
            (U, "promotion", "Midnight", "Midnight.", wrap(f'{body("This offer ends at midnight. {discount_value}% off everything.")}{btn("Shop Now")}')),
            (U, "promotion", "Going Going", "Going, going...", wrap(f'{heading("Going, going...")}{body("Foundation sizes are disappearing.")}{btn("Shop What is Left")}')),
            (U, "promotion", "One Day Sale", "One day sale.", wrap(f'{heading("{discount_value}% off.", 28)}{label("One day only")}{btn("Shop the Sale")}')),
            (U, "promotion", "Last Call — Short", "Last call.", wrap(f'{heading("Last call.")}{btn("Shop")}')),
            (U, "promotion", "Don't Miss It", "You will regret missing this.", wrap(f'{body("{discount_value}% off. Ends tonight. No exceptions.")}{btn("Shop Now")}')),
            (U, "promotion", "Weekend Only", "This weekend only.", wrap(f'{heading("This weekend.")}{body("{discount_value}% off the entire collection. Starts now.")}{btn("Shop")}')),
            (U, "promotion", "Subscribers Only — Flash", "For you only.", wrap(f'{label("Subscriber Exclusive")}{heading("{discount_value}% off.")}{body("This is not public. Ends in 24 hours.")}{btn("Shop Now")}')),
            (U, "promotion", "Countdown", "3... 2... 1...", wrap(f'{heading("3... 2... 1...", 28)}{body("Sale is live.")}{btn("Shop")}')),
            (U, "promotion", "Now or Never", "Now or never.", wrap(f'{body("{product_name} — last chance before it is gone.")}{btn("Get It", "{product_url}")}')),
            (U, "promotion", "Early Bird", "Early bird.", wrap(f'{label("First 24 Hours")}{heading("{discount_value}% off new arrivals.")}{body("For subscribers only. Before the public drop.")}{btn("Shop Early")}')),
            (U, "promotion", "Stock Alert", "Stock alert: {product_name}", wrap(f'{heading("{product_name}")}{body("Down to the last few. This is your alert.")}{btn("Shop", "{product_url}")}')),
            (U, "promotion", "Final Hours", "Final hours.", wrap(f'{heading("Final hours.")}{body("Sale closes at midnight. Do not sleep on it.")}{btn("Shop the Sale")}')),
        ]

        # === CASUAL (15) — conversational, human ===
        C = "casual"
        templates += [
            (C, "newsletter", "Hey", "Hey.", wrap(f'{body("Just wanted to say thanks for being here. More coming soon.")}{sig()}')),
            (C, "newsletter", "Been a Minute", "Been a minute.", wrap(f'{body("New pieces, same foundation. Come take a look when you are ready.")}{btn("See What is New")}')),
            (C, "newsletter", "Quick Update", "Quick update.", wrap(f'{body("New stuff in the shop. Nothing flashy, just good pieces.")}{btn("Take a Look")}')),
            (C, "promotion", "Still Thinking", "Still thinking about it?", wrap(f'{body("No pressure. Use <strong>{discount_code}</strong> for {discount_value}% off if it helps.")}{btn("Shop")}')),
            (C, "newsletter", "Happy Weekend", "Happy weekend.", wrap(f'{body("No sales pitch. Just hope you have a good one.")}{sig()}')),
            (C, "promotion", "Thought You Should Know", "Thought you should know.", wrap(f'{body("{product_name} is back in stock. Just a heads up.")}{btn("View", "{product_url}")}')),
            (C, "newsletter", "No Big Deal", "No big deal.", wrap(f'{body("Just dropped some new stuff. Or do not look. Either way.")}{btn("Shop")}')),
            (C, "newsletter", "Sunday Note", "Sunday note.", wrap(f'{body("Hope you had a good week. New things coming this month.")}{sig()}')),
            (C, "promotion", "FYI", "FYI.", wrap(f'{body("{discount_value}% off this week. Code: <strong>{discount_code}</strong>")}{btn("Shop")}')),
            (C, "newsletter", "From Kevin", "From Kevin.", wrap(f'{body("I just wanted to say — building this brand has been the hardest and best thing I have done. Thanks for rocking with us.")}<p style="font-size:13px;color:#bbb;margin:20px 0 0;">— Kevin</p>')),
            (C, "newsletter", "What is Next", "What is next.", wrap(f'{body("Working on Discovery — our second collection. Cannot say too much yet but it is going to be good.")}{sig()}')),
            (C, "promotion", "Sizes Going", "Heads up — sizes going.", wrap(f'{body("A few Foundation pieces are getting low. Just letting you know.")}{btn("Shop")}')),
            (C, "newsletter", "Real Talk", "Real talk.", wrap(f'{body("We are a small brand. Two people. Every order means a lot. If you have been thinking about grabbing something — we appreciate you.")}{btn("Shop")}')),
            (C, "promotion", "Payday Treat", "Payday treat.", wrap(f'{body("Treat yourself. {discount_value}% off with code <strong>{discount_code}</strong>.")}{btn("Shop")}')),
            (C, "newsletter", "Year in Review", "A look back.", wrap(f'{body("One collection. Thousands of pieces shipped. Zero regrets. Thank you for year one.")}{sig()}')),
        ]

        # === TRANSACTIONAL (5) — auto-trigger ===
        T = "transactional"
        templates += [
            (T, "welcome", "Welcome — Auto", "Welcome to Blueprint.", wrap(f'{label("Blueprint Apparel")}{body("You are in. New drops, early access, nothing else.")}{body("Use <strong>WELCOME10</strong> for 10% off your first order.")}{btn("Shop")}'), "on_subscribe"),
            (T, "order_confirmation", "Order Confirmed", "Order confirmed #{order_number}", wrap(f'{label("Order Confirmed")}{heading("#{order_number}", 18)}{body("Total: {total}")}{body("We will send tracking when it ships.")}'), "on_order"),
            (T, "shipping_notification", "Shipped", "Your order has shipped.", wrap(f'{label("Shipped")}{body("Order #{order_number} is on the way.")}{body("Tracking: {tracking_number}")}{btn("Track Order", "{tracking_url}")}'), "on_shipping"),
            (T, "custom", "Admin Order Alert", "New order: {order_number} — {total}", wrap(f'{heading("New Order", 18)}{body("#{order_number}")}{body("Total: {total}")}{body("{customer_email}")}'), "on_order_admin"),
            (T, "custom", "Blank Canvas", "", wrap('<p style="font-size:15px;line-height:1.8;color:#555;"></p>'), None),
        ]

        count = 0
        for t in templates:
            if len(t) == 5:
                folder, ttype, name, subject, html = t
                trigger = "manual"
            else:
                folder, ttype, name, subject, html, trigger = t[0], t[1], t[2], t[3], t[4], t[5]
                if trigger is None:
                    trigger = "manual"

            EmailTemplate.objects.create(
                name=name,
                template_type=ttype,
                folder=folder,
                auto_trigger=trigger,
                subject=subject,
                html_body=html,
                is_active=True,
            )
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Created {count} email templates"))
