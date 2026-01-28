from pythonforandroid.recipe import RustCompiledComponentsRecipe


class OrjsonRecipe(RustCompiledComponentsRecipe):
    version = "3.11.5"
    url = "https://github.com/ijl/orjson/archive/refs/tags/{version}.tar.gz"
    use_maturin = True
    hostpython_prerequisites = ["typing_extensions", "maturin>=1.3.0,<2.0.0"]
    depends = ["rust"]
    site_packages_name = "orjson"

    def get_recipe_env(self, *args, **kwargs):
        env = super().get_recipe_env(*args, **kwargs)
        env["ANDROID_API_LEVEL"] = str(self.ctx.android_api)
        return env


recipe = OrjsonRecipe()
