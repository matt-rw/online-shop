# Generated manually

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0029_order_is_test'),
    ]

    operations = [
        migrations.CreateModel(
            name='Return',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[
                    ('REQUESTED', 'Requested'),
                    ('APPROVED', 'Approved'),
                    ('REJECTED', 'Rejected'),
                    ('AWAITING_SHIPMENT', 'Awaiting Shipment'),
                    ('IN_TRANSIT', 'In Transit'),
                    ('RECEIVED', 'Received'),
                    ('REFUNDED', 'Refunded'),
                ], default='REQUESTED', max_length=20)),
                ('reason', models.CharField(choices=[
                    ('WRONG_SIZE', 'Wrong size'),
                    ('WRONG_ITEM', 'Wrong item received'),
                    ('DEFECTIVE', 'Defective/damaged'),
                    ('NOT_AS_DESCRIBED', 'Not as described'),
                    ('CHANGED_MIND', 'Changed mind'),
                    ('OTHER', 'Other'),
                ], max_length=30)),
                ('customer_notes', models.TextField(blank=True)),
                ('admin_notes', models.TextField(blank=True)),
                ('tracking_number', models.CharField(blank=True, max_length=100)),
                ('carrier', models.CharField(blank=True, max_length=50)),
                ('return_label_url', models.URLField(blank=True)),
                ('refund_amount', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('stripe_refund_id', models.CharField(blank=True, max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('received_at', models.DateTimeField(blank=True, null=True)),
                ('refunded_at', models.DateTimeField(blank=True, null=True)),
                ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='returns', to='shop.order')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ReturnItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('refund_amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('received', models.BooleanField(default=False)),
                ('condition_notes', models.TextField(blank=True)),
                ('order_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='shop.orderitem')),
                ('return_request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='shop.return')),
            ],
        ),
    ]
