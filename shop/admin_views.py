import csv
import io
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import get_user_model
from .models import EmailSubscription

User = get_user_model()


@staff_member_required
def subscribers_list(request):
    """
    Display list of email subscribers and registered users.
    Only accessible to admin/staff users.
    Handles CSV upload for bulk subscriber and user import.
    """
    # Handle Subscriber CSV Upload
    if request.method == 'POST' and request.FILES.get('subscriber_csv'):
        csv_file = request.FILES['subscriber_csv']

        # Validate file extension
        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'Please upload a CSV file.')
            return redirect('shop:admin_subscribers')

        try:
            # Read CSV file
            decoded_file = csv_file.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            csv_reader = csv.DictReader(io_string)

            added_count = 0
            skipped_count = 0
            errors = []

            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 (row 1 is header)
                email = row.get('email', '').strip().lower()
                is_confirmed = row.get('is_confirmed', '').strip().lower() in ['true', '1', 'yes']
                source = row.get('source', 'csv_upload').strip() or 'csv_upload'

                if not email:
                    errors.append(f"Row {row_num}: Missing email")
                    continue

                # Create or get subscriber
                try:
                    sub, created = EmailSubscription.objects.get_or_create(
                        email=email,
                        defaults={
                            'source': source,
                            'is_confirmed': is_confirmed
                        }
                    )
                    if created:
                        added_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    errors.append(f"Row {row_num} ({email}): {str(e)}")

            # Display results
            if added_count > 0:
                messages.success(request, f'Successfully added {added_count} new subscriber(s).')
            if skipped_count > 0:
                messages.info(request, f'Skipped {skipped_count} existing subscriber(s).')
            if errors:
                for error in errors[:5]:  # Show first 5 errors
                    messages.warning(request, error)
                if len(errors) > 5:
                    messages.warning(request, f'...and {len(errors) - 5} more errors.')

            return redirect('shop:admin_subscribers')

        except Exception as e:
            messages.error(request, f'Error processing CSV: {str(e)}')
            return redirect('shop:admin_subscribers')

    # Handle User CSV Upload
    if request.method == 'POST' and request.FILES.get('user_csv'):
        csv_file = request.FILES['user_csv']

        # Validate file extension
        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'Please upload a CSV file.')
            return redirect('shop:admin_subscribers')

        try:
            # Read CSV file
            decoded_file = csv_file.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            csv_reader = csv.DictReader(io_string)

            added_count = 0
            skipped_count = 0
            errors = []

            for row_num, row in enumerate(csv_reader, start=2):
                username = row.get('username', '').strip()
                email = row.get('email', '').strip().lower()
                password = row.get('password', '').strip() or User.objects.make_random_password()

                if not username or not email:
                    errors.append(f"Row {row_num}: Missing username or email")
                    continue

                # Create user if doesn't exist
                try:
                    user, created = User.objects.get_or_create(
                        username=username,
                        defaults={
                            'email': email,
                        }
                    )
                    if created:
                        user.set_password(password)
                        user.save()
                        added_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    errors.append(f"Row {row_num} ({username}): {str(e)}")

            # Display results
            if added_count > 0:
                messages.success(request, f'Successfully added {added_count} new user(s).')
            if skipped_count > 0:
                messages.info(request, f'Skipped {skipped_count} existing user(s).')
            if errors:
                for error in errors[:5]:  # Show first 5 errors
                    messages.warning(request, error)
                if len(errors) > 5:
                    messages.warning(request, f'...and {len(errors) - 5} more errors.')

            return redirect('shop:admin_subscribers')

        except Exception as e:
            messages.error(request, f'Error processing CSV: {str(e)}')
            return redirect('shop:admin_subscribers')

    # GET request - display page
    subscribers = EmailSubscription.objects.all().order_by('-subscribed_at')
    users = User.objects.all().order_by('-date_joined')

    context = {
        'subscribers': subscribers,
        'users': users,
        'total_subscribers': subscribers.count(),
        'total_users': users.count(),
        'confirmed_subscribers': subscribers.filter(is_confirmed=True).count(),
    }

    return render(request, 'admin/subscribers_list.html', context)
