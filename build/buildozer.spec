[app]

title = ABPlayer
package.name = abp
package.domain = com.abplayer
source.dir = ../src
source.include_exts = py,png,jpg,svg,gif,atlas,html,jar,css,js
source.include_patterns = assets/*

# version.regex = os.environ\["VERSION"] = "(.*)"
# version.filename = %(source.dir)s/main.py
version = 4.0.0

requirements = python3==3.14.2,hostpython3==3.14.2,kivy,pywebview,bottle,proxy-tools,typing_extensions,platformdirs,flask==2.2.4,loguru,pygments

presplash.filename = ./sources/icon.png
icon.filename = ./sources/icon.png

orientation = portrait,landscape

# OSX Specific
osx.python_version = 3.14.2
osx.kivy_version = 2.3.1

# Android specific
fullscreen = 0
android.presplash_color = #202225
# (string) Presplash animation using Lottie format.
# see https://lottiefiles.com/ for examples and https://airbnb.design/lottie/
# for general documentation.
# Lottie files can be created using various tools, like Adobe After Effect or Synfig.
#android.presplash_lottie = "path/to/lottie/file.json"
# (See https://python-for-android.readthedocs.io/en/latest/buildoptions/#build-options-1 for all the supported syntaxes and properties)
android.permissions = android.permission.INTERNET, (name=android.permission.WRITE_EXTERNAL_STORAGE;maxSdkVersion=18)
# (list) features (adds uses-feature -tags to manifest)
#android.features = android.hardware.usb.host
p4a.branch = develop
android.api = 36
android.ndk = 29
# (str) Android app theme, default is ok for Kivy-based app
android.apptheme = @android:style/Theme.Material.NoActionBar
android.add_jars = /home/alexdev505/projects/AudioBookPlayer/venv/lib/python3.14/site-packages/webview/lib/pywebview-android.jar

# (list) Put these files or directories in the apk assets directory.
# Either form may be used, and assets need not be in 'source.include_exts'.
# 1) android.add_assets = source_asset_relative_path
# 2) android.add_assets = source_asset_path:destination_asset_relative_path
#android.add_assets =

# (list) Put these files or directories in the apk res directory.
# The option may be used in three ways, the value may contain one or zero ':'
# Some examples:
# 1) A file to add to resources, legal resource names contain ['a-z','0-9','_']
# android.add_resources = my_icons/all-inclusive.png:drawable/all_inclusive.png
# 2) A directory, here  'legal_icons' must contain resources of one kind
# android.add_resources = legal_icons:drawable
# 3) A directory, here 'legal_resources' must contain one or more directories,
# each of a resource kind:  drawable, xml, etc...
# android.add_resources = legal_resources
#android.add_resources =

# (list) The Android archs to build for, choices: armeabi-v7a, arm64-v8a, x86, x86_64
# In past, was `android.arch` as we weren't supporting builds for multiple archs at the same time.
android.archs = arm64-v8a, armeabi-v7a

# (bool) enables Android auto backup feature (Android API >=23)
android.allow_backup = True


[buildozer]
log_level = 2
warn_on_root = 1
