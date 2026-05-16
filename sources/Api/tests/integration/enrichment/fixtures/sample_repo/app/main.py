import internal_http_wrapper as http

def charge(amount):
    return http.post("https://api.acme-payments.io/v1/charge", json={"a": amount})