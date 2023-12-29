def extract_access_token( request):
    """
    Extract the access token from the Authorization header.
    """
    auth_header = request.headers.get("Authorization")

    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ")[1]

    return None