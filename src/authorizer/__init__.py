from src.settings import settings

if settings.authorizer == "ceda":
    from src.authorizer.egi_authorizer import EGIAuthorizer as Auth
else:
    from src.authorizer.globus_authorizer import GlobusAuthorizer as Auth

Authorizer = Auth
