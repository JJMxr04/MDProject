from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.shortcuts import redirect

@login_required
@require_POST
def regenerate_friend_code(request):
    try:
        new_code = request.user.regenerate_friend_code()
        messages.success(request, 'Your friend code has been updated successfully!')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'new_code': new_code
            })
        return redirect('profile')  # or wherever you want to redirect
        
    except Exception as e:
        messages.error(request, 'Failed to generate new friend code. Please try again.')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
        return redirect('profile')