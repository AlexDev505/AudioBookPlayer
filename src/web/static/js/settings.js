page("settings-page").onOpen = function () {};
page("settings-page").onHide = function () {};
page("settings-page").unLoad = function () {};

function toggleDarkTheme() {
  dark_theme = !dark_theme;
  pywebview.api.set_dark_mode(dark_theme).then((_) => {
    location.reload();
  });
  toggleDarkThemeCheckBox(dark_theme);
}
function toggleDarkThemeCheckBox(value) {
  document
    .getElementById("dark-theme-checkbox")
    .classList.toggle("checked", value);
}

function setLanguage(button) {
  lang = button.dataset.lang;
  pywebview.api.set_language(lang).then((_) => {
    location.reload();
  });
  toggleLanguageButton(lang);
}
function toggleLanguageButton(lang) {
  let checked = document.querySelector(".lang-checkbox.checked");
  if (checked) checked.classList.remove("checked");
  document
    .querySelector(`.lang-checkbox[data-lang='${lang}']`)
    .classList.add("checked");
}

function changeLibraryDir() {
  clearPlayingBook();
  pywebview.api.change_library_dir().then((resp) => {
    if (resp.status != "ok") return showError(resp.message);
    var dirChanged = document
      .getElementById("dir-changed-notification")
      .content.cloneNode(true);
    dirChanged.querySelector(".books-count").textContent =
      resp.data.new_books_count;
    dirChanged.querySelector(".sources-count").textContent =
      resp.data.new_sources_count;
    if (resp.data.is_old_library_empty)
      dirChanged.querySelector(".old-library-actions").remove();
    createNotification(
      dirChanged,
      resp.data.is_old_library_empty ? 5 : 0,
      true,
    );
  });
}
function migrateOldLibrary() {
  var moving = document
    .getElementById("moving-files-notification")
    .content.cloneNode(true);
  var n = createNotification(moving, 0, false);
  pywebview.api.migrate_old_library().then((resp) => {
    closeNotification(n);
    if (resp.status != "ok") return showError(resp.message);
    var movingFinished = document
      .getElementById("moving-finished-notification")
      .content.cloneNode(true);
    movingFinished.querySelector(".count").textContent =
      resp.data.moved_books_count;
    createNotification(movingFinished, 10, true);
  });
}
function removeOldLibrary() {
  var removing = document
    .getElementById("removing-files-notification")
    .content.cloneNode(true);
  var n = createNotification(removing, 0, false);
  pywebview.api.remove_old_library().then((resp) => {
    closeNotification(n);
    if (resp.status != "ok") return showError(resp.message);
    var removingFinished = document
      .getElementById("removing-finished-notification")
      .content.cloneNode(true);
    removingFinished.querySelector(".count").textContent =
      resp.data.removed_books_count;
    createNotification(removingFinished, 10, true);
  });
}
