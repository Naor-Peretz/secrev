path = os.path.join(base_directory, user_supplied_name)
destination = Path(root) / name
archive.extract("../../etc/passwd")
shutil.copyfile(source, destination)
os.remove(target)
