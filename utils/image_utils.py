SUPPORTED_FORMATS = ['.jpeg', '.jpg', '.ico', '.png', '.gif', '.bmp', '.tiff', '.webp']
UNITS = ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi")


def sizeof_fmt(num: int | float, suffix: str = "B") -> str:
    for unit in UNITS:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"
