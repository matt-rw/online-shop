# Generated migration for product enhancements

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0014_campaignmessage_media_urls_campaignmessage_notes_and_more'),
    ]

    operations = [
        # Add missing Product fields
        migrations.AddField(
            model_name='product',
            name='description',
            field=models.TextField(blank=True, help_text='Product description and details'),
        ),
        migrations.AddField(
            model_name='product',
            name='category',
            field=models.CharField(
                max_length=100,
                blank=True,
                help_text='Product category (e.g., T-Shirts, Hoodies, Pants)',
                db_index=True
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='featured',
            field=models.BooleanField(
                default=False,
                help_text='Feature this product on homepage',
                db_index=True
            ),
        ),
        migrations.AddField(
            model_name='product',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name='product',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),

        # Add ProductVariant SKU
        migrations.AddField(
            model_name='productvariant',
            name='sku',
            field=models.CharField(
                max_length=50,
                blank=True,
                unique=True,
                null=True,
                help_text='Stock Keeping Unit - auto-generated if blank'
            ),
        ),

        # Create Discount model
        migrations.CreateModel(
            name='Discount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, help_text='Internal name for this discount')),
                ('code', models.CharField(max_length=50, unique=True, blank=True, help_text='Discount code (leave blank for auto-apply)')),
                ('discount_type', models.CharField(
                    max_length=20,
                    choices=[
                        ('percentage', 'Percentage Off'),
                        ('fixed', 'Fixed Amount Off'),
                        ('bogo', 'Buy One Get One'),
                    ],
                    default='percentage'
                )),
                ('value', models.DecimalField(
                    max_digits=10,
                    decimal_places=2,
                    help_text='Percentage (e.g., 20 for 20%) or fixed amount (e.g., 10.00 for $10 off)'
                )),
                ('min_purchase_amount', models.DecimalField(
                    max_digits=10,
                    decimal_places=2,
                    null=True,
                    blank=True,
                    help_text='Minimum purchase amount to qualify'
                )),
                ('max_uses', models.IntegerField(
                    null=True,
                    blank=True,
                    help_text='Maximum number of times this discount can be used (blank = unlimited)'
                )),
                ('times_used', models.IntegerField(default=0)),
                ('valid_from', models.DateTimeField(help_text='Discount becomes active at this time')),
                ('valid_until', models.DateTimeField(null=True, blank=True, help_text='Discount expires at this time (blank = no expiration)')),
                ('is_active', models.BooleanField(default=True, db_index=True)),
                ('applies_to_all', models.BooleanField(
                    default=True,
                    help_text='Apply to all products or specific products only'
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Discount',
                'verbose_name_plural': 'Discounts',
                'ordering': ['-created_at'],
            },
        ),

        # Many-to-many relationship for discount products
        migrations.AddField(
            model_name='discount',
            name='products',
            field=models.ManyToManyField(
                to='shop.Product',
                blank=True,
                related_name='discounts',
                help_text='Specific products this discount applies to (if not applying to all)'
            ),
        ),
    ]
