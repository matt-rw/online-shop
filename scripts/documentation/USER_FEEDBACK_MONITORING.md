# User Feedback & Performance Monitoring Guide

## Overview

After deploying your optimized homepage, you should monitor:
1. **Performance metrics** (load times, bounce rates)
2. **User behavior** (conversions, engagement)
3. **Technical issues** (errors, video playback)
4. **Direct feedback** (user reports, comments)

---

## 1. Performance Monitoring Tools

### Google Analytics 4 (Free & Essential)

#### Setup:
```html
<!-- Add to templates/base.html in <head> section -->
{% if not DEBUG %}
<!-- Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id=YOUR-GA4-ID"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'YOUR-GA4-ID');
</script>
{% endif %}
```

#### Key Metrics to Track:
- **Bounce Rate:** Should be <60% (lower is better)
- **Average Session Duration:** Should be >1 minute
- **Pages per Session:** Should be >2
- **Page Load Time:** Should be <3 seconds

#### Watch For:
- ❌ High bounce rate on mobile (>70%) → Video loading issues
- ❌ Very short sessions (<30s) → Performance problems
- ✅ Low bounce rate (<50%) → Good performance
- ✅ Increasing session duration → Users engaged

---

### Google PageSpeed Insights (Free)

#### How to Use:
1. Go to: https://pagespeed.web.dev/
2. Enter your homepage URL
3. Run test for Mobile and Desktop

#### Target Scores:
- **Mobile:** 75+ (Good), 90+ (Excellent)
- **Desktop:** 85+ (Good), 95+ (Excellent)

#### Key Metrics (Core Web Vitals):
- **LCP (Largest Contentful Paint):** <2.5s ✅
- **FID (First Input Delay):** <100ms ✅
- **CLS (Cumulative Layout Shift):** <0.1 ✅

#### Schedule:
- Test immediately after deployment
- Re-test after video optimization
- Monthly checks ongoing

---

### Hotjar or Microsoft Clarity (Free - User Behavior)

#### What They Show:
- **Heatmaps:** Where users click/scroll
- **Session Recordings:** Watch real user sessions
- **Rage Clicks:** Users clicking repeatedly (frustration)
- **Dead Clicks:** Clicks on non-interactive elements

#### Setup (Microsoft Clarity - Easiest):
```html
<!-- Add to templates/base.html before </head> -->
{% if not DEBUG %}
<script type="text/javascript">
  (function(c,l,a,r,i,t,y){
    c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};
    t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
    y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
  })(window, document, "clarity", "script", "YOUR_PROJECT_ID");
</script>
{% endif %}
```

#### Watch For:
- ❌ Users leaving during video section load
- ❌ Rage clicks on signup forms
- ❌ Quick exits after page loads
- ✅ Users scrolling through entire page
- ✅ High engagement with signup forms

---

## 2. Conversion & Signup Tracking

### Email/SMS Signup Monitoring

#### Add to Django Views:
```python
# shop/views.py

import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

def subscribe(request):
    if request.method == 'POST':
        email = request.POST.get('email')

        # Log signup with metadata
        logger.info(f"Email signup: {email}", extra={
            'user_agent': request.META.get('HTTP_USER_AGENT'),
            'device': 'mobile' if 'Mobile' in request.META.get('HTTP_USER_AGENT', '') else 'desktop',
            'referer': request.META.get('HTTP_REFERER'),
            'timestamp': timezone.now()
        })

        # ... rest of your signup logic
```

#### Track These Metrics:
- **Conversion Rate:** (Signups / Visitors) × 100
  - Target: 2-5% (good), 5-10% (excellent)
- **Mobile vs Desktop Conversions:** Should be similar
- **Time to First Signup:** How long after page load
- **Modal vs Inline Form:** Which converts better

#### Setup Dashboard:
Create simple admin view to track:
```python
# shop/admin_views.py

from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

def signup_stats(request):
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    stats = {
        'today': EmailSubscriber.objects.filter(created_at__date=today).count(),
        'week': EmailSubscriber.objects.filter(created_at__gte=week_ago).count(),
        'month': EmailSubscriber.objects.filter(created_at__gte=month_ago).count(),
        'total': EmailSubscriber.objects.count(),
    }

    # Device breakdown
    # (You'd need to add device field to model)

    return render(request, 'admin/signup_stats.html', {'stats': stats})
```

---

## 3. Technical Monitoring

### Video Playback Tracking

Add JavaScript to track video issues:

```javascript
// templates/home/home_page.html - Add to extra_js block

// Track video loading performance
const video = document.getElementById('foundation-video');
let videoLoadStartTime = Date.now();

video.addEventListener('loadstart', function() {
  videoLoadStartTime = Date.now();
  console.log('Video started loading');
});

video.addEventListener('loadeddata', function() {
  const loadTime = Date.now() - videoLoadStartTime;
  console.log(`Video loaded in ${loadTime}ms`);

  // Send to analytics if you want
  if (typeof gtag !== 'undefined') {
    gtag('event', 'video_loaded', {
      'load_time': loadTime,
      'video_source': this.currentSrc.includes('mobile') ? 'mobile' : 'desktop'
    });
  }
});

video.addEventListener('error', function(e) {
  console.error('Video error:', e);

  // Send error to analytics
  if (typeof gtag !== 'undefined') {
    gtag('event', 'video_error', {
      'error_type': e.type,
      'video_source': this.currentSrc
    });
  }
});

// Track which video version was used
video.addEventListener('play', function() {
  const source = this.currentSrc.includes('mobile') ? 'mobile' :
                 this.currentSrc.includes('desktop') ? 'desktop' : 'original';

  if (typeof gtag !== 'undefined') {
    gtag('event', 'video_version_used', {
      'version': source
    });
  }
}, { once: true });
```

### Django Logging Setup

```python
# settings.py

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'logs/homepage.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'shop': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

---

## 4. Direct User Feedback

### Simple Feedback Widget

Add to homepage footer:

```html
<!-- templates/home/home_page.html - Add before </footer> -->

<!-- Feedback Button (Floating) -->
<button id="feedback-btn"
        class="fixed bottom-4 right-4 z-50 bg-yellow-400 hover:bg-yellow-500 text-black font-bold py-2 px-4 rounded-full shadow-lg transition-all hover:scale-105"
        onclick="openFeedbackModal()">
  💬 Feedback
</button>

<!-- Feedback Modal -->
<div id="feedback-modal" class="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center hidden">
  <div class="bg-white rounded-xl shadow-2xl max-w-md w-full mx-4 p-6">
    <div class="flex justify-between items-center mb-4">
      <h3 class="text-xl font-bold text-gray-900">Share Your Feedback</h3>
      <button onclick="closeFeedbackModal()" class="text-gray-500 hover:text-gray-700">
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
        </svg>
      </button>
    </div>

    <form method="POST" action="{% url 'shop:submit_feedback' %}" class="space-y-4">
      {% csrf_token %}

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">
          How was your experience?
        </label>
        <div class="flex gap-2 justify-center">
          <button type="button" class="text-4xl hover:scale-125 transition-transform" onclick="setRating(1)">😞</button>
          <button type="button" class="text-4xl hover:scale-125 transition-transform" onclick="setRating(2)">😐</button>
          <button type="button" class="text-4xl hover:scale-125 transition-transform" onclick="setRating(3)">🙂</button>
          <button type="button" class="text-4xl hover:scale-125 transition-transform" onclick="setRating(4)">😊</button>
          <button type="button" class="text-4xl hover:scale-125 transition-transform" onclick="setRating(5)">🤩</button>
        </div>
        <input type="hidden" name="rating" id="rating-input" required>
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">
          What could we improve?
        </label>
        <textarea name="message" rows="4"
                  class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-yellow-400 focus:border-transparent"
                  placeholder="Tell us about your experience..."></textarea>
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">
          Email (optional)
        </label>
        <input type="email" name="email"
               class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-yellow-400 focus:border-transparent"
               placeholder="your@email.com">
      </div>

      <button type="submit"
              class="w-full bg-yellow-400 hover:bg-yellow-500 text-black font-bold py-3 rounded-lg transition-colors">
        Send Feedback
      </button>
    </form>
  </div>
</div>

<script>
function openFeedbackModal() {
  document.getElementById('feedback-modal').classList.remove('hidden');
}

function closeFeedbackModal() {
  document.getElementById('feedback-modal').classList.add('hidden');
}

function setRating(rating) {
  document.getElementById('rating-input').value = rating;
  // Highlight selected emoji
  document.querySelectorAll('#feedback-modal button[type="button"]').forEach((btn, idx) => {
    btn.style.opacity = idx + 1 === rating ? '1' : '0.3';
  });
}

// Close on outside click
document.getElementById('feedback-modal').addEventListener('click', function(e) {
  if (e.target === this) closeFeedbackModal();
});
</script>
```

### Django Model & View:

```python
# shop/models.py

class UserFeedback(models.Model):
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    message = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    user_agent = models.CharField(max_length=500, blank=True)
    page_url = models.URLField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.rating}★ - {self.created_at.strftime('%Y-%m-%d')}"

# shop/views.py

from django.contrib import messages
from django.shortcuts import redirect

def submit_feedback(request):
    if request.method == 'POST':
        UserFeedback.objects.create(
            rating=request.POST.get('rating'),
            message=request.POST.get('message', ''),
            email=request.POST.get('email', ''),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            page_url=request.META.get('HTTP_REFERER', '')
        )
        messages.success(request, "Thank you for your feedback! 🙏")
        return redirect('shop:home')
    return redirect('shop:home')

# shop/urls.py

urlpatterns = [
    # ... existing patterns
    path('feedback/', views.submit_feedback, name='submit_feedback'),
]

# shop/admin.py

from django.contrib import admin
from .models import UserFeedback

@admin.register(UserFeedback)
class UserFeedbackAdmin(admin.ModelAdmin):
    list_display = ['rating', 'message_preview', 'email', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['message', 'email']

    def message_preview(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_preview.short_description = 'Message'
```

---

## 5. Monitoring Checklist

### Immediately After Deployment (Day 1)

- [ ] Run Google PageSpeed Insights
  - Mobile score: _____
  - Desktop score: _____
  - Core Web Vitals: ✅/❌
- [ ] Check Google Analytics is tracking
- [ ] Test video loads on mobile device
- [ ] Test video loads on desktop
- [ ] Verify signup forms work
- [ ] Check browser console for errors

### First Week

- [ ] Daily check: Any error spikes?
- [ ] Monitor bounce rate daily
- [ ] Check signup conversion rate
- [ ] Review any user feedback received
- [ ] Test on different devices/browsers
- [ ] Monitor video loading times

**Key Metrics to Track:**
- Bounce rate: _____%
- Avg session: _____min
- Signups: _____
- Mobile vs Desktop traffic: _____%

### First Month

- [ ] Weekly PageSpeed checks
- [ ] Review GA4 behavior flow
- [ ] Analyze Clarity/Hotjar recordings
- [ ] Calculate conversion rates
- [ ] Check for slow page trends
- [ ] Review user feedback patterns

**Questions to Answer:**
- Is bounce rate acceptable (<60%)?
- Are mobile users converting?
- Any recurring feedback themes?
- Video loading causing issues?

---

## 6. Red Flags to Watch For

### Performance Issues

❌ **High bounce rate (>70%):**
- Action: Check page load times
- Possible cause: Video too slow to load
- Fix: Re-optimize or remove video

❌ **Very short sessions (<30s):**
- Action: Review Clarity recordings
- Possible cause: Content not engaging or slow load
- Fix: Improve content or performance

❌ **Mobile bounce much higher than desktop:**
- Action: Test on real mobile devices
- Possible cause: Mobile video issues
- Fix: Check mobile.mp4 file, reduce quality further

### Technical Issues

❌ **Console errors in browser:**
- Action: Open DevTools, check Console tab
- Fix: Review and fix JavaScript errors

❌ **Video not playing:**
- Action: Check video file paths
- Action: Verify video files uploaded correctly
- Fix: Check MIME types, file formats

❌ **Forms not submitting:**
- Action: Check Django logs
- Action: Verify CSRF tokens
- Fix: Review form validation

### User Feedback Issues

❌ **Low ratings (<3 stars consistently):**
- Action: Read detailed feedback
- Action: Identify common complaints
- Fix: Address top issues first

❌ **"Page is slow" feedback:**
- Action: Run PageSpeed test
- Action: Check video loading
- Fix: Further optimize or remove heavy assets

---

## 7. Success Indicators

✅ **Good Performance:**
- Bounce rate: <50%
- Avg session: >2 minutes
- PageSpeed score: >80
- Core Web Vitals: All green

✅ **Good Conversions:**
- Signup rate: 2-5%+ of visitors
- Form completion: >80%
- Modal close without signup: <70%

✅ **Positive Feedback:**
- Average rating: >4 stars
- Positive comments about design/speed
- Low complaint rate

✅ **Technical Health:**
- No console errors
- Video loads <3 seconds
- All forms working
- No broken links

---

## 8. Tools Summary

### Free Tools (Essential):
1. **Google Analytics 4** - Traffic & behavior
2. **Google PageSpeed Insights** - Performance scores
3. **Microsoft Clarity** - Session recordings & heatmaps
4. **Browser DevTools** - Technical debugging

### Paid Tools (Optional):
1. **Hotjar** ($0-$99/mo) - Advanced heatmaps
2. **Sentry** ($0-$26/mo) - Error tracking
3. **New Relic** ($0-$99/mo) - Application monitoring
4. **Mixpanel** ($0-$25/mo) - Advanced analytics

### Built-in (Django):
1. **Django Logs** - Server-side tracking
2. **Admin Dashboard** - Manual review
3. **Database Queries** - Signup tracking

---

## 9. Weekly Review Template

```
WEEK OF: [Date]

TRAFFIC:
- Total visitors: _____
- Mobile vs Desktop: ____% / ____%
- Bounce rate: _____%
- Avg session: _____min

CONVERSIONS:
- Email signups: _____
- SMS signups: _____
- Conversion rate: _____%

PERFORMANCE:
- PageSpeed (mobile): _____
- PageSpeed (desktop): _____
- Avg load time: _____s

FEEDBACK:
- Total responses: _____
- Avg rating: _____ / 5
- Key themes: __________

ISSUES:
- Critical: _____
- Minor: _____
- Fixed: _____

ACTION ITEMS:
1. _____
2. _____
3. _____
```

---

## 10. Quick Win Optimizations

If metrics show issues:

**High Bounce Rate?**
→ Reduce video file sizes further
→ Remove video on mobile completely
→ Lazy load video (only load when scrolled to)

**Low Conversions?**
→ A/B test modal timing (immediate vs delayed)
→ Simplify signup form
→ Add social proof ("Join 1,000+ subscribers")

**Slow Load Times?**
→ Enable Django template caching
→ Use CDN for static files
→ Further compress images

**Technical Errors?**
→ Check Django logs: `tail -f logs/homepage.log`
→ Review browser console
→ Test in incognito mode

---

## Summary

**Immediate Setup (1 hour):**
1. Add Google Analytics
2. Add Microsoft Clarity
3. Add feedback widget
4. Create Django logging

**Ongoing Monitoring:**
- Daily: Check GA4 dashboard
- Weekly: Review Clarity sessions
- Monthly: Full performance audit

**Success Metrics:**
- Bounce rate: <60%
- Conversion rate: 2-5%
- PageSpeed: >80
- User rating: >4 stars

With these tools in place, you'll have complete visibility into how users experience your homepage and can make data-driven improvements! 📊🚀
