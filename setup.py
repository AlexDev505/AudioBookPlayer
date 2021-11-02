"""

    Сборка приложения в exe.
    Для использования, дополнительно установите cx_Freeze используя
    pip install -U cx_freeze

    Сборка проекта осуществляется в 2 этапа.
    1. Сборка в exe. Осуществляется с помощью cx_Freeze.
    2. Сборка в exe установщик, осуществляемая при помощи nsis.

"""

import re

import cx_Freeze

__version__ = "1.0a2"
target_dir = rf"build\ABPlayer"

with open(r"ABPlayer\main.py", encoding="utf-8") as file:
    text = file.read()
text = re.sub(
    r'os.environ\["VERSION"] = ".+"', f'os.environ["VERSION"] = "{__version__}"', text
)
with open(r"ABPlayer\main.py", "w", encoding="utf-8") as file:
    file.write(text)

with open("installer.nsi") as file:
    text = file.read()
text = re.sub(
    r'!define PRODUCT_VERSION ".+"', f'!define PRODUCT_VERSION "{__version__}"', text
)
with open("installer.nsi", "w") as file:
    file.write(text)


executables = [
    cx_Freeze.Executable(
        script=r"ABPlayer\run.py",  # Запускаемый файл
        # base="Win32GUI",  # Использует pythonw.exe
        targetName="ABPlayer.exe",  # Имя exe
        icon=r"interface\resources\icon.ico",
    )
]
excludes = [
    "test",
    "tkinter",
    "lib2to3",
    "pydoc_data",
    "pkg_resources",
]  # Ненужные библиотеки
zip_include_packages = [
    "collections",
    "encodings",
    "importlib",
    "json",
    "click",
    "ctypes",
    "flask",
    "logging",
    "urllib",
    "threading",
    "email",
    "http",
    "html",
    "distutils",
    "multiprocessing",
    "xmlrpc",
    "wsgiref",
    "werkzeug",
    "xml",
    "werkzeug",
    "itsdangerous",
    "sqlite3_api",
    "sqlite3",
    "openpyxl",
    "et_xmlfile",
    "idna",
    "asyncio",
    "requests",
    "unittest",
    "urllib3",
    "concurrent",
    "packaging",
]  # Библиотеки, помещаемые в архив

cx_Freeze.setup(
    name="Журнал термометрии",
    options={
        "build_exe": {
            "packages": ["PyQt5", "selenium", "requests", "eyed3"],  # Библиотеки
            "excludes": excludes,
            "zip_include_packages": zip_include_packages,
        },
        "build": {"build_exe": target_dir},  # Место назначения
    },
    version=__version__,
    description="Приложение для ведения журнала термометрии.",
    author="AlexDev",
    executables=executables,
)

# python setup.py bdist_msi  # Сборка msi установщика
# python setup.py build  # Сборка exe
