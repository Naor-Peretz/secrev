requests.get(url, verify=False)
context = ssl._create_unverified_context()
context.verify_mode = ssl.CERT_NONE
