# The safe loader, spelled the three ways it is actually written.
config = yaml.safe_load(text)
config = yaml.load(text, Loader=yaml.SafeLoader)
config = yaml.load(text, Loader=SafeLoader)
data = json.loads(payload)
