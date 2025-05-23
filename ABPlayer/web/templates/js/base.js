var urlParams = new URLSearchParams(window.location.search);

var player = null

for (size_grip of document.getElementsByClassName("size-grip")) {
    size_grip.addEventListener("mousedown", event => {
    if (event.button == 0)
        pywebview.api.resize_drag(event.target.dataset.place)
    })
}

document.getElementById("top-bar").addEventListener("mousedown", event => {
    if (event.button == 0) {
        if (!["top-bar", "logo"].includes(event.target.id))
            return
        pywebview.api.drag_window()
    }
})

function getHttpRequestObject() {
    // Define and initialize as false
    var xmlHttpRequst = false;

    // Mozilla/Safari/Non-IE
    if (window.XMLHttpRequest)
    {
      xmlHttpRequst = new XMLHttpRequest();
    }
    // IE
    else if (window.ActiveXObject)
    {
      xmlHttpRequst = new ActiveXObject("Microsoft.XMLHTTP");
    }
    return xmlHttpRequst;
}

var sideMenu = document.getElementById("side-menu")
function toggleMenu() {
    if (menu_opened)
        sideMenu.classList.add("collapsed")
    else
        sideMenu.classList.remove("collapsed")
    menu_opened = !menu_opened
}

class Page {
    current = null

    constructor(el) {
        this.el = el
        this.shown = false
        this.onShow = null
        this.onHide = null
    }
    show() {
        if (this.constructor.current == this) return
        if (
            this.constructor.current &&
            this.constructor.current.constructor == this.constructor
        ) this.constructor.current.hide()
        this.constructor.current = this
        this.el.style = "display: block"
        this.shown = true
        if (this.onShow) this.onShow(this.el)
    }
    hide() {
        this.constructor.current = null
        this.el.style = "display: none"
        this.shown = false
        if (this.onHide) this.onHide(this.el)
    }
}

var pages = {}
for (let page_el of document.getElementsByClassName("page")) {
    page_ = new Page(page_el)
    pages[page_el.id] = page_
    page_.hide()
}
function page(el_id) {return pages[el_id]}

function addUrlParams(params) {
    var refresh = window.location.protocol + "//" + window.location.host + "?";
    for (let [name, value] of Object.entries(params)) {
        urlParams.set(name, value)
    }
    urlParams.forEach((v, k) => {
        refresh = refresh + `${k}=${v}&`
    })
    window.history.pushState({path: refresh}, '', refresh)
}

function PWVReady() {
    parseUrlParams()
    pywebview.api.check_for_updates().then(checkForUpdates)
    pywebview.api.get_downloads().then(showDownloads)
    pywebview.api.get_available_drivers().then(loadAvailableDrivers)
    toggleDarkThemeCheckBox(dark_theme)
    toggleLanguageButton(lang)
    loadLastListenedBook()
}
function parseUrlParams() {
    var page_name = urlParams.get("page")
    if (page_name) {
        var page_obj = page(page_name)
        if (page_obj) {
            page_obj.show()
            return
        }
    }
    page("library-page").show()
}
window.addEventListener("pywebviewready", PWVReady)

function delay(time) {
    return new Promise(resolve => setTimeout(resolve, time));
}

function openLibraryPage(favorite=null) {
    library_page = page('library-page')
    if (favorite != null) addUrlParams({"favorite": Number(favorite)})
    if (!library_page.shown) {
        library_page.show()
    } else {
        library_page.onHide()
        if (favorite != null) addUrlParams({"favorite": Number(favorite)})
        library_page.onShow(library_page.el)
    }
}

notifications_count = 0
function createNotification(content, timeout=0, closable=true) {
    notifications_count = notifications_count + 1
    if (notifications_count == 6) {
        notifications_count = notifications_count - 1
        document.querySelector(".notification").remove()
    }
    notifications = document.getElementById("notifications")
    var notification = document.createElement("div")
    notifications.appendChild(notification)
    notification.classList.add("notification")
    notification.innerHTML = `<div class="notification-content">${content}</div><div class="icon-btn cross-btn"></div>`
    notification.querySelector(".cross-btn").onclick = function() {this.parentElement.remove();notifications_count=notifications_count-1}
    if (timeout) setTimeout(function(notification){if(!notification.isConnected) return;notification.remove();notifications_count=notifications_count-1}, timeout*1000, notification)
    if (!closable) notification.querySelector(".cross-btn").style.display = "none"
    return notification
}
function showError(text) {
    createNotification(
        `<div style="font-weight: bold">Ошибка</div><div>${text}</div>`, 30, true
    )
}

function openLibraryDir() {
    pywebview.api.open_library_dir()
}

function scaleOninputDecorator(func) {
    return function() {
        this.setAttribute('data-value',
        `${(this.dataset.prefix)?this.dataset.prefix:""}${this.value}${(this.dataset.postfix)?this.dataset.postfix:""}`);
        func.apply(this)
    }
}
function toggleVolumeSpeed(section) {
    if (section == "volume-input") document.getElementById("speed-input").classList.remove("showed")
    if (section == "speed-input") document.getElementById("volume-input").classList.remove("showed")
    let el = document.getElementById(section)
    if (el.classList.contains("showed")) el.classList.remove("showed")
    else el.classList.add("showed")
}
const volumeBtn = document.getElementById("volume-btn")
volumeBtn.onclick = function() {toggleVolumeSpeed("volume-input")}
document.getElementById("speed-btn").onclick = function() {toggleVolumeSpeed("speed-input")}
function setVolume(value) {
    player.volume = value / 100
    volumeBtn.classList.remove("muted")
    volumeBtn.classList.remove("low")
    volumeBtn.classList.remove("medium")
    if (value == 0) volumeBtn.classList.add("muted")
    else if (value <= 33) volumeBtn.classList.add("low")
    else if (value <= 66) volumeBtn.classList.add("medium")
}
function setSpeed(value) {
    player.speed = Number(value)
}
function loadAvailableDrivers(resp) {
    container = document.getElementById("drivers-container")
    licensed_container = document.getElementById("licensed-container")
    if (required_drivers.length == 0) {
        for (driver of resp.data) required_drivers.push(driver.name)
    }
    _required_drivers = required_drivers.slice(0, required_drivers.length)
    required_drivers = []
    for (driver of resp.data) {
        if (_required_drivers.includes(driver.name) && driver.authed) required_drivers.push(driver.name)
        container.innerHTML += `
          <div class="driver-option checkbox ${(_required_drivers.includes(driver.name) && driver.authed) ? 'checked' : ''} ${(!driver.authed)? 'inactive': ''}" data-driver="${driver.name}" onclick="toggleDriver('${driver.name}', this)">${driver.name}</div>
        `
        if (driver.licensed) {
            licensed_container.innerHTML += `
              <div class="licensed-card">
                <a class="book-title" href="${driver.url}" target="_blank">${driver.name}</a>
                <div class="licensed-status">${(driver.authed)? "{{ gettext('licensed.authed') }}": "{{ gettext('licensed.not_authed') }}"}</div>
                <div class="button licensed-btn" data-driver="${driver.name}" data-authed="${driver.authed}" onclick="licensedBtnClicked(this)">${(driver.authed)? "{{ gettext('licensed.logout') }}": "{{ gettext('licensed.login') }}"}</div>
              </div>
            `
        }
    }
}