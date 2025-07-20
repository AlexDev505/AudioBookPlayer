page("licensed-page").onShow = function (el) {
  addUrlParams({ page: el.id });
};
page("licensed-page").onHide = function () {};

function licensedBtnClicked(btn) {
  if (btn.classList.contains("loading")) return;
  btn.classList.add("loading");
  if (btn.dataset.authed == "true")
    pywebview.api.logout_driver(btn.dataset.driver).then((resp) => {
      location.reload();
    });
  else {
    pywebview.api.login_driver(btn.dataset.driver).then((resp) => {
      if (resp.status != "ok") {
        btn.classList.remove("loading");
        return showError(resp.message);
      }
      location.reload();
    });
  }
}
