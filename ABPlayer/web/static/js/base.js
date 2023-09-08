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

function getHttpRequestObject()
{
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

sideMenu = document.getElementById("side-menu")
var menu_opened = true
function toggleMenu() {
    if (menu_opened)
        sideMenu.classList.add("collapsed")
    else
        sideMenu.classList.remove("collapsed")
    menu_opened = !menu_opened
}
