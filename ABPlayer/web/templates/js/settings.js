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

function setLanguage(button) {
    lang = button.dataset.lang
    pywebview.api.set_language(lang).then((resp) => {location.reload()})
    toggleLanguageButton(lang)
}

function toggleLanguageButton(lang) {
    checked = document.querySelector(".lang-checkbox.checked")
    if (checked) checked.classList.remove("checked")
    document.querySelector(`.lang-checkbox[data-lang='${lang}']`).classList.add("checked")
}

function changeLibraryDir() {
    clearPlayingBook()
    pywebview.api.change_library_dir().then((resp) => {
        if (resp.status != "ok") return
        content = "<div><b>{{ gettext("books_folder.changed") }}</b></div>" + ((resp.data.new_books_count) ? `<div>{{ gettext("books_folder.books_added") }}: ${resp.data.new_books_count}</div>` : "")
        timeout = 5
        if (!resp.data.is_old_library_empty) {
            timeout = 0
            content = content + `<div>{{ gettext("books_folder.downloaded_books_in_old_folder") }}</div>
            <div style="margin-top: 2px; text-decoration: underline; cursor:pointer" onclick="{migrateOldLibrary();this.parentElement.parentElement.remove()}">{{ gettext("books_folder.move_to_new_folder") }}</div>
            <div style="margin-top: 2px; text-decoration: underline; cursor:pointer" onclick="{removeOldLibrary();this.parentElement.parentElement.remove()}">{{ gettext("books_folder.delete_old_books") }}</div>`
        }
        createNotification(content, timeout, true)
    })
}
function migrateOldLibrary() {
    n = createNotification("<div><b>{{ gettext("books_folder.moving_files") }}...</b></div><div>{{ gettext("it_can_take_some_time") }}</div>", 0, false)
    pywebview.api.migrate_old_library().then((resp) => {
        n.querySelector(".cross-btn").click()
        if (resp.status != "ok") return
        createNotification(`<div><b>{{ gettext("books_folder.moving_finished") }}</b><div><div>{{ gettext("books_folder.books_moved") }}: ${resp.data.moved_books_count}</div>`, 10, true)
    })
}
function removeOldLibrary() {
    n = createNotification("<div><b>{{ gettext("books_folder.deleting_files") }}...</b></div><div>{{ gettext("it_can_take_some_time") }}</div>", 0, false)
    pywebview.api.remove_old_library().then((resp) => {
        n.querySelector(".cross-btn").click()
        if (resp.status != "ok") return
        createNotification(`<div><b>{{ gettext("books_folder.deleting_finished") }}</b><div><div>{{ gettext("books_folder.books_deleted") }}: ${resp.data.removed_books_count}</div>`, 10, true)
    })
}

function checkForUpdates(resp) {
    if (resp.status != "ok") {
        setTimeout(checkForUpdates, 60)
        return
    }
    if (!resp.data) return
    if (resp.data.stable || !stable_version) {
        createNotification(
            `<div><b>{{ gettext("update.available") }} ${resp.data.version}</b></div>
            <a style="margin-top: 2px" href="${resp.data.url}" target="_blank">{{ gettext("update.changelog") }}</a>
            <div style="margin-top: 2px; text-decoration: underline; cursor:pointer" onclick="{updateApp();this.parentElement.parentElement.remove()}">{{ gettext("update.install") }}</div>`
        )
    } else if (!only_stable){
        createNotification(
            `<div><b>{{ gettext("update.new_testing_version") }} ${resp.data.version}</b></div>
            <a style="margin-top: 2px" href="${resp.data.url}" target="_blank">{{ gettext("update.changelog") }}</a>
            <div style="margin-top: 2px; text-decoration: underline; cursor:pointer" onclick="{updateApp();this.parentElement.parentElement.remove()}">{{ gettext("update.install") }}</div>
            <div style="margin-top: 2px; text-decoration: underline; cursor:pointer" onclick="{unsubscribeNotStable();this.parentElement.parentElement.remove()}">{{ gettext("update.no_suggest_tests") }}</div>`
        )
    }
}

function updateApp() {
    n = createNotification("<div><b>{{ gettext("update.downloading") }}</b></div><div>{{ gettext("it_can_take_some_time") }}</div>", 0, false)
    pywebview.api.update_app().then((resp) => {
        n.querySelector(".cross-btn").click()
        if (resp.status != "ok") showError(resp.message)
    })
}
function unsubscribeNotStable() {
    pywebview.api.unsubscribe_not_stable()
}
