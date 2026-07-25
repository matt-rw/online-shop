from django.core.management.base import BaseCommand

from shop.models import EmailTemplate


WRAP_START = '<div style="font-family: Helvetica, Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 40px 20px; color: #333;">'
WRAP_END = "</div>"

LABEL = '<p style="font-size: 11px; letter-spacing: 0.15em; text-transform: uppercase; color: #999; margin: 0 0 20px;">{}</p>'
HEADING = '<p style="font-size: 22px; font-weight: 700; color: #000; margin: 0 0 14px; letter-spacing: -0.02em;">{}</p>'
BODY = '<p style="font-size: 15px; line-height: 1.8; color: #555; margin: 0 0 12px;">{}</p>'
CTA = '<a href="https://www.blueprnt.store/shop/" style="display: inline-block; padding: 13px 28px; background: #000; color: #fff; text-decoration: none; font-size: 11px; letter-spacing: 0.15em; text-transform: uppercase; margin-top: 12px;">{}</a>'
SPACER = '<div style="height: 16px;"></div>'


def wrap(*parts):
    return WRAP_START + "".join(parts) + WRAP_END


TEMPLATES = [
    # ── STORYTELLING / LONGER CONTENT ──
    {
        "name": "How Foundation Got Made",
        "subject": "How Foundation got made.",
        "folder": "storytelling",
        "template_type": "newsletter",
        "body": wrap(
            LABEL.format("Behind the Brand"),
            BODY.format(
                "Foundation started as a sketchbook full of ideas that didn't have a name yet. "
                "Kevin had been drawing since high school — pulling from basketball culture, "
                "Korean typography, old Chicago signage — but never with a plan to sell anything."
            ),
            BODY.format(
                "The shift happened when people started asking where he got his shirts. "
                "They weren't shirts you could buy. He'd been making them for himself."
            ),
            BODY.format(
                "That's when he called Matt. They spent six months sourcing fabric, testing fits, "
                "and figuring out how to print graphics that wouldn't crack after five washes. "
                "No shortcuts. No dropshipping. Every blank was hand-selected."
            ),
            BODY.format(
                "Foundation is the result of all that. Twelve pieces that hold up — "
                "in quality and in meaning."
            ),
            SPACER,
            CTA.format("See the Collection"),
        ),
    },
    {
        "name": "Chicago × Seoul",
        "subject": "Chicago × Seoul.",
        "folder": "storytelling",
        "template_type": "newsletter",
        "body": wrap(
            LABEL.format("Origin"),
            BODY.format(
                "Blueprint lives between two cities. Chicago gave us the grit — "
                "the concrete, the cold, the basketball courts where Kevin grew up. "
                "Seoul gave us the precision — clean lines, intentional space, respect for craft."
            ),
            BODY.format(
                "You'll see both in every piece. The graphic on the Foundation tee "
                "borrows from Korean brush calligraphy but hits like a Chicago mural. "
                "The colorways stay neutral because both cities taught us the same thing: "
                "let the work speak."
            ),
            BODY.format(
                "We're not trying to represent either place perfectly. "
                "We're making clothes that feel like where we come from."
            ),
            SPACER,
            CTA.format("Shop Foundation"),
        ),
    },
    {
        "name": "Why We Use Premium Blanks",
        "subject": "About the fabric.",
        "folder": "storytelling",
        "template_type": "newsletter",
        "body": wrap(
            LABEL.format("Materials"),
            BODY.format(
                "We get asked about our blanks a lot. Here's the honest answer: "
                "we tested over twenty before we found the ones we use now."
            ),
            BODY.format(
                "Most brands at our price point use blanks in the 150-180 GSM range. "
                "Ours run 220-280 GSM depending on the piece. Heavier cotton, tighter knit, "
                "better structure. They cost us more, but they don't pill, they don't shrink, "
                "and they don't lose shape after a few wears."
            ),
            BODY.format(
                "The fit is slightly relaxed but not oversized. We wanted something that "
                "looks intentional whether you're layering it or wearing it on its own."
            ),
            BODY.format(
                "No one sees the tag. But you feel the difference."
            ),
            SPACER,
            CTA.format("See for Yourself"),
        ),
    },
    {
        "name": "Two Friends One Brand",
        "subject": "How this started.",
        "folder": "storytelling",
        "template_type": "newsletter",
        "body": wrap(
            BODY.format(
                "Kevin and Matt have been friends since they were kids. "
                "Same neighborhood, same courts, different skills."
            ),
            BODY.format(
                "Kevin draws. Always has. He thinks in shapes and color and "
                "can look at a blank tee and see something finished. "
                "Matt builds systems. He figured out fulfillment, production, "
                "the website — the stuff that turns an idea into something you can actually hold."
            ),
            BODY.format(
                "Blueprint exists because neither of them could have done it alone. "
                "Kevin without Matt is a guy with a sketchbook. "
                "Matt without Kevin is a guy with an empty warehouse."
            ),
            BODY.format(
                "Together they made something real. That's the whole story."
            ),
        ),
    },
    {
        "name": "What Discovery Means",
        "subject": "Discovery.",
        "folder": "storytelling",
        "template_type": "newsletter",
        "body": wrap(
            LABEL.format("Collection 002 — Coming Late Summer"),
            HEADING.format("Discovery"),
            BODY.format(
                "Foundation was the starting line. It was us saying: here's who we are, "
                "here's what we make, here's what we stand for. It had to be solid because "
                "everything else builds on it."
            ),
            BODY.format(
                "Discovery is what comes next. New silhouettes. A wider palette. "
                "Graphics that push further than the first collection allowed."
            ),
            BODY.format(
                "We're not chasing trends with this one. We're following the threads "
                "that Foundation started and seeing where they lead. "
                "Some pieces will feel familiar. Others won't."
            ),
            BODY.format(
                "More details soon. Just wanted you to know it's coming."
            ),
        ),
    },
    # ── DIRECT / PRODUCT-FOCUSED ──
    {
        "name": "Foundation Breakdown",
        "subject": "Everything in Foundation.",
        "folder": "direct",
        "template_type": "newsletter",
        "body": wrap(
            LABEL.format("Collection 001"),
            HEADING.format("The Full Lineup"),
            BODY.format(
                "Foundation is our debut collection — every piece designed in Chicago, "
                "built on premium heavyweight blanks, and meant to work together or stand alone."
            ),
            BODY.format(
                "The collection covers the essentials: tees, long sleeves, and outerwear. "
                "Each graphic pulls from the same visual language — Korean typography, "
                "architectural lines, and the kind of restraint that makes you look twice."
            ),
            BODY.format(
                "Colorways are kept intentionally tight. Black, white, and earth tones "
                "that pair with whatever you already own. Nothing loud. Nothing disposable."
            ),
            BODY.format(
                "Free shipping on all U.S. orders."
            ),
            SPACER,
            CTA.format("Shop the Collection"),
        ),
    },
    {
        "name": "How to Style Foundation",
        "subject": "Three ways to wear it.",
        "folder": "direct",
        "template_type": "newsletter",
        "body": wrap(
            LABEL.format("Style Guide"),
            BODY.format(
                "Foundation pieces were designed to layer, mix, and work across contexts. "
                "Here are three ways to wear them."
            ),
            '<p style="font-size: 15px; font-weight: 600; color: #000; margin: 20px 0 4px;">1. Clean and simple</p>',
            BODY.format(
                "One Foundation tee, dark denim or trousers, clean sneakers. "
                "The graphic does the talking. Everything else stays quiet."
            ),
            '<p style="font-size: 15px; font-weight: 600; color: #000; margin: 20px 0 4px;">2. Layered</p>',
            BODY.format(
                "Foundation long sleeve under an open overshirt or jacket. "
                "The collar and hem peek out — enough to catch the detail without overdoing it."
            ),
            '<p style="font-size: 15px; font-weight: 600; color: #000; margin: 20px 0 4px;">3. All Blueprint</p>',
            BODY.format(
                "Match a Foundation tee with Blueprint outerwear. Same design language, "
                "same color family. It reads like a uniform in the best way."
            ),
            SPACER,
            CTA.format("Browse Pieces"),
        ),
    },
    {
        "name": "Sizing and Fit Guide",
        "subject": "Find your fit.",
        "folder": "direct",
        "template_type": "newsletter",
        "body": wrap(
            LABEL.format("Fit Guide"),
            HEADING.format("How Our Pieces Fit"),
            BODY.format(
                "Our fit sits between standard and relaxed. Not boxy, not slim — "
                "just enough room to move without looking oversized."
            ),
            BODY.format(
                "If you normally wear a Medium and like a clean fit, go Medium. "
                "If you prefer a looser drape for layering, size up one."
            ),
            BODY.format(
                "Our heavyweight cotton holds its shape wash after wash, "
                "so what you try on is what you'll get six months from now. "
                "No shrinking surprises."
            ),
            BODY.format(
                "Full measurements for every piece are on the product page. "
                "If you're between sizes or have questions, just reply to this email."
            ),
            SPACER,
            CTA.format("View Size Charts"),
        ),
    },
    # ── CASUAL / CONVERSATIONAL ──
    {
        "name": "Checking In",
        "subject": "Quick check-in.",
        "folder": "casual",
        "template_type": "newsletter",
        "body": wrap(
            BODY.format(
                "Just wanted to say thanks for being here. "
                "Whether you've bought something or you're just following along, it means a lot."
            ),
            BODY.format(
                "Blueprint is still a small operation — two people, no investors, no big team behind the scenes. "
                "Every order gets packed by hand. Every email gets read if you reply."
            ),
            BODY.format(
                "We've got some new stuff in the works that we think you'll like. "
                "More on that soon. For now, just wanted to check in."
            ),
            BODY.format("— Kevin & Matt"),
        ),
    },
    {
        "name": "Why We Started This",
        "subject": "Why we started this.",
        "folder": "casual",
        "template_type": "newsletter",
        "body": wrap(
            BODY.format(
                "Honestly? Because nothing fit right."
            ),
            BODY.format(
                "Not the clothes — those were fine. What didn't fit was the gap between "
                "what we wanted to wear and what was available. Everything was either fast fashion "
                "that fell apart in a month or luxury stuff that cost more than our rent."
            ),
            BODY.format(
                "We wanted well-made clothes with real design behind them, at a price "
                "that made sense. Clothes that felt personal — not mass-produced, not trying too hard."
            ),
            BODY.format(
                "So we made them. That's really it."
            ),
            SPACER,
            CTA.format("See What We Made"),
        ),
    },
    {
        "name": "Summer Plans",
        "subject": "What we're working on.",
        "folder": "casual",
        "template_type": "newsletter",
        "body": wrap(
            BODY.format(
                "Wanted to give you a quick look at what's ahead."
            ),
            BODY.format(
                "Discovery drops late summer. It's our second collection and it builds on "
                "everything Foundation started — but with new silhouettes, a wider color range, "
                "and some pieces we've never done before."
            ),
            BODY.format(
                "We're also working on some limited collaborative pieces. "
                "Can't say much yet, but if you're on this list you'll hear about it first."
            ),
            BODY.format(
                "In the meantime, Foundation is fully stocked. "
                "Good time to grab something if you've been thinking about it."
            ),
            SPACER,
            CTA.format("Shop Now"),
        ),
    },
    {
        "name": "We Read Every Reply",
        "subject": "Hit reply.",
        "folder": "casual",
        "template_type": "newsletter",
        "body": wrap(
            BODY.format(
                "This isn't a no-reply address. If you have a question, a thought, "
                "or just want to say what's up — reply to this email. We read everything."
            ),
            BODY.format(
                "Some of our best ideas have come from conversations with people on this list. "
                "Sizing feedback, colorway requests, even a few design suggestions that actually made it in."
            ),
            BODY.format(
                "We're building this thing in public and your input matters more than you think."
            ),
            BODY.format("— Kevin & Matt"),
        ),
    },
    # ── DIRECT / PRODUCT LAUNCH ──
    {
        "name": "New Drop This Week",
        "subject": "New this week.",
        "folder": "direct",
        "template_type": "promotion",
        "body": wrap(
            LABEL.format("New Arrival"),
            BODY.format(
                "We just added new pieces to the shop. Same quality you know from Foundation — "
                "heavyweight cotton, considered graphics, neutral tones that work year-round."
            ),
            BODY.format(
                "These are limited production runs. Once they're gone, "
                "we move on to the next thing. No restocks planned on these."
            ),
            BODY.format(
                "Free shipping on all U.S. orders. Easy returns if the fit isn't right."
            ),
            SPACER,
            CTA.format("See What's New"),
        ),
    },
    {
        "name": "Restock Alert",
        "subject": "Back in stock.",
        "folder": "direct",
        "template_type": "promotion",
        "body": wrap(
            LABEL.format("Restock"),
            BODY.format(
                "A few of our most-requested pieces are back. "
                "Same specs, same fit — we don't change what works."
            ),
            BODY.format(
                "Last run sold out in about two weeks. We made a slightly larger batch this time, "
                "but it's still a limited run."
            ),
            BODY.format(
                "If you missed it the first time, now's your window."
            ),
            SPACER,
            CTA.format("Shop the Restock"),
        ),
    },
    {
        "name": "Free Shipping Reminder",
        "subject": "Shipping is on us.",
        "folder": "direct",
        "template_type": "promotion",
        "body": wrap(
            BODY.format(
                "Just a reminder — free shipping on every U.S. order, no minimum. "
                "We cover it because we'd rather you spend on the clothes, not the delivery."
            ),
            BODY.format(
                "Orders ship within 1-2 business days. Most arrive in 3-5 days depending on where you are."
            ),
            BODY.format(
                "If anything doesn't fit right, returns are easy. No hassle, no questions."
            ),
            SPACER,
            CTA.format("Start Shopping"),
        ),
    },
]


class Command(BaseCommand):
    help = "Add longer-form, content-rich email templates for the swipe interface"

    def handle(self, *args, **options):
        created = 0
        skipped = 0

        for t in TEMPLATES:
            _, was_created = EmailTemplate.objects.get_or_create(
                name=t["name"],
                defaults={
                    "subject": t["subject"],
                    "html_body": t["body"],
                    "folder": t["folder"],
                    "template_type": t["template_type"],
                    "auto_trigger": "manual",
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created {created} templates, skipped {skipped} (already existed)."
            )
        )
