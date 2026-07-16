"""Add 150 more email templates across tone-based categories."""
from django.core.management.base import BaseCommand
from shop.models import EmailTemplate


def w(body):
    return f'<div style="font-family: Helvetica, Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 40px 20px; color: #333;">{body}</div>'

def l(t):
    return f'<p style="font-size: 11px; letter-spacing: 0.15em; text-transform: uppercase; color: #999; margin: 0 0 20px;">{t}</p>'

def h(t, s=22):
    return f'<p style="font-size: {s}px; font-weight: 700; color: #000; margin: 0 0 14px; letter-spacing: -0.02em;">{t}</p>'

def b(t):
    return f'<p style="font-size: 15px; line-height: 1.8; color: #555; margin: 0 0 12px;">{t}</p>'

def a(t, u="https://www.blueprnt.store/shop/"):
    return f'<a href="{u}" style="display: inline-block; padding: 13px 28px; background: #000; color: #fff; text-decoration: none; font-size: 11px; letter-spacing: 0.15em; text-transform: uppercase; margin-top: 12px;">{t}</a>'


class Command(BaseCommand):
    help = "Add 150 more email templates"

    def handle(self, *args, **options):
        templates = []

        # === MORE MINIMAL (30) ===
        M = "minimal"
        templates += [
            (M, "promotion", "Period", "Foundation.", w(f'{h(".", 36)}{a("Shop")}')),
            (M, "promotion", "Dash", "—", w(f'<div style="text-align:center;padding:20px 0;"><div style="width:40px;height:2px;background:#000;margin:0 auto 20px;"></div>{a("Shop New")}</div>')),
            (M, "promotion", "Numbers", "001", w(f'<div style="text-align:center;">{h("001", 32)}{a("Shop Foundation")}</div>')),
            (M, "promotion", "Square", "New.", w(f'<div style="text-align:center;"><div style="width:8px;height:8px;background:#000;margin:0 auto 20px;"></div>{a("Shop")}</div>')),
            (M, "promotion", "Underscore", "_", w(f'<div style="text-align:center;padding:30px 0;">{a("New Drop")}</div>')),
            (M, "promotion", "Just Price", "{product_price}", w(f'<div style="text-align:center;">{h("{product_price}", 28)}<p style="font-size:13px;color:#999;margin:0 0 16px;">{"{product_name}"}</p>{a("View", "{product_url}")}</div>')),
            (M, "promotion", "Slash", "/", w(f'{h("{product_name}", 18)}{a("Shop", "{product_url}")}')),
            (M, "promotion", "Quiet Drop", ".", w(f'{b("Something new in the shop.")}{a("See It")}')),
            (M, "promotion", "Plus", "+", w(f'<div style="text-align:center;"><p style="font-size:28px;color:#000;margin:0 0 16px;">+</p>{a("New Arrival")}</div>')),
            (M, "promotion", "Open Box", "▪", w(f'{a("Shop Blueprint")}')),
            (M, "promotion", "Colon", "Blueprint:", w(f'{b("{product_name}")}{a("View", "{product_url}")}')),
            (M, "newsletter", "Silence", " ", w(f'<div style="text-align:center;padding:40px 0;">{a("Shop")}</div>')),
            (M, "promotion", "X Marks", "×", w(f'{h("{product_name} × {product_name_2}", 18)}{a("Shop the Pair")}')),
            (M, "promotion", "Equals", "=", w(f'<div style="text-align:center;">{h("Quality = Intention", 18)}{a("Shop")}</div>')),
            (M, "promotion", "Parentheses", "(new)", w(f'{b("{product_name} just dropped.")}{a("View", "{product_url}")}')),
            (M, "promotion", "Brackets", "[Foundation]", w(f'{a("Shop Foundation")}')),
            (M, "promotion", "Asterisk", "*", w(f'{b("* Limited restock.")}{a("Shop")}')),
            (M, "promotion", "Pipe", "|", w(f'<div style="text-align:center;"><div style="width:1px;height:30px;background:#000;margin:0 auto 16px;"></div>{a("Shop")}</div>')),
            (M, "promotion", "Half", "50", w(f'<div style="text-align:center;">{h("50", 36)}<p style="font-size:12px;color:#999;letter-spacing:0.15em;text-transform:uppercase;margin:0 0 16px;">Percent off</p>{a("Shop")}</div>')),
            (M, "promotion", "Zero", "0", w(f'<div style="text-align:center;">{h("$0", 28)}<p style="font-size:12px;color:#999;margin:0 0 16px;">Shipping</p>{a("Shop")}</div>')),
            (M, "promotion", "No Subject Needed", "", w(f'{a("Shop Blueprint")}')),
            (M, "promotion", "Product Code", "BP-{product_name}", w(f'{l("Product")}{h("{product_name}", 18)}{a("View", "{product_url}")}')),
            (M, "promotion", "Tee", "Tee.", w(f'{h("Tee.", 24)}{a("Shop")}')),
            (M, "promotion", "Pants", "Pants.", w(f'{h("Pants.", 24)}{a("Shop")}')),
            (M, "promotion", "Set", "The set.", w(f'{h("The set.", 24)}{a("Shop Bundles")}')),
            (M, "promotion", "Black", "Black.", w(f'{b("Now in black.")}{a("Shop")}')),
            (M, "promotion", "White", "White.", w(f'{b("Now in white.")}{a("Shop")}')),
            (M, "promotion", "Both", "Both.", w(f'{b("Get both.")}{a("Shop")}')),
            (M, "promotion", "Fit Check", "Fit.", w(f'{b("Relaxed. Premium. Yours.")}{a("Shop")}')),
            (M, "promotion", "Cotton", "100% cotton.", w(f'{b("Nothing else.")}{a("Shop")}')),
        ]

        # === MORE DIRECT (30) ===
        D = "direct"
        templates += [
            (D, "promotion", "New + Price", "{product_name} — {product_price}", w(f'{l("New")}{h("{product_name}")}{b("Premium cotton. Relaxed fit. Designed in Chicago.")}<p style="font-size:18px;font-weight:700;color:#000;margin:0 0 20px;">{"{product_price}"}</p>{a("Shop", "{product_url}")}')),
            (D, "promotion", "Two Products", "New arrivals.", w(f'{l("Just Dropped")}{b("<strong>{product_name}</strong> and <strong>{product_name_2}</strong> are now available.")}{a("Shop New")}')),
            (D, "promotion", "Full Collection", "The full collection.", w(f'{h("Every piece.")}{b("See the entire Foundation lineup.")}{a("View All")}')),
            (D, "promotion", "Size Guide", "Find your fit.", w(f'{h("Size guide.")}{b("Not sure? Our pieces run relaxed. When in doubt, go true to size.")}{a("Shop")}')),
            (D, "promotion", "Returns Policy", "Easy returns.", w(f'{b("Returns for store credit within 30 days. No hassle.")}{a("Shop Confidently")}')),
            (D, "promotion", "Shipping Info", "Shipping details.", w(f'{h("Shipping")}{b("Standard: 5-7 business days. Free on orders over $75.")}{a("Shop")}')),
            (D, "promotion", "New Category", "New category: {category_name}", w(f'{l("New")}{h("{category_name}")}{b("New pieces just added to the shop.")}{a("View")}')),
            (D, "promotion", "Compare", "{product_name} vs {product_name_2}", w(f'{h("Which one?")}{b("Two pieces. Same quality. Different vibe.")}{a("Compare")}')),
            (D, "promotion", "Material Spotlight", "The fabric.", w(f'{h("Premium cotton.")}{b("Heavyweight. Pre-shrunk. Gets better with every wash.")}{a("Shop")}')),
            (D, "promotion", "Color Drop", "New color.", w(f'{l("Color Drop")}{h("{product_name}")}{b("Now available in {color_name}.")}{a("View", "{product_url}")}')),
            (D, "promotion", "Outfit Builder", "Build your outfit.", w(f'{h("Top + Bottom")}{b("Grab the tee and pants. Foundation essentials.")}{a("Shop the Set")}')),
            (D, "promotion", "First Order", "First order? Here.", w(f'{b("New here? Use <strong>WELCOME10</strong> for 10% off.")}{a("Shop")}')),
            (D, "promotion", "Price Comparison", "Worth it.", w(f'{h("{product_name}")}{b("Premium cotton at {product_price}. Compare that to anything else in your closet.")}{a("Shop", "{product_url}")}')),
            (D, "promotion", "Refer a Friend", "Share Blueprint.", w(f'{b("Know someone who would wear this? Forward this email. 10% off for both of you with code <strong>FRIEND10</strong>.")}{a("Shop")}')),
            (D, "promotion", "Student Discount", "Student? {discount_value}% off.", w(f'{b("Use code <strong>{discount_code}</strong> at checkout. Valid student ID required.")}{a("Shop")}')),
            (D, "promotion", "Stacked Savings", "Stack and save.", w(f'{h("Bundle deal.")}{b("Buy the set, save {discount_value}%. Automatically applied.")}{a("Shop Bundles")}')),
            (D, "promotion", "Clearance", "Final sale.", w(f'{h("Final sale.")}{b("Select Foundation pieces marked down. All sales final.")}{a("Shop Sale")}')),
            (D, "promotion", "Midweek Drop", "Wednesday drop.", w(f'{l("Midweek")}{b("New pieces. No fanfare. Just good product.")}{a("Shop")}')),
            (D, "promotion", "Pre-Order", "Pre-order now.", w(f'{h("Pre-order")}{b("{product_name} ships in 2-3 weeks. Secure yours now.")}{a("Pre-Order", "{product_url}")}')),
            (D, "promotion", "Gift Card", "Give Blueprint.", w(f'{h("Gift cards.")}{b("Not sure what to get? Let them choose.")}{a("Buy a Gift Card")}')),
            (D, "promotion", "Care Guide", "Make it last.", w(f'{h("Care guide.")}{b("Cold wash. Hang dry. Your pieces will last years.")}{a("Shop")}')),
            (D, "promotion", "Measurements", "Know before you buy.", w(f'{b("Every product page has detailed measurements. No guessing.")}{a("Shop")}')),
            (D, "promotion", "Mix and Match", "Mix and match.", w(f'{b("Every piece in Foundation works with every other piece. That is the point.")}{a("Shop")}')),
            (D, "promotion", "Layer Up", "Layer season.", w(f'{h("Layer up.")}{b("Foundation pieces are built for layering.")}{a("Shop")}')),
            (D, "promotion", "Weekend Wear", "Weekend ready.", w(f'{b("Pieces that work Monday through Sunday.")}{a("Shop")}')),
            (D, "promotion", "Travel Edit", "Travel light.", w(f'{h("Travel edit.")}{b("Pack less. Wear more. Foundation pieces work everywhere.")}{a("Shop")}')),
            (D, "promotion", "Gym to Street", "Gym to street.", w(f'{b("Relaxed fit. Premium fabric. Works both ways.")}{a("Shop")}')),
            (D, "promotion", "Night Out", "Night out.", w(f'{b("Clean enough for dinner. Comfortable enough for everything after.")}{a("Shop")}')),
            (D, "promotion", "Daily Driver", "Your daily driver.", w(f'{h("{product_name}")}{b("The one you reach for every day.")}{a("Shop", "{product_url}")}')),
            (D, "promotion", "No Brainer", "No brainer.", w(f'{b("{product_name} at {product_price}. Premium cotton. Free returns.")}{a("Get It", "{product_url}")}')),
        ]

        # === MORE STORYTELLING (30) ===
        S = "storytelling"
        templates += [
            (S, "newsletter", "The First Sketch", "The first sketch.", w(f'{h("The first sketch.")}{b("Every collection starts the same way — Kevin with a pencil, drawing something he would want to wear. Foundation started as three sketches on a napkin.")}{a("Shop Foundation")}')),
            (S, "newsletter", "Japanese Gardens", "Japanese gardens.", w(f'{b("Balance. Intention. Nothing wasted. The same principles behind a Japanese garden are behind every piece in Foundation.")}{a("Shop")}')),
            (S, "newsletter", "The Court", "The court.", w(f'{h("The court.")}{b("Kevin grew up playing basketball in Chicago. The discipline of practice, the focus under pressure — that energy is in the brand.")}{a("Shop")}')),
            (S, "newsletter", "Family Table", "The family table.", w(f'{b("Korean dinners with family. The colors, the textures, the care put into everything. That is where the attention to detail comes from.")}{a("Our Story", "https://www.blueprnt.store/shop/about/")}')),
            (S, "newsletter", "The Workshop", "The workshop.", w(f'{h("The workshop.")}{b("We do not have a big office. We have a table, two laptops, and a vision. Blueprint was built in late nights and early mornings.")}{a("Shop")}')),
            (S, "newsletter", "Why Premium", "Why premium.", w(f'{b("We could use cheaper fabric. We choose not to. You feel the difference the first time you put it on.")}{a("Shop")}')),
            (S, "newsletter", "The Palette", "The palette.", w(f'{h("The palette.")}{b("Black. White. Earth tones. We chose colors that do not compete with each other — or with you.")}{a("Shop")}')),
            (S, "newsletter", "No Logo", "No logo.", w(f'{b("You will not find our logo on the front of any piece. The graphics are the identity. The brand is in the quality.")}{a("Shop")}')),
            (S, "newsletter", "Designed in Chicago", "Designed in Chicago.", w(f'{l("Chicago")}{b("Every piece is designed here. The city is in the work — the grit, the ambition, the no-shortcuts mentality.")}{a("Shop")}')),
            (S, "newsletter", "The Drop Model", "Why we drop.", w(f'{b("We do not do seasons. We drop collections when they are ready. No rushing. No filler pieces to meet a deadline.")}{a("Shop")}')),
            (S, "newsletter", "Small Batch", "Small batch.", w(f'{b("We produce in small quantities. When it sells out, it is gone until the next run. This is intentional.")}{a("Shop")}')),
            (S, "newsletter", "The Fit", "The fit.", w(f'{h("Relaxed.")}{b("Not oversized. Not slim. Relaxed. The kind of fit where you forget you are wearing it.")}{a("Shop")}')),
            (S, "newsletter", "Behind Discovery", "Behind Discovery.", w(f'{l("Coming Soon")}{b("Discovery is our second collection. It builds on Foundation but goes somewhere new. We cannot wait to show you.")}')),
            (S, "newsletter", "The Graphic Process", "How graphics happen.", w(f'{b("Kevin starts with the feeling, not the image. The tiger came from thinking about courage. The swordsman came from thinking about discipline.")}{a("Shop")}')),
            (S, "newsletter", "Independent", "Independent.", w(f'{h("Independent.")}{b("No investors. No backing. Just two people who believe in what they are making. Your support is our funding.")}{a("Shop")}')),
            (S, "newsletter", "Quality Promise", "Our promise.", w(f'{b("If it does not meet our standard, we do not ship it. Every piece is checked before it goes out.")}{a("Shop")}')),
            (S, "newsletter", "The Name Blueprint", "Why Blueprint.", w(f'{b("A blueprint is what comes before the building. The intention before the action. We named the brand after the plan, not the finished product.")}{a("Shop")}')),
            (S, "newsletter", "Everyday Wear", "Everyday.", w(f'{b("We do not make statement pieces. We make pieces that become part of your life without asking for attention.")}{a("Shop")}')),
            (S, "newsletter", "Growth", "Growing.", w(f'{b("We started with two products. Now we have a full collection, a lookbook, and customers in every state. Thank you.")}{a("Shop")}')),
            (S, "newsletter", "What Comes Next", "What comes next.", w(f'{b("Foundation was the starting point. Discovery is the next step. And after that — we keep building. That is the blueprint.")}')),
            (S, "newsletter", "Made to Move", "Made to move.", w(f'{b("These pieces were designed for people who do things. Not for hangers in a closet.")}{a("Shop")}')),
            (S, "newsletter", "Heritage", "Heritage.", w(f'{l("Korean + Chicago")}{b("Two cultures. One brand. The tension between tradition and ambition is what makes Blueprint.")}{a("Our Story", "https://www.blueprnt.store/shop/about/")}')),
            (S, "newsletter", "Simplicity", "Simple.", w(f'{b("We removed everything that did not need to be there. What is left is the piece.")}{a("Shop")}')),
            (S, "newsletter", "The Standard", "The standard.", w(f'{h("The standard.")}{b("Premium cotton. Clean construction. A fit that works on every body type. This is our baseline, not our ceiling.")}{a("Shop")}')),
            (S, "newsletter", "Day One", "Day one.", w(f'{b("We remember the first order. The first customer who believed in something that did not exist yet. We are still building for that person.")}{a("Shop")}')),
            (S, "newsletter", "Patience", "Patience.", w(f'{b("Discovery took longer than we planned. Because we would rather be late and right than early and wrong.")}')),
            (S, "newsletter", "Wear Test", "Wear tested.", w(f'{b("Every piece gets worn by us before it ships. If we would not wear it daily, we do not sell it.")}{a("Shop")}')),
            (S, "newsletter", "No Waste", "No waste.", w(f'{b("Small runs. No overproduction. When we sell out, we sell out. Better than landfill.")}{a("Shop")}')),
            (S, "newsletter", "Roots", "Roots.", w(f'{b("Chicago concrete. Korean silk. Two worlds that shaped one brand.")}{a("Shop")}')),
            (S, "newsletter", "The Vision", "The vision.", w(f'{b("Build something real. Make it well. Let the work speak. That has been the vision since day one and it has not changed.")}{a("Shop")}')),
        ]

        # === MORE URGENT (30) ===
        U = "urgent"
        templates += [
            (U, "promotion", "Gone by Morning", "Gone by morning.", w(f'{h("Gone by morning.")}{b("{product_name} — last few units.")}{a("Get It", "{product_url}")}')),
            (U, "promotion", "Two Left", "Two left.", w(f'{b("{product_name} — two left in your size.")}{a("Shop", "{product_url}")}')),
            (U, "promotion", "No Restock", "Not restocking.", w(f'{h("Not restocking.")}{b("When these sell out, that is it until next collection.")}{a("Shop")}')),
            (U, "promotion", "Price Goes Up", "Price goes up tomorrow.", w(f'{b("{product_name} goes back to full price at midnight.")}{a("Shop Now", "{product_url}")}')),
            (U, "promotion", "Members Only", "Members only.", w(f'{l("Exclusive")}{b("{discount_value}% off for 24 hours. Subscribers only.")}{a("Shop")}')),
            (U, "promotion", "Secret Sale", "Shhh.", w(f'{b("Private sale. {discount_value}% off. Not on the site. Just for you.")}{a("Shop")}')),
            (U, "promotion", "Dropping Now", "Dropping now.", w(f'{h("Now.", 28)}{a("Shop")}')),
            (U, "promotion", "Limited Run", "Limited run.", w(f'{b("{product_name} — limited to 50 units.")}{a("Get Yours", "{product_url}")}')),
            (U, "promotion", "Back for 24hrs", "Back for 24 hours.", w(f'{h("{product_name}")}{b("Restocked for 24 hours only.")}{a("Shop", "{product_url}")}')),
            (U, "promotion", "Tonight Only", "Tonight only.", w(f'{b("{discount_value}% off. Code: <strong>{discount_code}</strong>. Expires midnight.")}{a("Shop")}')),
            (U, "promotion", "Wake Up", "Wake up.", w(f'{b("New drop just went live. Early bird gets it.")}{a("Shop Now")}')),
            (U, "promotion", "Reminder", "Reminder.", w(f'{b("Sale ends today. {discount_value}% off everything.")}{a("Shop")}')),
            (U, "promotion", "Closing Soon", "Closing soon.", w(f'{h("Doors closing.")}{b("This sale ends in hours.")}{a("Last Chance")}')),
            (U, "promotion", "One Size Left", "One size left.", w(f'{b("{product_name} — only {size} remaining.")}{a("Get It", "{product_url}")}')),
            (U, "promotion", "Cart Reminder", "You left something.", w(f'{b("Still thinking about {product_name}? It is still available.")}{a("Complete Your Order", "{product_url}")}')),
            (U, "promotion", "Double Points", "Double points.", w(f'{b("2x rewards on every purchase today.")}{a("Shop")}')),
            (U, "promotion", "Exclusive Drop", "Exclusive.", w(f'{l("Subscribers Only")}{b("This piece drops publicly in 48 hours. You see it now.")}{a("Shop")}')),
            (U, "promotion", "End of Season", "End of season.", w(f'{h("Final markdowns.")}{b("Foundation pieces at the lowest prices.")}{a("Shop Sale")}')),
            (U, "promotion", "Buy One", "Buy one, get one.", w(f'{b("BOGO on select Foundation pieces. Today only.")}{a("Shop")}')),
            (U, "promotion", "Lucky You", "Lucky you.", w(f'{b("You opened this. Here is {discount_value}% off. Code: <strong>{discount_code}</strong>")}{a("Shop")}')),
            (U, "promotion", "Act Fast", "Act fast.", w(f'{b("Bestseller back in stock. Will not last.")}{a("Shop")}')),
            (U, "promotion", "VIP Access", "VIP.", w(f'{l("Early Access")}{b("New collection drops in 24 hours. You get first pick.")}{a("Shop Early")}')),
            (U, "promotion", "Surprise Inside", "Open me.", w(f'{b("Code <strong>{discount_code}</strong> for {discount_value}% off. Valid 12 hours.")}{a("Shop")}')),
            (U, "promotion", "Breaking", "Breaking.", w(f'{h("New drop.", 24)}{b("Live now. Limited quantities.")}{a("Shop")}')),
            (U, "promotion", "Do Not Wait", "Do not wait.", w(f'{b("Last time we restocked {product_name}, it sold out in 3 days.")}{a("Shop", "{product_url}")}')),
            (U, "promotion", "Ends Midnight", "Ends midnight.", w(f'<div style="text-align:center;">{h("{discount_value}% OFF", 28)}{b("Code: {discount_code}")}{a("Shop")}</div>')),
            (U, "promotion", "Almost Over", "Almost over.", w(f'{b("The sale closes soon. This is the last reminder.")}{a("Shop Now")}')),
            (U, "promotion", "Waitlist Open", "Waitlist open.", w(f'{h("{product_name}")}{b("Sold out. Join the waitlist for the next restock.")}{a("Join Waitlist", "{product_url}")}')),
            (U, "promotion", "First Come", "First come.", w(f'{b("New drop. Limited stock. No holds. No reserves.")}{a("Shop Now")}')),
            (U, "promotion", "Right Now", "Right now.", w(f'{h("Right now.", 24)}{a("Shop Blueprint")}')),
        ]

        # === MORE CASUAL (30) ===
        C = "casual"
        templates += [
            (C, "newsletter", "Yo", "Yo.", w(f'{b("New stuff. Go look.")}{a("Shop")}')),
            (C, "newsletter", "Just Checking In", "Just checking in.", w(f'{b("Anything you need? We are here.")}')),
            (C, "newsletter", "Monday Mood", "Monday.", w(f'{b("Start the week right. New pieces in the shop.")}{a("Shop")}')),
            (C, "newsletter", "Friday Feeling", "Friday.", w(f'{b("Weekend plans? We got the outfit.")}{a("Shop")}')),
            (C, "promotion", "Treat Yourself", "Treat yourself.", w(f'{b("You have earned it. {discount_value}% off with code <strong>{discount_code}</strong>.")}{a("Shop")}')),
            (C, "promotion", "Your Call", "Your call.", w(f'{b("{product_name} or {product_name_2}? Both good choices.")}{a("Shop")}')),
            (C, "newsletter", "Honest Update", "Honest update.", w(f'{b("Working on new stuff. Not ready yet. But it is going to be worth the wait.")}')),
            (C, "newsletter", "Thanks Again", "Thanks again.", w(f'{b("Every order helps us keep going. Genuinely appreciate you.")}')),
            (C, "promotion", "Good News", "Good news.", w(f'{b("{product_name} is back. Grab it before it goes again.")}{a("Shop", "{product_url}")}')),
            (C, "newsletter", "Chill", "Chill.", w(f'{b("No promo. No sale. Just saying hi.")}')),
            (C, "promotion", "Why Not", "Why not.", w(f'{b("{discount_value}% off. Why not.")}{a("Shop")}')),
            (C, "newsletter", "Working on It", "Working on it.", w(f'{b("New collection is in progress. Sketches, samples, late nights. Stay tuned.")}')),
            (C, "promotion", "Last One", "Last one.", w(f'{b("Literally the last {product_name} in {size}.")}{a("Get It", "{product_url}")}')),
            (C, "newsletter", "Happy Holidays", "Happy holidays.", w(f'{b("From our two-person team to you. Thank you for a great year.")}')),
            (C, "newsletter", "New Year", "New year.", w(f'{b("Same blueprint. More to come.")}{a("Shop")}')),
            (C, "promotion", "Spring Clean", "Spring clean.", w(f'{b("Refresh your wardrobe. {discount_value}% off everything.")}{a("Shop")}')),
            (C, "newsletter", "We Hear You", "We hear you.", w(f'{b("You asked for more colors. More colors are coming.")}')),
            (C, "promotion", "Easy Gift", "Easy gift.", w(f'{b("Do not overthink it. Blueprint pieces make great gifts. Free returns.")}{a("Shop")}')),
            (C, "promotion", "Just Because", "Just because.", w(f'{b("No reason. {discount_value}% off. Code: <strong>{discount_code}</strong>.")}{a("Shop")}')),
            (C, "newsletter", "Behind the Scenes", "Behind the scenes.", w(f'{b("Sampling new fabrics this week. The weight on this one is insane. More soon.")}')),
            (C, "newsletter", "Grateful", "Grateful.", w(f'{b("Small brand, big gratitude. Thank you for supporting independent.")}')),
            (C, "promotion", "Match Made", "Match made.", w(f'{b("The tee and the pants. Trust us.")}{a("Shop the Set")}')),
            (C, "newsletter", "Feedback", "Talk to us.", w(f'{b("Reply to this email. Tell us what you want to see next. We actually read these.")}')),
            (C, "newsletter", "Milestone", "Milestone.", w(f'{b("Just hit {milestone}. Wild. Thank you.")}')),
            (C, "promotion", "No Excuses", "No excuses.", w(f'{b("Free shipping. Free returns. {discount_value}% off. What else do you need?")}{a("Shop")}')),
            (C, "newsletter", "The Process", "The process.", w(f'{b("Design. Sample. Wear test. Revise. Repeat. That is how we make everything.")}')),
            (C, "newsletter", "Sneak Peek", "Sneak peek.", w(f'{b("Cannot show you everything yet. But here is a hint: Discovery is going to be different.")}')),
            (C, "promotion", "Weekend Sale", "Weekend.", w(f'{b("{discount_value}% off through Sunday. Code: <strong>{discount_code}</strong>.")}{a("Shop")}')),
            (C, "promotion", "Try It", "Try it.", w(f'{b("{product_name}. 30-day returns. Zero risk.")}{a("Shop", "{product_url}")}')),
            (C, "newsletter", "One More Thing", "One more thing.", w(f'{b("We are launching something new next month. Not a product. Something different. Stay tuned.")}')),
        ]

        count = 0
        for t in templates:
            folder, ttype, name, subject, html = t
            # Skip if name already exists
            if EmailTemplate.objects.filter(name=name).exists():
                continue
            EmailTemplate.objects.create(
                name=name,
                template_type=ttype,
                folder=folder,
                auto_trigger="manual",
                subject=subject,
                html_body=html,
                is_active=True,
            )
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Added {count} new templates (total: {EmailTemplate.objects.count()})"))
