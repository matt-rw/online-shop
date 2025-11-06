from django.shortcuts import render
from django.core.mail import send_mail

from .forms import SubscribeForm
from .models import EmailSubscription


def subscribe(request):
    if request.method == 'POST':
        form = SubscribeForm(request.POST)
        print(form.is_valid())
        if form.is_valid():
            data = form.cleaned_data
            # Populate if email is new
            sub, created = EmailSubscription.objects.get_or_create(
                email=data['email']
            )
            print(sub)
            print(created)
            return render(request, '', {'form': form})
            
            # Send email
            full_message = """
            Test
            """

            # send_mail(
            #    subject='Subject',
            #    message=full_message,
            #    from_email=data['email'],
            #    recipient_list=[settings.CONTACT_FORM_RECIPIENT],
            #    fail_silently=False
            # )
            # return render(request, 'emails/subscribe.html', {'form': form})
        else:
            print('Form not valid')
            return render(request, 'emails/subscribe.html', {'form': form})




    """
    if not sub.is_confirmed:
        sub.unsub_token = sub.unsub_token or get_random_string(48)
        sub.save()
        confirm_url = request.build_absolute_uri(
            reverse('emails:confirm') + f'?email={sub.email}'
        )
        send_mail(
            'Confirm your subscription',
            f'Click to confirm: {confirm_url}',
            None,
            [sub.email]
        )
        return redirect('emails:thanks')
    """
    
