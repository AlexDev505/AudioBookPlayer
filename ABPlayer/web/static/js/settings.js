page("settings-page").onShow = function(el) {
    addUrlParams({"page": el.id})
}
page("book-page").onHide = function() {}


function toggleDarkTheme() {
    dark_theme = !dark_theme
    pywebview.api.set_dark_mode(dark_theme).then((resp) => {location.reload()})
    toggleDarkThemeCheckBox(dark_theme)
}

function toggleDarkThemeCheckBox(value) {
    if (value) document.getElementById("dark-theme-checkbox").classList.add("checked")
    else document.getElementById("dark-theme-checkbox").classList.remove("checked")
}
