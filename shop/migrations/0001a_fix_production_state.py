# Migration to fix production database state
# Production was migrated with an older version of 0001_initial
# This migration will create any missing tables that should exist after 0001_initial

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0001_initial'),
    ]

    # Run raw SQL to create all missing core tables
    operations = [
        # This giant SQL block creates ALL tables from 0001_initial if they don't exist
        migrations.RunSQL(
            sql=open('shop/migrations/sql/create_missing_tables.sql').read() if False else """
            -- This migration creates all missing tables from 0001_initial using CREATE TABLE IF NOT EXISTS
            -- It's idempotent and safe to run multiple times

            -- Core tables first (no foreign keys)
            CREATE TABLE IF NOT EXISTS shop_product (
                id BIGSERIAL PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                price NUMERIC(10, 2) NOT NULL,
                stock_quantity INTEGER NOT NULL DEFAULT 0,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS shop_discount (
                id BIGSERIAL PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                code VARCHAR(50) UNIQUE,
                discount_type VARCHAR(20) NOT NULL DEFAULT 'percentage',
                value NUMERIC(10, 2) NOT NULL,
                min_purchase_amount NUMERIC(10, 2),
                max_uses INTEGER,
                times_used INTEGER NOT NULL DEFAULT 0,
                valid_from TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                valid_until TIMESTAMP WITH TIME ZONE,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                applies_to_all BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS shop_discount_is_active_idx ON shop_discount(is_active);

            CREATE TABLE IF NOT EXISTS shop_campaign (
                id BIGSERIAL PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                status VARCHAR(20) NOT NULL,
                channel VARCHAR(20) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                start_date TIMESTAMP WITH TIME ZONE,
                end_date TIMESTAMP WITH TIME ZONE,
                total_sent INTEGER NOT NULL DEFAULT 0,
                total_opened INTEGER NOT NULL DEFAULT 0,
                total_clicked INTEGER NOT NULL DEFAULT 0,
                total_converted INTEGER NOT NULL DEFAULT 0,
                revenue_generated NUMERIC(10, 2) NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS shop_emailtemplate (
                id BIGSERIAL PRIMARY KEY,
                name VARCHAR(200) NOT NULL UNIQUE,
                subject VARCHAR(200) NOT NULL,
                body_html TEXT NOT NULL,
                body_text TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                last_used TIMESTAMP WITH TIME ZONE,
                notes TEXT NOT NULL DEFAULT '',
                folder_id BIGINT
            );

            CREATE TABLE IF NOT EXISTS shop_smstemplate (
                id BIGSERIAL PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                body TEXT NOT NULL,
                character_count INTEGER NOT NULL DEFAULT 0,
                segment_count INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            );

            -- Tables with foreign keys
            CREATE TABLE IF NOT EXISTS shop_campaignmessage (
                id BIGSERIAL PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                message_type VARCHAR(20) NOT NULL,
                custom_subject VARCHAR(200) NOT NULL DEFAULT '',
                custom_content TEXT NOT NULL DEFAULT '',
                send_mode VARCHAR(20) NOT NULL DEFAULT 'auto',
                media_urls TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                trigger_type VARCHAR(20) NOT NULL DEFAULT 'immediate',
                delay_days INTEGER NOT NULL DEFAULT 0,
                delay_hours INTEGER NOT NULL DEFAULT 0,
                scheduled_date TIMESTAMP WITH TIME ZONE,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                total_recipients INTEGER NOT NULL DEFAULT 0,
                sent_count INTEGER NOT NULL DEFAULT 0,
                failed_count INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                sent_at TIMESTAMP WITH TIME ZONE,
                "order" INTEGER NOT NULL DEFAULT 0,
                campaign_id BIGINT REFERENCES shop_campaign(id) ON DELETE CASCADE,
                discount_id BIGINT REFERENCES shop_discount(id) ON DELETE SET NULL,
                email_template_id BIGINT REFERENCES shop_emailtemplate(id) ON DELETE SET NULL,
                sms_template_id BIGINT REFERENCES shop_smstemplate(id) ON DELETE SET NULL
            );
            CREATE INDEX IF NOT EXISTS shop_campaignmessage_campaign_id_idx ON shop_campaignmessage(campaign_id);
            CREATE INDEX IF NOT EXISTS shop_campaignmessage_discount_id_idx ON shop_campaignmessage(discount_id);
            CREATE INDEX IF NOT EXISTS shop_campaignmessage_email_template_id_idx ON shop_campaignmessage(email_template_id);
            CREATE INDEX IF NOT EXISTS shop_campaignmessage_sms_template_id_idx ON shop_campaignmessage(sms_template_id);

            -- Many-to-many tables
            CREATE TABLE IF NOT EXISTS shop_discount_products (
                id BIGSERIAL PRIMARY KEY,
                discount_id BIGINT NOT NULL REFERENCES shop_discount(id) ON DELETE CASCADE,
                product_id BIGINT NOT NULL REFERENCES shop_product(id) ON DELETE CASCADE,
                UNIQUE (discount_id, product_id)
            );

            CREATE TABLE IF NOT EXISTS shop_campaignmessage_products (
                id BIGSERIAL PRIMARY KEY,
                campaignmessage_id BIGINT NOT NULL REFERENCES shop_campaignmessage(id) ON DELETE CASCADE,
                product_id BIGINT NOT NULL REFERENCES shop_product(id) ON DELETE CASCADE,
                UNIQUE (campaignmessage_id, product_id)
            );
            """,
            reverse_sql="-- No reverse - don't drop tables"
        ),
    ]
