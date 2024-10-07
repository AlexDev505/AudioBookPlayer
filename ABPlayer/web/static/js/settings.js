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
        content = "<div><b>Папка с книгами изменена</b></div>" + ((resp.data.new_books_count) ? `<div>Книг добавлено: ${resp.data.new_books_count}</div>` : "")
        timeout = 5
        if (!resp.data.is_old_library_empty) {
            timeout = 0
            content = content + `<div>но скачанные ранее файлы остались на месте</div>
            <div style="margin-top: 2px; text-decoration: underline; cursor:pointer" onclick="{migrateOldLibrary();this.parentElement.parentElement.remove()}">Перенести всё в новое место</div>
            <div style="margin-top: 2px; text-decoration: underline; cursor:pointer" onclick="{removeOldLibrary();this.parentElement.parentElement.remove()}">Удалить старые книги из библиотеки</div>`
        }
        createNotification(content, timeout, true)
    })
}
function migrateOldLibrary() {
    n = createNotification("<div><b>Перенос файлов...</b></div><div>это может занять некоторое время</div>", 0, false)
    pywebview.api.migrate_old_library().then((resp) => {
        n.querySelector(".cross-btn").click()
        if (resp.status != "ok") return
        createNotification(`<div><b>Перенос завершен</b><div><div>Книг перенесено: ${resp.data.moved_books_count}</div>`, 10, true)
    })
}
function removeOldLibrary() {
    n = createNotification("<div><b>Удаление старых книг...</b></div><div>это может занять некоторое время</div>", 0, false)
    pywebview.api.remove_old_library().then((resp) => {
        n.querySelector(".cross-btn").click()
        if (resp.status != "ok") return
        createNotification(`<div><b>Удаление завершено</b><div><div>Книг удалено: ${resp.data.removed_books_count}</div>`, 10, true)
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
            `<div><b>Доступно обновление ${resp.data.version}</b></div>
            <a style="margin-top: 2px" href="${resp.data.url}" target="_blank">список изменений</a>
            <div style="margin-top: 2px; text-decoration: underline; cursor:pointer" onclick="{updateApp();this.parentElement.parentElement.remove()}">установить</div>`
        )
    } else if (!only_stable){
        createNotification(
            `<div><b>Доступна новая версия для тестирования ${resp.data.version}</b></div>
            <a style="margin-top: 2px" href="${resp.data.url}" target="_blank">список изменений</a>
            <div style="margin-top: 2px; text-decoration: underline; cursor:pointer" onclick="{updateApp();this.parentElement.parentElement.remove()}">установить</div>
            <div style="margin-top: 2px; text-decoration: underline; cursor:pointer" onclick="{unsubscribeNotStable();this.parentElement.parentElement.remove()}">не предлагать участие в тестировании</div>`
        )
    }
}

function updateApp() {
    n = createNotification("<div><b>Загрузка обновления</b></div><div>это может занять некоторое время</div>", 0, false)
    pywebview.api.update_app().then((resp) => {
        n.querySelector(".cross-btn").click()
        if (resp.status != "ok") showError(resp.message)
    })
}
function unsubscribeNotStable() {
    pywebview.api.unsubscribe_not_stable()
}
