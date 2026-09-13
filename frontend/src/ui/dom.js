/**
 * Tiny DOM helpers. No framework, no build step.
 *
 * `h()` is the whole rendering layer: it builds real elements, so text always
 * goes through textContent and user input can never become markup.
 */

export function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);

  for (const [key, value] of Object.entries(props || {})) {
    if (value === null || value === undefined || value === false) continue;

    if (key === "class") el.className = value;
    else if (key === "dataset") Object.assign(el.dataset, value);
    else if (key === "style") Object.assign(el.style, value);
    else if (key.startsWith("on") && typeof value === "function") {
      el.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (key === "html") el.innerHTML = value;
    else if (key in el && key !== "list" && typeof value !== "object") el[key] = value;
    else el.setAttribute(key, value === true ? "" : value);
  }

  append(el, children);
  return el;
}

function append(parent, children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false || child === "") continue;
    parent.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

export function clear(el) {
  while (el.firstChild) el.firstChild.remove();
  return el;
}

export function mount(el, ...children) {
  clear(el);
  append(el, children);
  return el;
}

/** A labelled form field. Returns the wrapper; the control is at `.control`. */
export function field(label, control, { error, hint } = {}) {
  const wrap = h(
    "div",
    { class: "field" },
    label && h("label", { class: "field-label", for: control.id || undefined }, label),
    control,
    hint && h("div", { class: "muted", style: { fontSize: "12.5px" } }, hint),
    error && h("div", { class: "field-error" }, error)
  );
  wrap.control = control;
  return wrap;
}

export function select(options, value, props = {}) {
  return h(
    "select",
    { class: "select", ...props },
    options.map(([optionValue, label]) =>
      h("option", { value: optionValue, selected: optionValue === value }, label)
    )
  );
}

export function icon(glyph, props = {}) {
  return h("span", { "aria-hidden": "true", ...props }, glyph);
}

/** Focus the first focusable thing inside a container — used by the drawer and modals. */
export function focusFirst(container) {
  const target = container.querySelector(
    "input:not([type=hidden]), textarea, select, button, [href], [tabindex]:not([tabindex='-1'])"
  );
  if (target) target.focus();
}

export function debounce(fn, ms = 220) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}
