page("settings-page").onShow = function(el) {
    addUrlParams({"page": el.id})
}
page("settings-page").onHide = function() {}


function toggleDarkTheme() {
    dark_theme = !dark_theme
    pywebview.api.set_dark_mode(dark_theme).then((resp) => {location.reload()})
    toggleDarkThemeCheckBox(dark_theme)
}

function toggleDarkThemeCheckBox(value) {
    if (value) document.getElementById("dark-theme-checkbox").classList.add("checked")
    else document.getElementById("dark-theme-checkbox").classList.remove("checked")
}

function changeLibraryDir() {
    clearPlayingBook()
    pywebview.api.change_library_dir().then((resp) => {
        if (resp.status != "ok") return
        content = "<div><b>Book folder changed</b></div>" + ((resp.data.new_books_count) ? `<div>Books added: ${resp.data.new_books_count}</div>` : "")
        timeout = 5
        if (!resp.data.is_old_library_empty) {
            timeout = 0
            content = content + `<div>but previously downloaded files remain in place</div>
            <div style="margin-top: 2px; text-decoration: underline; cursor:pointer" onclick="{migrateOldLibrary();this.parentElement.parentElement.remove()}">Move everything to the new location</div>
            <div style="margin-top: 2px; text-decoration: underline; cursor:pointer" onclick="{removeOldLibrary();this.parentElement.parentElement.remove()}">Delete old books from the library</div>`
        }
        createNotification(content, timeout, true)
    })
}
function migrateOldLibrary() {
    n = createNotification("<div><b>Transferring files...</b></div><div>this may take some time</div>", 0, false)
    pywebview.api.migrate_old_library().then((resp) => {
        n.querySelector(".cross-btn").click()
        if (resp.status != "ok") return
        createNotification(`<div><b>Transfer complete</b></div><div>Books transferred: ${resp.data.moved_books_count}</div>`, 10, true)
    })
}
function removeOldLibrary() {
    n = createNotification("<div><b>Deleting old books...</b></div><div>this may take some time</div>", 0, false)
    pywebview.api.remove_old_library().then((resp) => {
        n.querySelector(".cross-btn").click()
        if (resp.status != "ok") return
        createNotification(`<div><b>Deletion complete</b></div><div>Books deleted: ${resp.data.deleted_books_count}</div>`, 10, true)
    })
}

function checkForUpdates(resp) {
    if (resp.status != "ok") {
        setTimeout(checkForUpdates, 60)
        return
    }
    if (!resp.data) return
    if (resp.sable || !stable_version) {
        createNotification(
            `<div><b>Update ${resp.data.version} available</b></div>
            <a style="margin-top: 2px" href="${resp.data.url}" target="_blank">changelog</a>
            <div style="margin-top: 2px; text-decoration: underline; cursor:pointer" onclick="{updateApp();this.parentElement.parentElement.remove()}">install</div>`
        )
    } else if (!only_stable){
        createNotification(
            `<div><b>New test version available ${resp.data.version}</b></div>
            <a style="margin-top: 2px" href="${resp.data.url}" target="_blank">changelog</a>
            <div style="margin-top: 2px; text-decoration: underline; cursor:pointer" onclick="{updateApp();this.parentElement.parentElement.remove()}">install</div>
            <div style="margin-top: 2px; text-decoration: underline; cursor:pointer" onclick="{unsubscribeNotStable();this.parentElement.parentElement.remove()}">do not offer test participation</div>`
        )
    }
}

function updateApp() {
    n = createNotification("<div><b>Downloading update</b></div><div>this may take some time</div>", 0, false)
    pywebview.api.update_app().then((resp) => {
        n.querySelector(".cross-btn").click()
        if (resp.status != "ok") showError(resp.message)
    })
}
function unsubscribeNotStable() {
    pywebview.api.unsubscribe_not_stable()
}

