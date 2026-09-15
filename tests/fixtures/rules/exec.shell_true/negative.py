import subprocess


def extract(archive_name):
    # An argument list: no shell parses it, so a semicolon in the
    # filename stays part of the filename.
    subprocess.run(["tar", "-xzf", archive_name], check=True)
