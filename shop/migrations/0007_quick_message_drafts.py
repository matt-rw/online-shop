from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0006_quick_messages'),
    ]

    operations = [
        # Remove old index first
        migrations.RemoveIndex(
            model_name='quickmessage',
            name='quickmsg_sent_idx',
        ),
        # Add draft to status choices (handled by AlterField)
        migrations.AlterField(
            model_name='quickmessage',
            name='status',
            field=models.CharField(
                choices=[
                    ('draft', 'Draft'),
                    ('sending', 'Sending'),
                    ('sent', 'Sent'),
                    ('partial', 'Partially Sent'),
                    ('failed', 'Failed'),
                ],
                default='sending',
                max_length=20,
            ),
        ),
        # Add created_at field (copy from sent_at for existing records)
        migrations.AddField(
            model_name='quickmessage',
            name='created_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
            preserve_default=False,
        ),
        # Add updated_at field
        migrations.AddField(
            model_name='quickmessage',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        # Make sent_at nullable for drafts
        migrations.AlterField(
            model_name='quickmessage',
            name='sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        # Add new indexes
        migrations.AddIndex(
            model_name='quickmessage',
            index=models.Index(fields=['-created_at'], name='quickmsg_created_idx'),
        ),
        migrations.AddIndex(
            model_name='quickmessage',
            index=models.Index(fields=['status'], name='quickmsg_status_idx'),
        ),
    ]
