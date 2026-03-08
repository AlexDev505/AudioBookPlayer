var urlParams = new URLSearchParams(window.location.search);
function applyUrlParams() {
  var refresh = window.location.protocol + "//" + window.location.host + "?";
  refresh += urlParams.toString();
  window.history.pushState({ path: refresh }, "", refresh);
}
function addUrlParams(params) {
  for (let [name, value] of Object.entries(params)) urlParams.set(name, value);
  applyUrlParams();
}
function removeUrlParams(params) {
  for (let name of params) urlParams.delete(name);
  applyUrlParams();
}
function clearUrlParams() {
  removeUrlParams(urlParams.keys());
}

function delay(time) {
  return new Promise((resolve) => setTimeout(resolve, time));
}

if (platform == "Windows") {
  for (size_grip of document.getElementsByClassName("size-grip")) {
    size_grip.addEventListener("mousedown", (event) => {
      if (event.button == 0)
        pywebview.api.resize_drag(event.target.dataset.place);
    });
  }

  document.getElementById("top-bar").addEventListener("mousedown", (event) => {
    if (event.button == 0) {
      if (!["top-bar", "logo"].includes(event.target.id)) return;
      pywebview.api.drag_window();
    }
  });
}

var notifications_count = 0;
const notificationTemplate = document.getElementById("notification-template");
function createNotification(content, timeout = 0, closable = true) {
  notifications_count += 1;
  if (notifications_count == 6) {
    notifications_count -= 1;
    document.querySelector(".notification").remove();
  }
  var notifications = document.getElementById("notifications");
  var notification = document.importNode(notificationTemplate.content, true);
  notification.querySelector(".notification-content").appendChild(content);
  notification.querySelector(".cross-btn").onclick = function () {
    this.parentElement.remove();
    notifications_count -= 1;
  };
  notifications.appendChild(notification);
  if (timeout)
    setTimeout(
      function (notification) {
        if (!notification.isConnected) return;
        notification.remove();
        notifications_count -= 1;
      },
      timeout * 1000,
      notification,
    );
  if (!closable)
    notification.querySelector(".cross-btn").style.display = "none";
  return notification;
}
function showError(text) {
  var errorNotification = document
    .getElementById("error-notification-template")
    .content.cloneNode(true);
  errorNotification.querySelector(".content").innerText = text;
  createNotification(errorNotification, 30, true);
}

var sideMenu = document.getElementById("side-menu");
function toggleMenu() {
  pywebview.state.menu_opened = !sideMenu.classList.toggle("collapsed");
}

class Page {
  current = null;
  last = null;

  constructor(el) {
    this.el = el;
    this.shown = false;
    this.onOpen = null;
    this.onHide = null;
    this.unLoad = null;
  }
  open() {
    if (this.constructor.current == this) return;
    if (this.constructor.last && this.constructor.last != this) {
      if (this.constructor.last.unLoad)
        this.constructor.last.unLoad(this.constructor.last.el);
    }
    var restore = this == this.constructor.last;
    if (
      this.constructor.current &&
      this.constructor.current.constructor == this.constructor
    ) {
      this.constructor.last = this.constructor.current;
      this.constructor.current.hide();
    }
    this.constructor.current = this;
    addUrlParams({ page: this.el.id });
    if (this.onOpen && !restore) this.onOpen(this.el);
    this.el.style = "display: block";
    this.shown = true;
  }
  hide() {
    this.constructor.current = null;
    this.el.style = "display: none";
    this.shown = false;
    if (this.onHide) this.onHide(this.el);
  }
}

var pages = {};
for (let page_el of document.getElementsByClassName("page")) {
  var page_ = new Page(page_el);
  pages[page_el.id] = page_;
}
function page(el_id) {
  return pages[el_id];
}
function openPageFromUrlParams() {
  var page_name = urlParams.get("page") || "library-page";
  var page_obj = page(page_name);
  if (page_obj) page_obj.open();
}

window.addEventListener("pywebviewready", function () {
  openPageFromUrlParams();
  pywebview.state.menu_opened = !sideMenu.classList.contains("collapsed");
  // pywebview.api.check_for_updates().then(checkForUpdates);
  // pywebview.api.get_downloads().then(showDownloads);
  // pywebview.api.get_available_drivers().then(loadAvailableDrivers);
  // toggleDarkThemeCheckBox(dark_theme);
  // toggleLanguageButton(lang);
  // loadLastListenedBook();
});

function openLibraryPage(favorite = false) {
  library_page = page("library-page");
  if (favorite == true) addUrlParams({ favorite: 1 });
  else if (favorite == false && urlParams.get("favorite"))
    removeUrlParams(["favorite"]);
  if (
    library_page.shown ||
    (Page.last == library_page && favorite != library_filters.favorite)
  ) {
    library_page.unLoad(library_page.el);
    library_page.onOpen(library_page.el);
  } else {
    library_page.open();
  }
}

function openLibraryDir() {
  pywebview.api.open_library_dir();
}

function scaleOninputDecorator(func) {
  return function () {
    this.setAttribute(
      "data-value",
      `${this.dataset.prefix ? this.dataset.prefix : ""}${this.value}${this.dataset.postfix ? this.dataset.postfix : ""}`,
    );
    func.apply(this);
  };
}
