page("search-page").onShow = function (el) {
  q = urlParams.get("search");
  if (q) {
    document.querySelector("#search-input-line input").value = q;
    searchBooks();
  }
};
page("search-page").onHide = function () {
  urlParams.delete("search");
};
page("search-page").unLoad = function () {
  document.getElementById("search-results-container").innerHTML = "";
  document.querySelector("#search-input-line input").value = "";
  document.getElementById("search-results-container").classList.remove("shown");
};
