requests.get(url, verify=True)
requests.get(url, verify=CA_BUNDLE)
context = ssl.create_default_context()
context.verify_mode = ssl.CERT_REQUIRED
