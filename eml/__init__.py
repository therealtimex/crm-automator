from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("crm-automator")
except PackageNotFoundError:
    # Fallback if the package is not installed (e.g. during local development)
    __version__ = "1.5.1" 
