import esgvoc.api as ev

projects = ev.get_all_projects()

for proj in projects:
    print(proj)
