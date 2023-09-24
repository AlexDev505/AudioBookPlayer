var current_section = null
class Section {
    constructor(el) {
        this.el = el
        this.btn = document.getElementById(el.id + "-btn")
        this.hide()
    }
    show() {
        if (current_section) current_section.hide()
        current_section = this
        this.el.style = "display: block"
        this.btn.classList.add("active")
    }
    hide() {
        this.el.style = "display: none"
        this.btn.classList.remove("active")
    }
}
var sections = {}
for (section_el of document.getElementsByClassName("books-section")) {
    sections[section_el.id] = new Section(section_el)
}
function section(el_id) {return sections[el_id]}
section("all-books-section").show()
