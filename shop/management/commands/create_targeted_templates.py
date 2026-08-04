from django.core.management.base import BaseCommand

from shop.models.email import EmailTemplate


WRAP = '<div style="font-family: Helvetica, Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 40px 20px; color: #333;">'
END = '</div>'
LABEL = '<p style="font-size: 11px; letter-spacing: 0.15em; text-transform: uppercase; color: #999; margin: 0 0 20px;">{}</p>'
BODY = '<p style="font-size: 15px; line-height: 1.8; color: #555; margin: 0 0 12px;">{}</p>'
CTA = '<a href="{}" style="display: inline-block; padding: 13px 28px; background: #000; color: #fff; text-decoration: none; font-size: 11px; letter-spacing: 0.15em; text-transform: uppercase; margin-top: 12px;">{}</a>'


TEMPLATES = [
    # Account creation (target_audience = no_account)
    {"name": "Create Your Account", "subject": "Your Blueprint account is waiting.", "folder": "targeted", "target_audience": "no_account",
     "body": WRAP + LABEL.format("Blueprint Apparel") + BODY.format("Create your free account to track orders, save your addresses, and get early access to new drops.") + CTA.format("https://www.blueprnt.store/accounts/signup/", "Create Account") + END},
    {"name": "Early Access", "subject": "Get early access to Discovery.", "folder": "targeted", "target_audience": "no_account",
     "body": WRAP + LABEL.format("Members Only") + BODY.format("Our next collection, Discovery, drops late summer. Blueprint members get first access before it goes public.") + BODY.format("Create your account now so you are ready.") + CTA.format("https://www.blueprnt.store/accounts/signup/", "Join Now") + END},
    {"name": "Save Your Info", "subject": "Make checkout faster next time.", "folder": "targeted", "target_audience": "no_account",
     "body": WRAP + LABEL.format("Blueprint Apparel") + BODY.format("Create an account to save your shipping address and speed up your next order. No more retyping everything.") + CTA.format("https://www.blueprnt.store/accounts/signup/", "Create Account") + END},
    {"name": "Your Order History", "subject": "Keep track of your orders.", "folder": "targeted", "target_audience": "no_account",
     "body": WRAP + LABEL.format("Blueprint Apparel") + BODY.format("With a Blueprint account, you can view your full order history, track shipments, and reorder your favorites in one click.") + CTA.format("https://www.blueprnt.store/accounts/signup/", "Create Account") + END},
    {"name": "Be First", "subject": "New drops. First access. No spam.", "folder": "targeted", "target_audience": "no_account",
     "body": WRAP + BODY.format("Blueprint members hear about new releases, restocks, and limited runs before anyone else.") + BODY.format("Takes 30 seconds. No spam. Just the good stuff.") + CTA.format("https://www.blueprnt.store/accounts/signup/", "Sign Up") + END},
    # Review requests (target_audience = review_request)
    {"name": "How was it?", "subject": "How are you liking your Blueprint?", "folder": "targeted", "target_audience": "review_request",
     "body": WRAP + LABEL.format("We want to hear from you") + BODY.format("You picked up something from Blueprint Apparel. We would love to know what you think.") + BODY.format("Your honest review helps other customers and helps us make better clothes.") + CTA.format("https://www.blueprnt.store/shop/", "Leave a Review") + END},
    {"name": "Share your thoughts", "subject": "Your opinion matters to us.", "folder": "targeted", "target_audience": "review_request",
     "body": WRAP + BODY.format("Thanks for supporting Blueprint. We are a small team and every piece of feedback helps us improve.") + BODY.format("If you have a minute, we would really appreciate a quick review.") + CTA.format("https://www.blueprnt.store/shop/", "Write a Review") + END},
    {"name": "Quick review?", "subject": "Got 30 seconds?", "folder": "targeted", "target_audience": "review_request",
     "body": WRAP + BODY.format("We hope you are enjoying your Blueprint gear. A quick review helps other customers find the right fit and size.") + CTA.format("https://www.blueprnt.store/shop/", "Leave a Review") + END},
    {"name": "Wear test complete", "subject": "You have had it for a while now.", "folder": "targeted", "target_audience": "review_request",
     "body": WRAP + LABEL.format("Blueprint Apparel") + BODY.format("By now you have worn it, washed it, and lived in it. That is the real test.") + BODY.format("How did it hold up? Let us know.") + CTA.format("https://www.blueprnt.store/shop/", "Share Your Experience") + END},
    {"name": "Rate your purchase", "subject": "Help the community.", "folder": "targeted", "target_audience": "review_request",
     "body": WRAP + BODY.format("Your review helps other customers make confident decisions. It only takes a minute.") + CTA.format("https://www.blueprnt.store/shop/", "Rate Your Purchase") + END},
]


class Command(BaseCommand):
    help = "Create targeted email templates for account creation and review requests"

    def handle(self, *args, **options):
        created = 0
        for t in TEMPLATES:
            _, was_created = EmailTemplate.objects.get_or_create(
                name=t["name"],
                defaults={
                    "subject": t["subject"],
                    "html_body": t["body"],
                    "folder": t["folder"],
                    "template_type": "custom",
                    "auto_trigger": "manual",
                    "target_audience": t["target_audience"],
                    "is_active": True,
                },
            )
            if was_created:
                created += 1

        self.stdout.write(self.style.SUCCESS(f"Created {created} targeted templates."))
