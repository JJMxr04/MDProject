from django.http import HttpResponse

def robots_txt(request):
    lines = [
        "User-agent: Googlebot",
        "Disallow: ",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")
